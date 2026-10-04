"""開催日の速報系データを、まとめて DuckDB に入れる。

蓄積系（:mod:`nvstore.sync`）に入ってくるのは、確定したあとのデータだけ。発走前に要る
オッズ・馬体重・天候と馬場状態・出走取消は、速報系（``NVRTOpen``）でしか取れない。
ここでは **開催日を1つ指定して、その日の速報を全部取る**。レースや馬で絞り込む機能は持たない。

提供の単位はデータ種別ごとに決まっている（docs/03-dataspecs.md）。

- 開催日単位（キーは ``YYYYMMDD``）: 速報レース情報・速報開催情報・速報馬体重・速報重勝式
- レース毎（キーは ``YYYYMMDDJJKKHHRR``）: 速報オッズ。その日のレースは、先に取った速報レース情報
  （無ければ蓄積系の ``ra``）から拾う

まだ発表されていないデータは「該当データなし」で、エラーにはしない。同じ日を何度取り直してもよい
（同じ鍵の行は新しい版に置き換わり、オッズは発表時刻ごとに行が増える）。
"""

from __future__ import annotations

import time
from pathlib import Path
from threading import Event
from typing import Any, Callable

from jvstore.realtime import RealtimeResult, parse_day
from jvstore.store import DuckStore
from jvstore.sync import check_cancel

from .layouts import load_layouts
from .link32.nvlink_error import NVLinkError
from .link_process import LinkProcess

__all__ = ["DAY_DATASPECS", "RACE_DATASPECS", "RealtimeResult", "fetch_day", "parse_day"]

#: 開催日単位で取る速報。先頭の速報レース情報が、その日のレースの一覧（ra）も運んでくる。
DAY_DATASPECS: tuple[tuple[str, str], ...] = (
    ("0B15", "速報レース情報（出馬表・成績・払戻）"),
    ("0B14", "速報開催情報（天候・馬場状態、出走取消）"),
    ("0B11", "速報馬体重"),
    ("0B51", "速報重勝式"),
)
#: レース毎に取る速報。全賭式（単勝〜3連単。枠単発売場は枠単も）のオッズ。
RACE_DATASPECS: tuple[tuple[str, str], ...] = (
    ("0B30", "速報オッズ（全賭式）"),
)


def fetch_day(
    db_path: Path,
    day: str,
    *,
    log: Callable[[str], None] = print,
    stop: Event | None = None,
    layouts=None,
    link_factory: Callable[[], Any] | None = None,
) -> RealtimeResult:
    """開催日 ``day`` の速報を全部取り込む。途中で失敗した種別やレースがあっても、残りは続ける。"""
    key = parse_day(day)
    layouts = layouts or load_layouts()
    factory = link_factory or LinkProcess
    summary = RealtimeResult()
    log(f"{key[:4]}-{key[4:6]}-{key[6:]} の速報を取得します")
    log(f"保存先: {db_path.resolve()}")

    store = DuckStore(db_path, layouts)
    try:
        for dataspec, title in DAY_DATASPECS:
            check_cancel(stop)
            _fetch_one(factory(), store, dataspec, key, summary, log=log, label=f"{dataspec} {title}")
        races = _race_keys(store, key)
        summary.races = len(races)
        for dataspec, title in RACE_DATASPECS:
            log("")
            log(f"{dataspec} {title} — {len(races)} レース")
            if not races:
                log("  その日のレースが DB にありません（出馬表の発表前か、開催の無い日）")
            for race_key in races:
                check_cancel(stop)
                _fetch_one(factory(), store, dataspec, race_key, summary, log=log, label="", quiet=True)
            log(f"  {summary.records.get(dataspec, 0):,} レコード")
    finally:
        store.close()
    return summary


def _fetch_one(
    link: Any,
    store: DuckStore,
    dataspec: str,
    key: str,
    summary: RealtimeResult,
    *,
    log: Callable[[str], None],
    label: str,
    quiet: bool = False,
) -> None:
    """1つのデータ種別・1つのキーぶんを取り込む。失敗しても呼び手は次へ進む。"""
    if label:
        log("")
        log(label)
    started = time.time()
    written = 0
    try:
        if not link.rt_open(dataspec, key):
            if not quiet:
                log("  該当データなし（まだ発表されていないか、提供期間を過ぎています）")
            if dataspec not in summary.empty:
                summary.empty.append(dataspec)
            return
        for data in link.records():
            store.write(data)
            written += 1
        store.flush()
    except NVLinkError as error:
        log(f"  取得できませんでした（{dataspec} {key}）: {error}")
        if dataspec not in summary.failed:
            summary.failed.append(dataspec)
        return
    finally:
        link.close()
    summary.records[dataspec] = summary.records.get(dataspec, 0) + written
    if not quiet:
        log(f"  {written:,} レコード / {time.time() - started:.1f} 秒")


def _race_keys(store: DuckStore, day: str) -> list[str]:
    """その日の全レースの要求キー（``YYYYMMDDJJKKHHRR``）。``ra`` がまだ無ければ空。"""
    exists = store.con.execute(
        "SELECT count(*) FROM duckdb_tables() WHERE table_name = 'ra'"
    ).fetchone()[0]
    if not exists:
        return []
    rows = store.con.execute(
        'SELECT DISTINCT "開催年" || "開催月日" || "競馬場コード" || "開催回[第N回]" || "開催日目[N日目]" || "レース番号" '
        'FROM ra WHERE "開催年" = ? AND "開催月日" = ? ORDER BY 1',
        [day[:4], day[4:]],
    ).fetchall()
    return [key for (key,) in rows]
