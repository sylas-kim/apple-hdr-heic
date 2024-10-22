import colour
import cv2
import numpy as np
import pillow_heif
from exiftool import ExifToolHelper

REF_WHITE_LUM = 203.0  # reference white luminance in nits


class AppleHDRMetadata:
    __slots__ = ["maker33", "maker48", "profile_desc", "hdrgainmap_version", "aux_type"]

    def __init__(self, file_name):
        for attr in self.__slots__:
            setattr(self, attr, None)
        # we are primarily interested in maker tags 33 (0x0021) and 48 (0x0030)
        # see https://github.com/exiftool/exiftool/blob/405674e0/lib/Image/ExifTool/Apple.pm
        tag_patterns = ["XMP:HDR*", "Apple:HDR*", "ICC_Profile:ProfileDesc*", "Quicktime:Auxiliary*"]
        with ExifToolHelper() as et:
            tags = et.get_tags(file_name, tags=tag_patterns)[0]
            for tag, val in tags.items():
                if tag == "XMP:HDRGainMapVersion":
                    self.hdrgainmap_version = val
                elif tag == "MakerNotes:HDRHeadroom":
                    self.maker33 = val
                elif tag == "MakerNotes:HDRGain":
                    self.maker48 = val
                elif tag == "ICC_Profile:ProfileDescription":
                    self.profile_desc = val
                elif tag == "Quicktime:AuxiliaryImageType":
                    self.aux_type = val

    @property
    def headroom(self) -> float:
        # ref https://developer.apple.com/documentation/appkit/images_and_pdf/applying_apple_hdr_effect_to_your_photos
        assert self.maker33 is not None and self.maker48 is not None
        if self.maker33 < 1.0:
            if self.maker48 <= 0.01:
                stops = -20.0 * self.maker48 + 1.8
            else:
                stops = -0.101 * self.maker48 + 1.601
        else:
            if self.maker48 <= 0.01:
                stops = -70.0 * self.maker48 + 3.0
            else:
                stops = -0.303 * self.maker48 + 2.303
        return 2.0 ** max(stops, 0.0)


# ref https://developer.apple.com/documentation/appkit/images_and_pdf/applying_apple_hdr_effect_to_your_photos
def combine_hdrgainmap(dp3_sdr, hdrgainmap, headroom: float):
    """
    Combine the a (non-linear) Display P3 SDR image with its HDR gain map.

    :param dp3_sdr: A float32 numpy array of shape (H1, W1, 3) with values between 0 and 1.
    :param hdrgainmap: A float32 numpy array of shape (H2, W2) with values between 0 and 1.
    :param headroom: The value of AppleHDRMetadata.headroom property of the image.

    :returns: A float32 numpy array of shape (H1, W1, 3) with values between 0 and ``headroom``
    """
    # note: Display P3 and sRGB have the same EOTF
    dp3_sdr_linear = colour.models.eotf_sRGB(dp3_sdr)
    h, w = dp3_sdr.shape[:2]
    hdrgainmap = cv2.resize(hdrgainmap, (w, h))
    hdrgainmap_linear = colour.models.eotf_sRGB(hdrgainmap)[:, :, None]
    return dp3_sdr_linear * (1.0 + (headroom - 1.0) * hdrgainmap_linear)


def load_and_combine_gainmap(file_name) -> np.ndarray:
    """
    Loads an HEIC file and returns the HDR image in linear Display P3 color space.

    :param file_name: A path to an HEIC image file containing HDR gain map data.

    :returns: A float32 numpy array of shape (H, W, 3) in linear Display P3 color space.
    """
    hdr_metadata = AppleHDRMetadata(file_name)
    assert hdr_metadata.profile_desc == "Display P3"
    aux_type = hdr_metadata.aux_type or "urn:com:apple:photo:2020:aux:hdrgainmap"
    headroom = hdr_metadata.headroom

    heif_file = pillow_heif.open_heif(file_name)
    dp3_sdr = np.asarray(heif_file) / np.float32(255)
    hdrgainmap = hdrgainmap / np.float32(255)
    assert aux_type in heif_file.info["aux"]
    aux_id = heif_file.info["aux"][aux_type][0]
    aux_im = heif_file.get_aux_image(aux_id)

    return combine_hdrgainmap(np.asarray(heif_file), np.asarray(aux_im), headroom)


def displayp3_to_bt2020(dp3_hdr):
    """
    Converts an image in linear Display P3 color space to BT.2020 color space.

    :param dp3_hdr: A float32 array of shape (H, W, 3) in Display P3 space.

    :returns: A float32 array of shape (H, W, 3) in BT.2020 color space, with values clipped to be non-negative.
    """
    input_colourspace = colour.RGB_COLOURSPACES["Display P3"]
    output_colourspace = colour.RGB_COLOURSPACES["ITU-R BT.2020"]
    transform_matrix = colour.matrix_RGB_to_RGB(input_colourspace, output_colourspace)
    bt2020_hdr = np.tensordot(dp3_hdr, transform_matrix, axes=(2, 1))
    #bt2020_hdr = np.einsum("hwj,ij->hwi", dp3_hdr, transform_matrix)  # same as above tensordot but slower

    return np.clip(bt2020_hdr, 0.0, None, out=bt2020_hdr)


def load_as_bt2100_pq(file_name, white_lum: float = REF_WHITE_LUM):
    """
    Loads an HEIC file and returns the HDR image in non-linear BT.2100 PQ color space.

    :param file_name: A path to an HEIC image file containing HDR gain map data.
    :param white_lum: Luminance of reference white in cd/m2 (or nits). Default: 203 nits

    :returns: A float32 array of shape (H, W, 3) in non-linear BT.2100 color space with PQ transfer function, with values between 0 and 1.
    """
    dp3_hdr = load_and_combine_gainmap(file_name)
    bt2020_hdr = displayp3_to_bt2020(dp3_hdr)
    return colour.models.eotf_inverse_BT2100_PQ(white_lum * bt2020_hdr)
