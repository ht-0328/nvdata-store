"""フレーム（:mod:`nvstore.frame`）を標準出力へ書く側。"""

from __future__ import annotations

from typing import BinaryIO

from .. import frame
from ..open_result import OpenResult


class FrameWriter:
    """1本のバイナリの出力に、種類ごとのフレームを書く。"""

    def __init__(self, stream: BinaryIO) -> None:
        self._stream = stream

    def open_result(self, result: OpenResult) -> None:
        self._write(frame.OPEN, frame.encode_json(result.to_dict()))

    def record(self, data: bytes) -> None:
        self._write(frame.RECORD, data)

    def file(self, name: str) -> None:
        self._write(frame.FILE, name.encode("utf-8"))

    def progress(self, done: int, total: int) -> None:
        self._write(frame.PROGRESS, frame.encode_json({"done": done, "total": total}))

    def log(self, text: str) -> None:
        self._write(frame.LOG, text.encode("utf-8"))

    def error(self, func: str, code: int, message: str, filename: str = "") -> None:
        self._write(frame.ERROR, frame.encode_json(
            {"func": func, "code": code, "message": message, "filename": filename}))

    def end(self) -> None:
        self._write(frame.END)

    def _write(self, kind: bytes, payload: bytes = b"") -> None:
        frame.write_frame(self._stream, kind, payload)
        self._stream.flush()
