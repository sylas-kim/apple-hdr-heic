import os
from pathlib import Path

import cv2
import numpy as np
import numpy.typing as npt
import pillow_heif

from apple_hdr_heic.metadata import AppleHDRMetadata

os.environ["COLOUR_SCIENCE__FILTER_USAGE_WARNINGS"] = "True"
os.environ["COLOUR_SCIENCE__DEFAULT_FLOAT_DTYPE"] = "float32"

import colour  # may raise a missing matplotlib warning

REF_WHITE_LUM = 203.0  # reference white luminance in nits


# ref https://developer.apple.com/documentation/appkit/images_and_pdf/applying_apple_hdr_effect_to_your_photos
def combine_hdrgainmap(
    dp3_sdr: npt.NDArray[np.floating],
    hdrgainmap: npt.NDArray[np.floating],
    headroom: float,
) -> npt.NDArray[np.floating]:
    """
    Combine a (non-linear) Display P3 SDR image with its HDR gain map.

    :param dp3_sdr: A numpy array of shape (H, W, 3) with values between 0 and 1.
    :param hdrgainmap: A numpy array of shape (H, W) with values between 0 and 1.
    :param headroom: The value of AppleHDRMetadata.headroom property of the image.

    :returns: A numpy array of shape (H, W, 3) with values between 0 and ``headroom``.
    :exception AssertionError: if height and width of ``dp3_sdr`` does not match that of ``hdrgainmap``.
    """
    assert np.issubdtype(dp3_sdr.dtype, np.floating)
    assert np.issubdtype(hdrgainmap.dtype, np.floating)
    # note: Display P3 and sRGB have the same EOTF
    dp3_sdr_linear = colour.models.eotf_sRGB(dp3_sdr)
    assert dp3_sdr.shape[:2] == hdrgainmap.shape
    hdrgainmap_linear = colour.models.eotf_sRGB(hdrgainmap)[:, :, None]
    return dp3_sdr_linear * (1.0 + (headroom - 1.0) * hdrgainmap_linear)


def displayp3_to_bt2020(dp3_hdr: npt.NDArray[np.floating]) -> npt.NDArray[np.floating]:
    """
    Converts an image in Display P3 color space to BT.2020 color space, using simple linear transformation.

    :param dp3_hdr: A numpy array of shape (H, W, 3) in linear Display P3 color space.

    :returns: A numpy array of shape (H, W, 3) in linear BT.2020 color space,
        with negative values truncated to zero and dtype the same as ``dp3_sdr``
    """
    assert np.issubdtype(dp3_hdr.dtype, np.floating)
    input_colourspace = colour.RGB_COLOURSPACES["Display P3"]
    output_colourspace = colour.RGB_COLOURSPACES["ITU-R BT.2020"]
    transform_matrix = colour.matrix_RGB_to_RGB(input_colourspace, output_colourspace).astype(dp3_hdr.dtype)
    bt2020_hdr = np.tensordot(dp3_hdr, transform_matrix, axes=(2, 1))
    return np.clip(bt2020_hdr, 0.0, None, out=bt2020_hdr)


def load_and_combine_gainmap(file_name: str | Path) -> npt.NDArray[np.floating]:
    """
    Loads an HEIC file and returns the HDR image in linear Display P3 color space.

    :param file_name: A path to an HEIC image file containing HDR gain map data.

    :returns: A float32 numpy array of shape (H, W, 3) in linear Display P3 color space.
    """
    hdr_metadata = AppleHDRMetadata.from_file(file_name)
    assert hdr_metadata.profile_desc == "Display P3"
    aux_type = hdr_metadata.aux_type or "urn:com:apple:photo:2020:aux:hdrgainmap"
    headroom = hdr_metadata.headroom

    heif_file = pillow_heif.open_heif(file_name)
    assert aux_type in heif_file.info["aux"]
    aux_id = heif_file.info["aux"][aux_type][0]
    aux_im = heif_file.get_aux_image(aux_id)
    hdrgainmap = np.asarray(aux_im) / np.float32(255)
    hdrgainmap = cv2.resize(hdrgainmap, heif_file.size)  # type: ignore  # bilinear

    dp3_sdr = np.asarray(heif_file) / np.float32(255)
    return combine_hdrgainmap(dp3_sdr, hdrgainmap, headroom)


def load_as_bt2100_pq(file_name: str | Path, white_lum: float = REF_WHITE_LUM) -> npt.NDArray[np.floating]:
    """
    Loads an HEIC file and returns the HDR image in non-linear BT.2100 PQ color space.

    :param file_name: A path to an HEIC image file containing HDR gain map data.
    :param white_lum: Luminance of reference white in cd/m2 (or nits). Default: 203 nits

    :returns: A float32 array of shape (H, W, 3) in non-linear BT.2100 color space with PQ transfer function,
        with values between 0 and 1.
    """
    dp3_hdr = load_and_combine_gainmap(file_name)
    bt2020_hdr = displayp3_to_bt2020(dp3_hdr)
    return colour.models.eotf_inverse_BT2100_PQ(white_lum * bt2020_hdr)


def quantize_to_uint16(float_array: npt.NDArray[np.floating]) -> npt.NDArray[np.uint16]:
    """
    Quantizes a floating point numpy array with values in the unit interval to a 16-bit unsigned integer.

    :param float_array: A floating point numpy array with values between 0 and 1.

    :returns: A uint16 numpy array.
    """
    quantized = float_array * 0xffff
    np.round(quantized, out=quantized)
    np.clip(quantized, 0, 0xffff, out=quantized)
    return quantized.astype(np.uint16)
