"""Strip untrusted EXIF while retaining orientation and compressed pixel data."""

import struct
import zlib
from io import BytesIO

from PIL import Image


def strip_exif(data: bytes, content_type: str) -> bytes:
    with Image.open(BytesIO(data)) as image:
        orientation = image.getexif().get(274)
    minimal = Image.Exif()
    if orientation in range(1, 9):
        minimal[274] = orientation
    exif = minimal.tobytes() if minimal else b""
    if content_type == "image/jpeg":
        output = bytearray(data[:2])
        if exif:
            output.extend(b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif)
        offset = 2
        while offset < len(data):
            start = offset
            while data[offset] == 255:
                offset += 1
            marker = data[offset]
            offset += 1
            if marker in {0xDA, 0xD9}:
                output.extend(data[start:])
                break
            length = struct.unpack(">H", data[offset : offset + 2])[0]
            end = offset + length
            if marker != 0xE1:  # EXIF and XMP APP1 are not business evidence.
                output.extend(data[start:end])
            offset = end
        return bytes(output)
    if content_type == "image/png":
        output = bytearray(data[:8])
        offset = 8
        while offset < len(data):
            length = struct.unpack(">I", data[offset : offset + 4])[0]
            kind = data[offset + 4 : offset + 8]
            end = offset + 12 + length
            if kind == b"eXIf":
                if exif:
                    payload = b"eXIf" + exif[6:]
                    output.extend(
                        struct.pack(">I", len(exif) - 6)
                        + payload
                        + struct.pack(">I", zlib.crc32(payload))
                    )
            else:
                output.extend(data[offset:end])
            offset = end
        return bytes(output)
    chunks = bytearray()
    offset = 12
    while offset < len(data):
        kind = data[offset : offset + 4]
        length = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
        payload = data[offset + 8 : offset + 8 + length]
        offset += 8 + length + length % 2
        if kind == b"EXIF":
            if not exif:
                continue
            payload = exif
        if kind == b"VP8X" and not exif:
            payload = bytes([payload[0] & ~8]) + payload[1:]
        chunks.extend(
            kind
            + struct.pack("<I", len(payload))
            + payload
            + (b"\x00" if len(payload) % 2 else b"")
        )
    return b"RIFF" + struct.pack("<I", len(chunks) + 4) + b"WEBP" + bytes(chunks)
