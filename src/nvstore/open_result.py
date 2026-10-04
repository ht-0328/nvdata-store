"""NVOpen / NVRTOpen の結果。32bit の取得プロセスと 64bit の本体の両方で使う。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

#: NVOpen / NVRTOpen が「該当データ無し」を表す戻り値。エラーにはしない。
NO_DATA = -1


@dataclass(slots=True)
class OpenResult:
    code: int
    """NVOpen / NVRTOpen の戻り値。0 なら読める。NO_DATA なら該当データ無し。"""
    read_count: int = 0
    """読み込み対象の全ファイル数。"""
    download_count: int = 0
    """うちサーバーからのダウンロードが必要なファイル数。"""
    last_file_timestamp: str = ""
    """対象ファイル中で最も新しいタイムスタンプ。次回 NVOpen の fromtime に使う。"""

    @property
    def has_data(self) -> bool:
        return self.code == 0 and self.read_count > 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OpenResult":
        return cls(
            code=int(data["code"]),
            read_count=int(data.get("read_count", 0)),
            download_count=int(data.get("download_count", 0)),
            last_file_timestamp=str(data.get("last_file_timestamp", "")),
        )
