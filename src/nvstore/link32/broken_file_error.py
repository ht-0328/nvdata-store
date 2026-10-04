"""保存パスのファイルが壊れていて読めないときの例外。"""

from __future__ import annotations

from .nvlink_error import NVLinkError

#: NVGets の戻り値のうち、保存パスのファイルが壊れていることを表すもの。
#: -402: ファイルサイズが0 / -403: データ内容が異常。
BROKEN_FILE_CODES = (-402, -403)


class BrokenFileError(NVLinkError):
    """ファイルを消して（NVFiledelete）、直前の NVOpen からやり直す。

    ``filename`` はそのファイル名。NV-Link が名前を返さないときは空。
    """

    def __init__(self, code: int, filename: str, message: str = "") -> None:
        super().__init__("NVGets", code, message)
        self.filename = filename
