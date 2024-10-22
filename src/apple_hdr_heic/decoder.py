import argparse

import cv2

from apple_hdr_heic import load_as_bt2100_pq


def main():
    parser = argparse.ArgumentParser(
        prog="apple-hdr-heic-decoder",
        description=(
            "Decode an HEIC image file containing HDR gain map and other metadata (in Apple's format) to "
            "a 48-bit PNG file in BT.2100 color space with PQ transfer function."
        ),
    )
    parser.add_argument('input_image')
    parser.add_argument('output_image')
    args = parser.parse_args()

    assert args.input_image.lower().endswith(".heic")
    assert args.output_image.lower().endswith(".png")
    rgb_hdr_pq = load_as_bt2100_pq(args.input_image)
    rgb_hdr_pq_u16 = np.round(rgb_hdr_pq * np.iinfo(np.uint16).max).astype(np.uint16)
    bgr_hdr_pq_u16 = cv2.cvtColor(rgb_hdr_pq_u16, cv2.COLOR_RGB2BGR)
    cv2.imwrite(args.output_image, bgr_hdr_pq_u16)
    # adding cICP data to PNG files is difficult https://github.com/w3c/png/issues/312


if __name__ == "__main__":
    main()
