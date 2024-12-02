# apple-hdr-heic

A library/tool to decode photos (HEIC files) taken on an iPhone that contain HDR gain map, and convert it to a 48-bit (16-bit per channel) HDR representation as per [Rec. 2100](https://en.wikipedia.org/wiki/Rec._2100) with PQ transfer function.

**Disclaimer:** This project is _not_ affiliated with, or endorsed by, Apple Inc. or any of its subsidiaries.

## Pre-requisites

* Python 3.10+
* [`exiftool`](https://exiftool.org/) 12.54+
  - For Ubuntu or Debian, do `sudo apt install libimage-exiftool-perl`
  - For other Linux distros, search `exiftool` using your package manager
  - For Mac or Windows, follow the instructions in website
  - For Windows, it is also available via [Scoop](https://scoop.sh/)

## Installation

To install the latest published version, do (preferrably in a [virtual environment](https://docs.python.org/3/library/venv.html)):

```
pip install apple-hdr-heic
```

Or if you want the latest development version, install using a Github archive link:

```
pip install https://github.com/johncf/apple-hdr-heic/archive/master.tar.gz
```

## Usage

### CLI Tool

```
apple-hdr-heic-decode input.heic output.png
apple-hdr-heic-decode input.heic output.heic -q 95
```

Lossless conversion:

```
apple-hdr-heic-decode input.heic output.avif -b 12 -y 444
```

Note: With 12-bit channels (in AVIF or HEIC), it's not truly lossless compared to 16-bit channels in PNG, but it's close enough.

### Library Usage

```py
from apple_hdr_heic import load_as_bt2100_pq, quantize_to_uint16

bt2100_pq = load_as_bt2100_pq("input.heic")
bt2100_pq_u16 = quantize_to_uint16(bt2100_pq)
cv2.imwrite("output.png", bt2100_pq_u16[:, :, ::-1])
```

Note: The output file `output.png` (in examples above) does not contain the necessary [cICP](https://en.wikipedia.org/wiki/Coding-independent_code_points) metadata that denotes it to have `bt2020` (9) color primaries and `smpte2084` (16) transfer characteristics. Therefore, all image viewers will display them incorrectly.

## Development

### Environment Set Up

Install [`uv`](https://github.com/astral-sh/uv).

Install `nox` using `uv`:

```
uv tool install nox
```

### Unit Testing

```
nox -s test
```

### Type Checking

```
nox -s typeck
```

### Linting

```
nox -s lint
```

### Formatting

```
nox -s style
```

### Building

```
uv tool install flit
flit build --no-use-vcs
```

## Miscellaneous Notes

### About 12-bit HEIC Files

Although this tool supports 12-bit HEIC output, it doesn't seem to be widely supported, even in Apple softwares.

### About AVIF Output

If you want to use a different AVIF encoder, first use this tool to produce a PNG file, then use [libavif](https://github.com/AOMediaCodec/libavif) with `--cicp` set to `9/16/9` to convert the PNG to AVIF:

```
avifenc -s 4 -j 4 --min 1 --max 56 -a end-usage=q -a cq-level=10 -a tune=ssim -a color:enable-qm=1 \
    -a color:enable-chroma-deltaq=1 -d 12 --cicp 9/16/9 output.png output.avif
```
