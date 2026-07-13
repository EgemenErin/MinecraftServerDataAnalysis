"""Minimal Minecraft NBT reader (gzip/zlib aware, no external deps).

Only implements enough of the NBT spec to walk player .dat files and pull
inventory/enchantment data. Strings are decoded as UTF-8 (item ids and
enchant ids are ASCII), which is close enough to Java's modified UTF-8 for
this use case.
"""

from __future__ import annotations

import gzip
import struct
import zlib
from pathlib import Path

TAG_END = 0
TAG_BYTE = 1
TAG_SHORT = 2
TAG_INT = 3
TAG_LONG = 4
TAG_FLOAT = 5
TAG_DOUBLE = 6
TAG_BYTE_ARRAY = 7
TAG_STRING = 8
TAG_LIST = 9
TAG_COMPOUND = 10
TAG_INT_ARRAY = 11
TAG_LONG_ARRAY = 12


class _Reader:
    __slots__ = ("d", "i")

    def __init__(self, data: bytes) -> None:
        self.d = data
        self.i = 0

    def _take(self, n: int) -> bytes:
        chunk = self.d[self.i : self.i + n]
        self.i += n
        return chunk

    def u1(self) -> int:
        v = self.d[self.i]
        self.i += 1
        return v

    def _unpack(self, fmt: str, size: int):
        v = struct.unpack_from(fmt, self.d, self.i)[0]
        self.i += size
        return v

    def string(self) -> str:
        length = self._unpack(">H", 2)
        return self._take(length).decode("utf-8", "replace")

    def payload(self, tag: int):
        if tag == TAG_BYTE:
            return self._unpack(">b", 1)
        if tag == TAG_SHORT:
            return self._unpack(">h", 2)
        if tag == TAG_INT:
            return self._unpack(">i", 4)
        if tag == TAG_LONG:
            return self._unpack(">q", 8)
        if tag == TAG_FLOAT:
            return self._unpack(">f", 4)
        if tag == TAG_DOUBLE:
            return self._unpack(">d", 8)
        if tag == TAG_BYTE_ARRAY:
            length = self._unpack(">i", 4)
            return list(self._take(length))
        if tag == TAG_STRING:
            return self.string()
        if tag == TAG_LIST:
            item_type = self.u1()
            length = self._unpack(">i", 4)
            if item_type == TAG_END:
                return []
            return [self.payload(item_type) for _ in range(length)]
        if tag == TAG_COMPOUND:
            out: dict = {}
            while True:
                child = self.u1()
                if child == TAG_END:
                    break
                name = self.string()
                out[name] = self.payload(child)
            return out
        if tag == TAG_INT_ARRAY:
            length = self._unpack(">i", 4)
            return [self._unpack(">i", 4) for _ in range(length)]
        if tag == TAG_LONG_ARRAY:
            length = self._unpack(">i", 4)
            return [self._unpack(">q", 8) for _ in range(length)]
        raise ValueError(f"Unknown NBT tag id: {tag}")


def parse_nbt_bytes(data: bytes) -> dict:
    reader = _Reader(data)
    tag = reader.u1()
    if tag != TAG_COMPOUND:
        return {}
    reader.string()  # root name (usually empty)
    return reader.payload(TAG_COMPOUND)


def _decompress(raw: bytes) -> bytes:
    if raw[:2] == b"\x1f\x8b":
        return gzip.decompress(raw)
    if raw[:1] == b"\x78":  # zlib
        try:
            return zlib.decompress(raw)
        except zlib.error:
            return raw
    return raw


def read_nbt_file(path: str | Path) -> dict:
    raw = Path(path).read_bytes()
    return parse_nbt_bytes(_decompress(raw))
