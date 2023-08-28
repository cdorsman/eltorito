#!/usr/bin/python3
"""
Extract El Torito image from a bootable CD (or image).

Reference:
https://userpages.uni-koblenz.de/~krienke/ftp/noarch/geteltorito/
https://en.wikipedia.org/wiki/El_Torito_(CD-ROM_standard)
"""
import argparse
import os
import struct
import sys
import io
import typing

V_SECTOR_SIZE = 512
SECTOR_SIZE = 2048


class DetailHandler():

    def __init__(self, stdout: typing.TextIO = sys.stdout):
        self._stdout = stdout

    def set(self, key: str, value: object) -> None:
        if self._stdout is not None:
            self._stdout.write("- {key} -> {value}\n".format(key=key,
                                                             value=value))
        setattr(self, key, value)

    def get(self, key: str) -> object:
        return getattr(self, key)


class ElToritoError(Exception):

    def __init__(self, message: str):
        self.message = message


def _get_sector(number: int, count: int, handle: io.IOBase) -> bytes:
    """Get a sector."""
    handle.seek(number * SECTOR_SIZE, 0)
    sector: bytes = handle.read(V_SECTOR_SIZE * count)
    if len(sector) != V_SECTOR_SIZE * count:
        raise ElToritoError("invalid sector read")
    return sector


def extract(input_stream: io.IOBase, handler: DetailHandler) -> (bytes):
    """Extract image."""
    if input_stream is None or handler is None:
        raise ElToritoError(
            "invalid arguments for extraction, all inputs must be set")
    sector = _get_sector(17, 1, input_stream)
    # we only need the first section of this segment
    segment = struct.unpack("<B5sB32s32sL", sector[0:75])
    handler.set("iso", segment[1].decode("ascii"))
    handler.set("vers", segment[2])
    spec = segment[3].decode("ascii").strip()
    handler.set(
        "spec",
        "".join([x for x in spec if (x >= 'A' and x <= 'Z') or x == ' ']))
    # 4 is unused
    handler.set("partition", segment[5])
    if handler.get("iso") != "CD001" or str(
            handler.get("spec")).strip() != "EL TORITO SPECIFICATION":
        raise ElToritoError("this is not a bootable cd-image")
    sector = _get_sector(int(str(handler.get("partition"))), 1, input_stream)
    segment = struct.unpack("<BBH24sHBB", sector[0:32])
    header = segment[0]
    handler.set("platform", segment[1])
    # skip 2
    handler.set("manufacturer", segment[3].decode("ascii"))
    # skip 4
    five = segment[5]
    aa = segment[6]
    if header != 1 or five != int("0x55", 16) or aa != int("0xaa", 16):
        raise ElToritoError("invalid validation entry")
    platform_string = "unknown"
    platform = int(str(handler.get("platform")))
    if platform == 0:
        platform_string = "x86"
    elif platform == 1:
        platform_string = "PowerPC"
    elif platform == 2:
        platform_string = "Mac"
    handler.set("platform_string", platform_string)
    segment = struct.unpack("<BBHBBHLB", sector[32:45])
    boot = segment[0]
    handler.set("media", segment[1])
    load = segment[2]
    sys = segment[3]
    # skip 4
    cnt = segment[5]
    start = segment[6]
    # skip 7
    if boot != int("0x88", 16):
        raise ElToritoError("boot indicator is not 0x88, not bootable")
    media_type = "unknown"
    count = 0
    media = int(str(handler.get("media")))
    if media == 0:
        media_type = "no emulation"
        count = 0
    elif media == 1:
        media_type = "1.2meg floppy"
        count = int(1200 * 1024 / V_SECTOR_SIZE)
    elif media == 2:
        media_type = "1.44meg floppy"
        count = int(1440 * 1024 / V_SECTOR_SIZE)
    elif media == 3:
        media_type = "2.88meg floppy"
        count = int(2880 * 1024 / V_SECTOR_SIZE)
    elif media == 4:
        media_type = "harddisk"
        mbr = _get_sector(start, 1, input_stream)
        part = mbr[446:462]
        segment = struct.unpack("<8sLL", part)
        # skip 0
        first = segment[1]
        size = segment[2]
        count = first + size
    if count == 0:
        count = cnt
    handler.set("media_type", media_type)
    handler.set("sector_size", V_SECTOR_SIZE)
    handler.set("sector_count", count)
    handler.set("sector_start", start)
    return _get_sector(start, count, input_stream)


def main() -> None:
    """Main entry."""
    parser = argparse.ArgumentParser("el torito image extraction")
    parser.add_argument("input", help="cd image to read")
    parser.add_argument("output", help="output file")
    args = parser.parse_args()
    if not os.path.exists(args.input):
        print("unable to find {}".format(args.input))
        exit(1)
    if os.path.exists(args.output):
        print("output file already exists {}".format(args.output))
        exit(1)
    try:
        with open(args.input, "rb") as f:
            b = extract(f, DetailHandler())
            with open(args.output, "wb") as o:
                o.write(b)
        print("image written successfully")
    except ElToritoError as e:
        print("unable to extract image, eltorito format error")
        print(e)


if __name__ == "__main__":
    main()
