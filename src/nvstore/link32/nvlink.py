"""NV-Link（COM: ``NVDTLabLib.NVLink``）の薄いラッパ。**32bit でしか動かない。**

呼び出しの順番は JV-Link と同じ（JV-Link インターフェース仕様書 4.9.0.1）:

    NVInit → NVOpen / NVRTOpen → (NVStatus でDL進捗) → NVGets を EOF まで → NVClose

NVGets は 1 呼び出しで 1 レコード分の **bytes** を返す。固定長レコードを
バイト位置で切り出すため、str ではなく bytes のまま扱う。
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Iterator

from ..open_result import NO_DATA, OpenResult
from .broken_file_error import BROKEN_FILE_CODES, BrokenFileError
from .nvlink_error import NVLinkError

__all__ = ["NVLink"]

#: NVGets の戻り値のうち、レコード以外を表すもの。
_GETS_EOF = 0
_GETS_NEXT_FILE = -1
_GETS_DOWNLOADING = -3


class NVLink:
    """NV-Link COM オブジェクトのラッパ。使い終えたら ``dispose`` で解放する。"""

    PROGID = "NVDTLabLib.NVLink"
    #: NVGets に伝えるバッファの大きさ。最長レコード(H6: 102,890バイト)より大きくする。
    BUFFER_SIZE = 200_000

    def __init__(self, sid: str = "UNKNOWN") -> None:
        import pythoncom  # noqa: F401  （COM を使うスレッドで初期化しておく）
        import win32com.client

        pythoncom.CoInitialize()
        try:
            self._com = win32com.client.Dispatch(self.PROGID)
        except Exception:
            pythoncom.CoUninitialize()
            raise
        self.sid = sid
        self._opened = False
        self._disposed = False

    # ------------------------------------------------------------------ 基本
    def init(self) -> None:
        """NVInit。他のメソッドより先に必ず 1 回呼ぶ。"""
        code = int(self._com.NVInit(self.sid))
        if code != 0:
            raise NVLinkError("NVInit", code)

    def set_ui_properties(self) -> None:
        """UmaConn の設定画面（利用キーの登録）を開く。閉じるまで戻らない。"""
        self._com.NVSetUIProperties()

    def info(self) -> dict[str, Any]:
        """利用キーの登録の有無・保存先・バージョン。キーそのものは返さない。"""
        return {
            "service_key_registered": bool(str(self._com.m_servicekey or "").strip()),
            "save_path": str(self._com.m_savepath or ""),
            "version": str(self._com.m_NVLinkVersion or ""),
        }

    def close(self) -> None:
        if self._opened:
            try:
                self._com.NVClose()
            finally:
                self._opened = False

    def dispose(self) -> None:
        """このインスタンスを使い終えたとき、COM を作ったスレッドで解放する。"""
        if self._disposed:
            return
        try:
            self.close()
        finally:
            import pythoncom

            self._com = None
            self._disposed = True
            pythoncom.CoUninitialize()

    def file_delete(self, filename: str) -> None:
        code = int(self._com.NVFiledelete(filename))
        if code != 0:
            raise NVLinkError("NVFiledelete", code)

    def empty_files(self) -> list[str]:
        """保存パスにある、大きさ0のファイルの名前。

        NVGets が -402（ファイルサイズ＝0）を返したのにファイル名を返さないとき、
        消すべきファイルをここから探す。
        """
        root = Path(str(self._com.m_savepath or ""))
        if not root.is_dir():
            return []
        return sorted(f.name for f in root.rglob("*.nvd") if f.stat().st_size == 0)

    # ------------------------------------------------------------------ 取得
    def open(self, dataspec: str, fromtime: str, option: int = 1) -> OpenResult:
        """蓄積系データの取得要求（NVOpen）。

        option は 1:通常 2:今週 3:セットアップ 4:ダイアログ無しセットアップ。
        戻り値 -1（該当データ無し）は例外にせず、そのまま結果に入れて返す。
        """
        returned = self._com.NVOpen(dataspec, fromtime, int(option), 0, 0, "")
        code = int(returned[0]) if isinstance(returned, (list, tuple)) else int(returned)
        if code == NO_DATA:
            self._opened = True  # 該当データ無しでも NVClose は必要
            return OpenResult(code=NO_DATA)
        if code != 0:
            raise NVLinkError("NVOpen", code)
        self._opened = True
        return OpenResult(
            code=0,
            read_count=int(returned[1] or 0),
            download_count=int(returned[2] or 0),
            last_file_timestamp=str(returned[3] or ""),
        )

    def rt_open(self, dataspec: str, key: str) -> OpenResult:
        """速報系データの取得要求（NVRTOpen）。該当データが無ければ code=-1 で返す。"""
        code = int(self._com.NVRTOpen(dataspec, key))
        if code == NO_DATA:
            self._opened = True
            return OpenResult(code=NO_DATA)
        if code != 0:
            raise NVLinkError("NVRTOpen", code)
        self._opened = True
        return OpenResult(code=0, read_count=1)

    def status(self) -> int:
        """ダウンロード済みファイル数（NVStatus）。"""
        code = int(self._com.NVStatus())
        if code < 0:
            raise NVLinkError("NVStatus", code)
        return code

    def gets(self) -> tuple[int, bytes, str]:
        """NVGets を 1 回呼ぶ。戻り値は (コード, データ, ファイル名)。

        コードは >0:読み込んだバイト数 / 0:EOF / -1:ファイル切り替わり / -3:ダウンロード中。
        バッファは空で渡す。NV-Link は渡されたバッファを解放せず自分で確保した
        バイト配列に差し替えて返すので、大きなバッファを渡すと呼ぶたびに残る。
        """
        returned, memory, filename = self._com.NVGets(bytearray(), self.BUFFER_SIZE, bytearray())
        code = int(returned)
        data = memory.tobytes()[:code] if code > 0 and memory is not None else b""
        return code, data, str(filename or "")

    def wait_download(
        self,
        result: OpenResult,
        on_progress: Callable[[int, int], None] | None = None,
        interval: float = 0.5,
    ) -> None:
        """ダウンロード完了まで NVStatus を監視する。"""
        if result.download_count <= 0:
            return
        while True:
            done = self.status()
            if on_progress:
                on_progress(done, result.download_count)
            if done >= result.download_count:
                return
            time.sleep(interval)

    def records(
        self,
        on_file: Callable[[str], None] | None = None,
        retry_interval: float = 1.0,
    ) -> Iterator[bytes]:
        """EOF まで NVGets を繰り返し、1 レコードずつ返すイテレータ。"""
        while True:
            code, data, filename = self.gets()
            if code > 0:
                yield data
            elif code == _GETS_NEXT_FILE:
                # ファイル切り替わり。エラーではないので読み込みを続ける。
                if on_file:
                    on_file(filename)
            elif code == _GETS_DOWNLOADING:
                # 読み出そうとするファイルがまだダウンロード中。
                time.sleep(retry_interval)
            elif code == _GETS_EOF:
                return
            elif code in BROKEN_FILE_CODES:
                raise BrokenFileError(code, filename)
            else:
                raise NVLinkError("NVGets", code)
