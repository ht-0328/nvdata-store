"""試験で使う部品。偽の NV-Link と、レイアウトどおりの長さのレコードを作る道具。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from nvstore.layouts import load_layouts
from nvstore.open_result import NO_DATA, OpenResult

LAYOUTS = load_layouts()

#: 試験用のレースキー（開催年・開催月日・競馬場コード・回・日目・レース番号）。大井 2026-10-04 1R。
RACE = {"開催年": "2026", "開催月日": "1004", "競馬場コード": "44", "開催回[第N回]": "10",
        "開催日目[N日目]": "01", "レース番号": "01"}


def make_record(record_id: str, **values: str) -> bytes:
    """レイアウトどおりの長さで、指定した項目だけ埋めたレコード。ほかは空白。"""
    layout = LAYOUTS.get(record_id)
    buffer = bytearray(b" " * layout.length)
    buffer[-2:] = b"\r\n"
    for name, value in {"レコード種別ID": record_id, **values}.items():
        item = next(i for i in layout.items if i.name == name)
        encoded = value.encode("cp932")
        buffer[item.offset:item.offset + len(encoded)] = encoded
    return bytes(buffer)


@dataclass
class FakeLink:
    """呼ばれた内容を記録し、決めたレコードを返すだけの NV-Link（LinkProcess の代わり）。"""

    records_by_spec: dict[str, list[bytes]] = field(default_factory=dict)
    timestamps: dict[str, str] = field(default_factory=dict)
    errors: dict[str, Exception] = field(default_factory=dict)
    calls: list[tuple] = field(default_factory=list)
    closed: int = 0
    deleted: list[str] = field(default_factory=list)
    empty: list[str] = field(default_factory=list)
    _current: str = ""

    def open(self, dataspec: str, fromtime: str, option: int) -> OpenResult:
        self.calls.append(("open", dataspec, fromtime, option))
        self._current = dataspec
        if dataspec in self.errors and not isinstance(self.errors[dataspec], _DuringRead):
            raise self.errors[dataspec]
        if dataspec not in self.records_by_spec:
            return OpenResult(code=NO_DATA)
        return OpenResult(code=0, read_count=len(self.records_by_spec[dataspec]) or 1,
                          last_file_timestamp=self.timestamps.get(dataspec, "20261004231021"))

    def rt_open(self, dataspec: str, key: str) -> bool:
        self.calls.append(("rt_open", dataspec, key))
        self._current = f"{dataspec}:{key}"
        if self._current in self.errors and not isinstance(self.errors[self._current], _DuringRead):
            raise self.errors[self._current]
        return self._current in self.records_by_spec or dataspec in self.records_by_spec

    def records(self, on_file=None, on_progress=None):
        error = self.errors.get(self._current)
        if isinstance(error, _DuringRead):
            raise error.error
        if on_file:
            on_file("FAKE.nvd")
        yield from self.records_by_spec.get(self._current) or self.records_by_spec.get(self._current.split(":")[0], [])

    def close(self) -> None:
        self.closed += 1

    def file_delete(self, filename: str) -> None:
        self.deleted.append(filename)

    def empty_files(self) -> list[str]:
        return list(self.empty)


@dataclass
class _DuringRead:
    """開くのは成功して、読んでいる途中で起きるエラー。"""

    error: Exception


def during_read(error: Exception) -> _DuringRead:
    return _DuringRead(error)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "nvdata.duckdb"
