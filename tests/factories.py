"""Shared test data factories."""

import base64 as _base64
import struct as _struct
import zlib as _zlib


def _make_png() -> bytes:
    """Generate a minimal valid 1×1 white PNG for use in tests."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = _zlib.crc32(tag + data) & 0xFFFFFFFF
        return _struct.pack(">I", len(data)) + tag + data + _struct.pack(">I", crc)

    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", _struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", _zlib.compress(b"\x00\xff\xff\xff"))
        + _chunk(b"IEND", b"")
    )


FAKE_PNG: bytes = _make_png()
FAKE_LOGO: bytes = FAKE_PNG
FAKE_SIG_B64: str = _base64.b64encode(FAKE_PNG).decode()
