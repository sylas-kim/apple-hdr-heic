import argparse
from pathlib import Path

import cv2
import pillow_heif
from pillow_heif import HeifFile

from apple_hdr_heic import load_as_bt2100_pq, quantize_to_uint16


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="apple-hdr-heic-decoder",
        description=(
            "Decode an HEIC image file containing HDR gain map and other metadata (in Apple's format) to "
            "a 48-bit PNG file or a 10- or 12-bit HEIC or AVIF file in BT.2100 color space with PQ transfer function."
        ),
    )
    parser.add_argument("input_image", help="Input HEIC image path")
    parser.add_argument("output_image", help="Output image path (supports: .png, .heic, .avif)")
    parser.add_argument(
        "-q", "--quality", type=int, default=-1,
        help="Output image quality; 0 = lowest; 100 = highest; ignored for .png (default: lossless, see readme)",
    )  # fmt: skip
    parser.add_argument(
        "-b", "--bitdepth", type=int, default=10, choices=[10, 12],
        help="Output channel bit-depth; ignored for .png (default: 10-bit)",
    )  # fmt: skip
    parser.add_argument(
        "-y", "--yuv", type=str, default=None, choices=["420", "422", "444"],
        help="Output chroma subsampling; ignored for .png (default: 420)",
    )  # fmt: skip
    args = parser.parse_args()

    assert args.input_image.lower().endswith(".heic")
    assert -1 <= args.quality <= 100
    bt2100_pq = load_as_bt2100_pq(args.input_image)
    bt2100_pq_u16 = quantize_to_uint16(bt2100_pq)
    output_ext = Path(args.output_image).suffix.lower()
    if output_ext == ".png":
        write_png(args.output_image, bt2100_pq_u16)
    elif output_ext == ".heic":
        write_heif(
            args.output_image,
            bt2100_pq_u16,
            quality=args.quality,
            bitdepth=args.bitdepth,
            yuv=args.yuv,
        )
    elif output_ext == ".avif":
        write_heif(
            args.output_image,
            bt2100_pq_u16,
            format="AVIF",
            quality=args.quality,
            bitdepth=args.bitdepth,
            yuv=args.yuv,
        )
    else:
        raise ValueError(f"Output file type not supported: {output_ext}")


def write_png(out_path, rgb_data):
    cv2.imwrite(out_path, rgb_data[:, :, ::-1])
    # note: currently Pillow doesn't support 16-bit per channel RGB images
    #       see https://github.com/python-pillow/Pillow/issues/1888
    # note: adding cICP data to PNG files (to indicate BT.2100 PQ) is difficult
    #       see https://github.com/w3c/png/issues/312
    #       see https://github.com/pnggroup/libpng/issues/508
    #       see https://github.com/randy408/libspng/issues/218


def write_heif(out_path, rgb_data, format="HEIF", quality=-1, bitdepth=10, yuv=None):
    if bitdepth == 12:
        pillow_heif.options.SAVE_HDR_TO_12_BIT = True
    imsize = (rgb_data.shape[1], rgb_data.shape[0])
    heif_file = HeifFile()
    added_image = heif_file.add_frombytes(
        mode="RGB;16",
        size=imsize,
        data=bytes(rgb_data),
    )
    added_image.info["color_primaries"] = 9
    added_image.info["transfer_characteristics"] = 16
    added_image.info["matrix_coefficients"] = 9
    added_image.info["full_range_flag"] = 1
    heif_file.save(out_path, format=format, quality=quality, chroma=yuv)


if __name__ == "__main__":
    main()
