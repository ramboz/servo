#!/usr/bin/env python3
"""Minimal, dependency-free PNG cropper for design-eval's native capture providers.

servo is standard-library only (ADR-0020), so there is no Pillow/ImageMagick to
crop a device screenshot down to the reference's logical frame. This module does
exactly one job: decode the PNG shape that mobile screencap tools emit
(``adb exec-out screencap`` / ``xcrun simctl io screenshot`` — 8-bit, truecolor
RGB/RGBA, non-interlaced), crop it by pixel insets, and re-encode a valid PNG.

It is deliberately NOT a general PNG library: interlaced, paletted, <8-bit, and
16-bit images raise ``PngCropError`` rather than be mis-handled. The crop output
is an unfrozen capture artifact (never hashed), so a re-encode that is
byte-different from a hypothetical Pillow output is irrelevant — only the pixels
matter, and those are preserved exactly (lossless inflate → crop → deflate).

Python 3.9+ standard library only.
"""
from __future__ import annotations

import struct
import zlib

_SIG = b"\x89PNG\r\n\x1a\n"
# color_type -> channels per pixel (only 8-bit truecolor variants supported)
_CHANNELS = {2: 3, 6: 4}


class PngCropError(Exception):
    """Raised for a malformed PNG or an unsupported/invalid crop."""


def _iter_chunks(data: bytes):
    if data[:8] != _SIG:
        raise PngCropError("not a PNG (bad signature)")
    off = 8
    n = len(data)
    while off + 8 <= n:
        (length,) = struct.unpack(">I", data[off:off + 4])
        ctype = data[off + 4:off + 8]
        start = off + 8
        end = start + length
        if end + 4 > n:
            raise PngCropError("truncated PNG chunk")
        yield ctype, data[start:end]
        off = end + 4  # skip the 4-byte CRC


def _unfilter(raw: bytes, width: int, height: int, bpp: int) -> bytearray:
    """Reverse PNG scanline filtering → raw pixel rows (no filter bytes)."""
    stride = width * bpp
    expected = (stride + 1) * height
    if len(raw) < expected:
        raise PngCropError("decompressed data shorter than the declared image")
    out = bytearray(stride * height)
    prev = bytearray(stride)
    pos = 0
    for row in range(height):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ftype == 0:
            pass
        elif ftype == 1:  # Sub
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ftype == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:  # Average
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:  # Paeth
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        else:
            raise PngCropError(f"unknown PNG filter type {ftype}")
        out[row * stride:(row + 1) * stride] = line
        prev = line
    return out


def _encode(pixels: bytes, width: int, height: int, bpp: int, color_type: int) -> bytes:
    stride = width * bpp
    raw = bytearray()
    for row in range(height):
        raw.append(0)  # filter: None
        raw.extend(pixels[row * stride:(row + 1) * stride])
    idat = zlib.compress(bytes(raw), 9)

    def chunk(ctype: bytes, body: bytes) -> bytes:
        return (struct.pack(">I", len(body)) + ctype + body
                + struct.pack(">I", zlib.crc32(ctype + body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return _SIG + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def crop_png(data: bytes, *, top: int = 0, bottom: int = 0,
             left: int = 0, right: int = 0) -> bytes:
    """Crop ``data`` (PNG bytes) by pixel insets and return new PNG bytes.

    Raises ``PngCropError`` for an unsupported PNG, negative insets, or a crop
    that leaves no pixels (``top+bottom >= height`` or ``left+right >= width``).
    """
    for name, v in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        if v < 0:
            raise PngCropError(f"crop {name} must be >= 0, got {v}")

    ihdr = None
    idat = bytearray()
    for ctype, body in _iter_chunks(data):
        if ctype == b"IHDR":
            ihdr = body
        elif ctype == b"IDAT":
            idat.extend(body)
        elif ctype == b"IEND":
            break
    if ihdr is None:
        raise PngCropError("PNG has no IHDR")

    width, height, bit_depth, color_type, comp, filt, interlace = struct.unpack(
        ">IIBBBBB", ihdr)
    if bit_depth != 8 or color_type not in _CHANNELS or interlace != 0:
        raise PngCropError(
            f"unsupported PNG (bit_depth={bit_depth}, color_type={color_type}, "
            f"interlace={interlace}); expected 8-bit truecolor non-interlaced")
    bpp = _CHANNELS[color_type]

    new_w = width - left - right
    new_h = height - top - bottom
    if new_w <= 0 or new_h <= 0:
        raise PngCropError(
            f"crop leaves no pixels: {width}x{height} with insets "
            f"top={top} bottom={bottom} left={left} right={right}")

    pixels = _unfilter(zlib.decompress(bytes(idat)), width, height, bpp)
    stride = width * bpp
    out = bytearray(new_w * bpp * new_h)
    row_bytes = new_w * bpp
    for r in range(new_h):
        src = (r + top) * stride + left * bpp
        out[r * row_bytes:(r + 1) * row_bytes] = pixels[src:src + row_bytes]
    return _encode(bytes(out), new_w, new_h, bpp, color_type)


def png_dimensions(data: bytes) -> tuple[int, int]:
    """(width, height) from a PNG's IHDR — a cheap read for tests/callers."""
    for ctype, body in _iter_chunks(data):
        if ctype == b"IHDR":
            w, h = struct.unpack(">II", body[:8])
            return w, h
    raise PngCropError("PNG has no IHDR")
