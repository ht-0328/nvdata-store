"""NV-Link から読んだものを、フレームにして流す。

1回の起動で 1回の NVOpen（または NVRTOpen）だけを扱う。読み終えたらプロセスごと
終わるので、COM の中にたまるものが次の取得に持ち越されない。
"""

from __future__ import annotations

from ..open_result import OpenResult
from .broken_file_error import BrokenFileError
from .frame_writer import FrameWriter
from .nvlink import NVLink
from .nvlink_error import NVLinkError


class Streamer:
    """開いて、ダウンロードを待って、EOF まで読んで、フレームで流す。"""

    def __init__(self, link: NVLink, writer: FrameWriter) -> None:
        self._link = link
        self._writer = writer

    def historical(self, dataspec: str, fromtime: str, option: int) -> int:
        """蓄積系（NVOpen）。終了コードを返す（0: 正常）。"""
        return self._stream(lambda: self._link.open(dataspec, fromtime, option))

    def realtime(self, dataspec: str, key: str) -> int:
        """速報系（NVRTOpen）。終了コードを返す（0: 正常）。"""
        return self._stream(lambda: self._link.rt_open(dataspec, key))

    def _stream(self, open_link) -> int:
        try:
            result: OpenResult = open_link()
            self._writer.open_result(result)
            if result.has_data:
                self._link.wait_download(result, on_progress=self._writer.progress)
                for data in self._link.records(on_file=self._writer.file):
                    self._writer.record(data)
            self._writer.end()
            return 0
        except BrokenFileError as error:
            self._writer.error(error.func, error.code, str(error), error.filename)
            return 1
        except NVLinkError as error:
            self._writer.error(error.func, error.code, str(error))
            return 1
        finally:
            self._link.close()
