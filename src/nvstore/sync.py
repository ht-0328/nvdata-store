"""過去N年ぶんの蓄積系データを、まとめて DuckDB に入れる。

このモジュールが取得の本体で、コマンドラインも画面もここを呼ぶ。
**選ぶのは「何年ぶん」と「どのデータ種別か」だけ**にしてある。
レースや馬で絞り込む機能は持たない。絞り込みは読む側（keiba-yosou）の責務。

データ種別ごとに、初回はセットアップ（option=4）、2回目以降は前回の続き（option=1）。
どこまで取ったかは DuckDB の ``_meta`` に持つので、状態ファイルは要らない。

**セットアップは年ごとに区切れない。** NV-Link は読み出し終了時刻を無視するので、
開始時刻から今までを一度に開く（2005年からなら約10万ファイル）。ダウンロードの完了を
待ちながら読む。

**DIFF は NB（生産者マスタ地方）だけを取り込む。** DIFF に入ってくる NU は DIFN より短い旧サイズで、
血統登録番号の体系も違う。同じ表に混ぜると壊れた行が入るので、DIFF からはほかの種別に無い NB だけを取る。
"""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from threading import Event
from typing import Any, Callable, Sequence

from jvstore.record import record_id_of
from jvstore.store import DuckStore
from jvstore.sync import Cancelled, SyncResult, check_cancel

from .layouts import load_layouts
from .link32.broken_file_error import BrokenFileError
from .link32.nvlink_error import NVLinkError
from .link_process import LinkProcess
from .open_result import NO_DATA, OpenResult

__all__ = ["RECORD_FILTER", "SYNC_DATASPECS", "TITLES", "Cancelled", "SyncResult", "start_time", "sync"]

#: 過去N年ぶんを取るときに回すデータ種別。この4つで地方競馬DATA の蓄積系の表を覆う
#: （docs/03-dataspecs.md）。
SYNC_DATASPECS: tuple[tuple[str, str], ...] = (
    ("RACE", "レース情報（出馬表・成績・払戻・票数・確定オッズ・枠単・重勝式）"),
    ("DIFN", "マスタ（競走馬地方・騎手・調教師・馬主）"),
    ("SNAP", "出走別着度数地方"),
    ("DIFF", "生産者マスタ地方（NB だけを取る）"),
)

TITLES = dict(SYNC_DATASPECS)

#: データ種別から取り込むレコード種別を限る。載っていない種別は全部取り込む。
RECORD_FILTER: dict[str, frozenset[str]] = {"DIFF": frozenset({"NB"})}

#: ``_meta`` に前回の続きの時刻を残すときのキーの接頭辞。
_META_PREFIX = "sync:"

#: NVOpen の option。1:通常（前回の続き） 4:ダイアログ無しセットアップ。
_OPTION_CONTINUE = 1
_OPTION_SETUP = 4

#: 地方競馬DATA の提供開始年。これより前は指定しない。
_FIRST_YEAR = 2005

#: 過去年数として受け付ける範囲（両端を含む）。
_MIN_YEARS = 1
_MAX_YEARS = 40

#: 壊れたファイルを消して開き直す回数の上限。
_MAX_REOPEN = 3

#: 途中経過を出すレコード件数の刻み。
_PROGRESS_EVERY = 50000

#: NV-Link の代わりになるもの（LinkProcess か、試験用の偽物）を作る関数。
LinkFactory = Callable[[], Any]


def start_time(years: int, today: date | None = None) -> str:
    """``NVOpen`` に渡す読み出し開始時刻。年の1月1日まで切り下げ、2005年より前にはしない。"""
    if not _MIN_YEARS <= years <= _MAX_YEARS:
        raise ValueError(f"過去年数は{_MIN_YEARS}〜{_MAX_YEARS}年で指定してください。")
    year = (today or date.today()).year - years
    return f"{max(_FIRST_YEAR, year):04d}0101000000"


def sync(
    db_path: Path,
    years: int = 10,
    dataspecs: Sequence[str] | None = None,
    *,
    log: Callable[[str], None] = print,
    stop: Event | None = None,
    layouts=None,
    link_factory: LinkFactory | None = None,
    dry_run: bool = False,
    force_setup: bool = False,
) -> SyncResult:
    """過去N年ぶんを取り込む。途中で失敗したデータ種別があっても、残りは続ける。"""
    layouts = layouts or load_layouts()
    specs = [name.upper() for name in (dataspecs or [name for name, _ in SYNC_DATASPECS])]
    start = start_time(years)
    factory = link_factory or LinkProcess
    summary = SyncResult()

    log(f"過去 {years} 年（{start[:4]}年1月1日以降）の蓄積系データを取得します")
    log(f"対象データ種別: {', '.join(specs)}")
    log(f"保存先: {db_path.resolve()}")

    store = DuckStore(db_path, layouts)
    try:
        for position, dataspec in enumerate(specs, 1):
            check_cancel(stop)
            fromtime, option = _resume_point(store, dataspec, start, force_setup)
            kind = "続きから" if option == _OPTION_CONTINUE else "セットアップ"
            log("")
            log(f"[{position}/{len(specs)}] {dataspec} {TITLES.get(dataspec, '')} — {kind} {fromtime}")
            timestamp = _sync_dataspec(
                factory, store, dataspec, fromtime, option, summary, log=log, stop=stop, dry_run=dry_run,
            )
            if timestamp is None:
                summary.failed.append(dataspec)
            elif not dry_run:
                _remember_progress(store, dataspec, timestamp)
    finally:
        summary.counts = store.counts()
        store.close()
    return summary


def _resume_point(store: DuckStore, dataspec: str, start: str, force_setup: bool) -> tuple[str, int]:
    """読み出し開始時刻と NVOpen の option。前回の続きが残っていればそこから、無ければセットアップ。"""
    saved = store.meta(_META_PREFIX + dataspec)
    if saved and not force_setup:
        return saved, _OPTION_CONTINUE
    return start, _OPTION_SETUP


def _sync_dataspec(
    factory: LinkFactory,
    store: DuckStore,
    dataspec: str,
    fromtime: str,
    option: int,
    summary: SyncResult,
    *,
    log: Callable[[str], None],
    stop: Event | None,
    dry_run: bool,
) -> str | None:
    """1データ種別ぶんを読み切る。最新ファイルの時刻を返し、失敗なら None。

    保存パスのファイルが壊れていたら、そのファイルを消して ``NVOpen`` からやり直す。
    消したファイルは開き直すときにダウンロードし直される。読み終えたレコードをもう一度書いても行は増えない。
    """
    for _ in range(_MAX_REOPEN):
        try:
            return _open_and_read(factory, store, dataspec, fromtime, option, summary, log=log, stop=stop, dry_run=dry_run)
        except BrokenFileError as error:
            log(f"  {error}")
            if not _delete_broken(factory(), error, log=log):
                return None
            log("  壊れたファイルを消しました。開き直してダウンロードし直します")
    log(f"  {_MAX_REOPEN}回開き直しても読めませんでした")
    return None


def _delete_broken(link: Any, error: BrokenFileError, *, log: Callable[[str], None]) -> bool:
    """壊れたファイルを消す。消すファイルが分からない・消せないなら False。"""
    names = [error.filename] if error.filename else link.empty_files()
    if not names:
        log("  壊れたファイルの名前が分からないので、消せませんでした")
        return False
    try:
        for name in names:
            log(f"  削除: {name}")
            link.file_delete(name)
    except NVLinkError as delete_error:
        log(f"  削除できませんでした: {delete_error}")
        return False
    return True


def _open_and_read(
    factory: LinkFactory,
    store: DuckStore,
    dataspec: str,
    fromtime: str,
    option: int,
    summary: SyncResult,
    *,
    log: Callable[[str], None],
    stop: Event | None,
    dry_run: bool,
) -> str | None:
    """``NVOpen`` して読み切る。壊れたファイルに当たったら BrokenFileError を投げる。"""
    link = factory()
    try:
        result = link.open(dataspec, fromtime, option)
    except NVLinkError as error:
        link.close()
        log(f"  取得できませんでした: {error}")
        return None
    try:
        if result.code == NO_DATA:
            log("  該当データなし")
            return ""
        log(f"  対象ファイル {result.read_count:,} 件 / 要ダウンロード {result.download_count:,} 件")
        if result.read_count > 0 and not dry_run:
            _read_records(link, store, dataspec, result, summary, log=log, stop=stop)
    except (Cancelled, BrokenFileError):
        raise
    except Exception as error:  # noqa: BLE001
        log(f"  読み込みに失敗しました: {error}")
        return None
    finally:
        link.close()
    return result.last_file_timestamp


def _read_records(
    link: Any,
    store: DuckStore,
    dataspec: str,
    result: OpenResult,
    summary: SyncResult,
    *,
    log: Callable[[str], None],
    stop: Event | None,
) -> None:
    """開いたぶんを読み切って書き込む。取り込まない種別は数えるだけで捨てる。"""
    allowed = RECORD_FILTER.get(dataspec)
    written = skipped = 0
    started = time.time()
    records = link.records(
        on_file=lambda name: log(f"  読込: {name}"),
        on_progress=lambda done, total: log(f"  ダウンロード {done:,}/{total:,}"),
    )
    for data in records:
        check_cancel(stop)
        if allowed is not None and record_id_of(data) not in allowed:
            skipped += 1
            continue
        store.write(data)
        written += 1
        if written % _PROGRESS_EVERY == 0:
            log(f"  {written:,} レコード ({time.time() - started:.0f}秒)")
    store.flush()
    summary.records += written
    note = f"（取り込まない種別 {skipped:,} 件を飛ばした）" if skipped else ""
    log(f"  {written:,} レコード / {time.time() - started:.1f} 秒{note}")


def _remember_progress(store: DuckStore, dataspec: str, timestamp: str) -> None:
    """次回の続きの起点を残す。タイムスタンプが取れないとき（該当データなし）は触らない。"""
    if timestamp:
        store.set_meta(_META_PREFIX + dataspec, timestamp)
