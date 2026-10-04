"""32bit の取得プロセスと 64bit の本体をつなぐ、1本のパイプに流すフレームの形。

NV-Link は 32bit の COM でしか作れず、DuckDB は 64bit でしか入らない。そこで取得は
別プロセス（:mod:`nvstore.link32`）で行い、読んだレコードを標準出力の1本のパイプで
本体に渡す。パイプには文字とバイト列が混ざるので、**種類1バイト＋長さ4バイト＋中身**
の固定の枠（フレーム）に揃えて流す。2本目のパイプ（標準エラー）を同時に読まずに済み、
片方が詰まって止まることがない。

このモジュールは両側から使うので、標準ライブラリしか使わない。
"""

from __future__ import annotations

import json
import struct
from typing import Any, BinaryIO, Iterator

__all__ = [
    "END", "ERROR", "FILE", "LOG", "OPEN", "PROGRESS", "RECORD",
    "decode_json", "encode_json", "read_frame", "read_frames", "write_frame",
]

#: 種類1バイト（英字）＋中身の長さ4バイト（リトルエンディアン）。
HEADER = struct.Struct("<cI")

#: NVOpen / NVRTOpen の結果。中身は JSON（:class:`nvstore.open_result.OpenResult`）。
OPEN = b"O"
#: 1レコード。中身はレコードのバイト列そのもの。
RECORD = b"R"
#: 読んでいるファイルが切り替わった。中身はファイル名（UTF-8）。
FILE = b"F"
#: ダウンロードの進み具合。中身は JSON ``{"done": n, "total": n}``。
PROGRESS = b"P"
#: 本体のログに出す文章。中身は UTF-8。
LOG = b"L"
#: NV-Link が失敗した。中身は JSON ``{"func", "code", "message", "filename"}``。
ERROR = b"E"
#: 読み終えた。中身は空。これが来ずにパイプが閉じたら、取得プロセスが落ちたとみなす。
END = b"Z"


def write_frame(stream: BinaryIO, kind: bytes, payload: bytes = b"") -> None:
    stream.write(HEADER.pack(kind, len(payload)))
    stream.write(payload)


def read_frame(stream: BinaryIO) -> tuple[bytes, bytes] | None:
    """1フレーム読む。パイプが閉じていれば None。途中で切れていれば EOFError。"""
    header = stream.read(HEADER.size)
    if not header:
        return None
    if len(header) < HEADER.size:
        raise EOFError("取得プロセスからのデータが途中で切れました")
    kind, length = HEADER.unpack(header)
    payload = stream.read(length)
    if len(payload) < length:
        raise EOFError("取得プロセスからのデータが途中で切れました")
    return kind, payload


def read_frames(stream: BinaryIO) -> Iterator[tuple[bytes, bytes]]:
    """パイプが閉じるまでフレームを返す。"""
    while True:
        frame = read_frame(stream)
        if frame is None:
            return
        yield frame


def encode_json(data: dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def decode_json(payload: bytes) -> dict[str, Any]:
    return json.loads(payload.decode("utf-8"))
