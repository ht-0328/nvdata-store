"""nvstore コマンドラインインターフェース。

    nvstore sync --years 10            過去N年ぶんの蓄積系データをまとめて取得する
    nvstore realtime --date 2026-10-04 開催日の速報（出馬表・成績・馬体重・天候馬場・取消・オッズ）をまとめて取得する
    nvstore fetch --dataspec RACE --from 20261001000000   蓄積系データ(NVOpen)を1回ぶん取得する（動作確認用）
    nvstore rt --dataspec 0B30 --key 2026100444100101   速報系データ(NVRTOpen)を1回ぶん取得する（動作確認用）
    nvstore setup                      UmaConn の設定画面（利用キー登録）を開く
    nvstore info                       利用キーの登録の有無・保存先・UmaConn のバージョン
    nvstore serve / panel              データ取得・管理画面 / その操作パネル

出力先は DuckDB（既定 nvdata.duckdb）。NV-Link は 32bit の取得プロセスで呼ぶ（:mod:`nvstore.link_process`）。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .layouts import load_layouts

#: 既定の保存先。中央の jvdata.duckdb とは別のファイルにする。
DEFAULT_DB = "nvdata.duckdb"

#: 画面のポート。jvdata-store（8766）と同時に開けるよう、1つずらす。
DEFAULT_PORT = 8767

#: 途中経過を出すレコード件数の刻み。
_PROGRESS_EVERY = 50000


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _link(args: argparse.Namespace):
    from .link_process import LinkProcess

    return LinkProcess(args.sid)


# --------------------------------------------------------------------- 取得
def cmd_sync(args: argparse.Namespace) -> int:
    """過去N年ぶんの蓄積系データを、種別を順に回してまとめて DuckDB へ入れる。本体は :mod:`nvstore.sync`。"""
    from .sync import SYNC_DATASPECS, sync

    specs = [name.strip().upper() for name in args.dataspec.split(",")] if args.dataspec else [n for n, _ in SYNC_DATASPECS]
    result = sync(
        Path(args.db), years=args.years, dataspecs=specs, log=_log, layouts=load_layouts(),
        link_factory=lambda: _link(args), dry_run=args.dry_run, force_setup=args.force_setup,
    )
    _log("")
    _log("--- テーブルごとの行数 ---")
    for table, count in result.counts.items():
        _log(f"  {table:<28} {count:>12,}")
    if result.failed:
        _log(f"取得できなかったデータ種別: {', '.join(result.failed)}")
        return 1
    return 0


def cmd_realtime(args: argparse.Namespace) -> int:
    """開催日の速報系データをまとめて DuckDB へ入れる。本体は :mod:`nvstore.realtime`。"""
    from datetime import date

    from .realtime import fetch_day, parse_day

    days = [parse_day(day) for day in (args.date or [date.today().isoformat()])]
    failed: list[str] = []
    for position, day in enumerate(days):
        if position:
            _log("")
        result = fetch_day(Path(args.db), day, log=_log, layouts=load_layouts(), link_factory=lambda: _link(args))
        failed += [f"{day} {dataspec}" for dataspec in result.failed]
    if failed:
        _log(f"取得できなかったデータ種別: {', '.join(failed)}")
        return 1
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    """蓄積系データを1回の NVOpen ぶん取り込む。種別や期間を指定して中身を確かめるためのもの。"""
    from .link32.nvlink_error import NVLinkError
    from .open_result import NO_DATA

    link = _link(args)
    try:
        _log(f"NVOpen dataspec={args.dataspec} fromtime={args.from_} option={args.option}")
        result = link.open(args.dataspec, args.from_, args.option)
        if result.code == NO_DATA:
            _log("該当データがありません。")
            return 0
        _log(f"対象ファイル {result.read_count:,} 件 / 要ダウンロード {result.download_count:,} 件"
             f" / 最新タイムスタンプ {result.last_file_timestamp or '-'}")
        if args.dry_run:
            return 0
        _store_records(args, link)
        return 0
    except NVLinkError as error:
        _log(str(error))
        return 1
    finally:
        link.close()


def cmd_rt(args: argparse.Namespace) -> int:
    """速報系データを1回の NVRTOpen ぶん取り込む。"""
    from .link32.nvlink_error import NVLinkError

    link = _link(args)
    try:
        _log(f"NVRTOpen dataspec={args.dataspec} key={args.key}")
        if not link.rt_open(args.dataspec, args.key):
            _log("該当データがありません（まだ発表されていないか、提供期間を過ぎています）")
            return 0
        _store_records(args, link)
        return 0
    except NVLinkError as error:
        _log(str(error))
        return 1
    finally:
        link.close()


def _store_records(args: argparse.Namespace, link) -> None:
    """開いたぶんを読み切って DuckDB に書き、種別ごとの件数を出す。"""
    from jvstore.record import UNKNOWN_STATS_KEY
    from .nv_store import NvStore

    layouts = load_layouts()
    started = time.time()
    written = 0
    with NvStore(Path(args.db), layouts) as store:
        records = link.records(
            on_file=lambda name: _log(f"  読込: {name}"),
            on_progress=lambda done, total: _log(f"  ダウンロード {done:,}/{total:,}"),
        )
        for data in records:
            store.write(data)
            written += 1
            if args.limit and written >= args.limit:
                _log(f"--limit {args.limit} に達したので読み込みを打ち切ります")
                break
            if written % _PROGRESS_EVERY == 0:
                _log(f"  {written:,} レコード処理 ({time.time() - started:.0f}秒)")
        store.flush()
        _log(f"合計 {written:,} レコード / {time.time() - started:.1f} 秒")
        _log("")
        _log("--- 取り込んだレコード（表＝レコード種別ごと） ---")
        for key, count in sorted(store.stats.items()):
            layout = layouts.get(key)
            _log(f"  {key} {layout.title if layout else '?':<16} {count:>9,} 件")
        unknown = store.stats.get(UNKNOWN_STATS_KEY, 0)
        if unknown:
            _log(f"  レイアウト定義に無いレコード: {unknown:,} 件（仕様の変わり目かもしれません）")
        _log(f"  -> {store.path}")


# --------------------------------------------------------------------- 設定・画面
def cmd_setup(args: argparse.Namespace) -> int:
    _log("UmaConn の設定画面を開きます（利用キーの登録）。閉じると戻ります")
    _link(args).set_ui_properties()
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    info = _link(args).info()
    print(json.dumps(info, ensure_ascii=False, indent=1))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from .web.server import serve

    serve(Path(args.db), args.port, args.open)
    return 0


def cmd_panel(args: argparse.Namespace) -> int:
    """操作パネルを開く。サーバーは `serve` と同じ引数で別プロセスとして起動する。"""
    import tempfile

    from jvstore.web.local_server import LocalServer, console_python
    from jvstore.web.panel import run_panel

    from .web.server import APP

    db = Path(args.db).resolve()
    command = [console_python(), "-m", "nvstore.cli", "serve", "--db", str(db), "--port", str(args.port)]
    log_path = Path(tempfile.gettempdir()) / f"nvstore-serve-{args.port}.log"
    run_panel(LocalServer(APP, args.port, command, Path.cwd(), log_path), APP)
    return 0


# --------------------------------------------------------------------- 引数
def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default=DEFAULT_DB, help=f"DuckDB の保存先（既定: {DEFAULT_DB}）")
    parser.add_argument("--sid", default="UNKNOWN", help="NVInit に渡すソフトウェアID")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nvstore", description="地方競馬DATA（UmaConn / NV-Link）のデータを、レコードの表単位で DuckDB に貯める")
    commands = parser.add_subparsers(dest="command", required=True)

    sync = commands.add_parser("sync", help="過去N年ぶんの蓄積系データをまとめて DuckDB に入れる")
    sync.add_argument("--years", type=int, default=10, help="何年ぶん遡るか（既定: 10。2005年より前には遡れない）")
    sync.add_argument("--dataspec", help="データ種別IDをカンマ区切りで限定（既定: RACE,DIFN,SNAP,DIFF）")
    sync.add_argument("--force-setup", action="store_true", help="続きからではなく、セットアップ取得をやり直す")
    sync.add_argument("--dry-run", action="store_true", help="対象ファイル数だけ確認して終了")
    _add_common_args(sync)
    sync.set_defaults(func=cmd_sync)

    realtime = commands.add_parser("realtime", help="開催日の速報（出馬表・成績・馬体重・天候馬場・取消・オッズ）をまとめて DuckDB に入れる")
    realtime.add_argument("--date", action="append", help="開催日 YYYY-MM-DD（何度でも書ける。省略すると今日）")
    _add_common_args(realtime)
    realtime.set_defaults(func=cmd_realtime)

    fetch = commands.add_parser("fetch", help="蓄積系データ(NVOpen)を1回ぶん取得する（動作確認用）")
    fetch.add_argument("--dataspec", required=True, help="データ種別ID（RACE, DIFN, SNAP, DIFF）")
    fetch.add_argument("--from", dest="from_", required=True, help="読み出し開始ポイント時刻 YYYYMMDDhhmmss")
    fetch.add_argument("--option", type=int, default=1, choices=(1, 2, 3, 4), help="1:通常 4:ダイアログ無しセットアップ")
    fetch.add_argument("--limit", type=int, help="読み込むレコード数の上限")
    fetch.add_argument("--dry-run", action="store_true", help="NVOpen の件数だけ確認して終了")
    _add_common_args(fetch)
    fetch.set_defaults(func=cmd_fetch)

    rt = commands.add_parser("rt", help="速報系データ(NVRTOpen)を1回ぶん取得する（動作確認用）")
    rt.add_argument("--dataspec", required=True, help="速報系データ種別ID（0B15, 0B30 …）")
    rt.add_argument("--key", required=True, help="要求キー（YYYYMMDD / YYYYMMDDJJKKHHRR）")
    rt.add_argument("--limit", type=int, help="読み込むレコード数の上限")
    _add_common_args(rt)
    rt.set_defaults(func=cmd_rt)

    setup = commands.add_parser("setup", help="UmaConn の設定画面を開く")
    setup.add_argument("--sid", default="UNKNOWN")
    setup.set_defaults(func=cmd_setup)

    info = commands.add_parser("info", help="利用キーの登録の有無・保存先・UmaConn のバージョン")
    info.add_argument("--sid", default="UNKNOWN")
    info.set_defaults(func=cmd_info)

    serve = commands.add_parser("serve", help="データ取得・管理画面を開く")
    panel = commands.add_parser("panel", help="画面の起動・停止・開き直しを行う操作パネルを開く（run.bat はこれを使う）")
    for screen in (serve, panel):
        screen.add_argument("--db", type=Path, default=Path(DEFAULT_DB))
        screen.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve.add_argument("--open", action="store_true", help="ブラウザを開く")
    serve.set_defaults(func=cmd_serve)
    panel.set_defaults(func=cmd_panel)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
