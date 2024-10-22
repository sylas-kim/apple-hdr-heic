# apple-hdr-heic

A library/tool to decode photos (HEIC files) taken on an iPhone that contain HDR gain map, and convert it to a 48-bit (16-bit per channel) HDR representation.

## Pre-requisites

* Python 3.10+
* [`exiftool`](https://exiftool.org/)
  - For Ubuntu or Debian, do `sudo apt install libimage-exiftool-perl`
  - For other Linux distros, search `exiftool` using your package manager
  - For Mac or Windows, follow the instructions in website
  - For Windows, it is also available via [Scoop](https://scoop.sh/)

## Installation

Clone this repository, create a python environment and do:

```
pip install .
```

## Usage

CLI tool:

```
apple-hdr-heic-decode input.heic output.png
```

Library usage:

```
from apple_hdr_heic import apple_hdr_to_bt2100_pq

rgb_hdr_pq = apple_hdr_to_bt2100_pq("input.heic")
rgb_hdr_pq_u16 = np.round(rgb_hdr_pq * np.iinfo(np.uint16).max).astype(np.uint16)
bgr_hdr_pq_u16 = cv2.cvtColor(rgb_hdr_pq_u16, cv2.COLOR_RGB2BGR)
cv2.imwrite("output.png", bgr_hdr_pq_u16)
```

The output file `output.png` does not contain the necessary [cICP](https://en.wikipedia.org/wiki/Coding-independent_code_points) metadata that denotes it to have `bt2020` (9) color primaries, `smpte2084` (16) transfer function and `bt2020nc` color space.

To convert the above PNG to a 12-bit HDR AVIF file with appropriate metadata, do:

```
avifenc -s 4 -j 4 --min 1 --max 56 -a end-usage=q -a cq-level=20 -a tune=ssim -a color:enable-qm=1 \
    -a color:enable-chroma-deltaq=1 -d 12 --cicp 9/16/9 output.png output.avif
```
