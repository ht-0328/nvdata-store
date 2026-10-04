"""32bit の取得プロセスの入口。64bit の本体（:class:`nvstore.link_process.LinkProcess`）が起動する。

    python -m nvstore.link32 open --dataspec RACE --fromtime 20260101000000 --option 4
    python -m nvstore.link32 rtopen --dataspec 0B30 --key 2026100444100101
    python -m nvstore.link32 setup            UmaConn の設定画面を開く
    python -m nvstore.link32 info             利用キーの登録の有無・保存先・バージョンを JSON で出す
    python -m nvstore.link32 delete --filename RANV….nvd
    python -m nvstore.link32 empty-files      大きさ0のファイルの名前を JSON で出す

``open`` と ``rtopen`` は、レコードを標準出力にフレーム（:mod:`nvstore.frame`）で流す。
それ以外は標準出力に JSON か何も出さない。
"""

from __future__ import annotations

import argparse
import json
import sys

from .frame_writer import FrameWriter
from .nvlink import NVLink
from .nvlink_error import NVLinkError
from .streamer import Streamer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nvstore.link32", description=__doc__)
    parser.add_argument("--sid", default="UNKNOWN", help="NVInit に渡すソフトウェアID")
    commands = parser.add_subparsers(dest="command", required=True)

    opened = commands.add_parser("open", help="蓄積系データ（NVOpen）を読んでフレームで流す")
    opened.add_argument("--dataspec", required=True)
    opened.add_argument("--fromtime", required=True)
    opened.add_argument("--option", type=int, default=1, choices=(1, 2, 3, 4))

    rt = commands.add_parser("rtopen", help="速報系データ（NVRTOpen）を読んでフレームで流す")
    rt.add_argument("--dataspec", required=True)
    rt.add_argument("--key", required=True)

    commands.add_parser("setup", help="UmaConn の設定画面を開く")
    commands.add_parser("info", help="利用キーの登録の有無・保存先・バージョン")
    delete = commands.add_parser("delete", help="保存パスのファイルを消す（NVFiledelete）")
    delete.add_argument("--filename", required=True)
    commands.add_parser("empty-files", help="保存パスにある大きさ0のファイル")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    link = NVLink(args.sid)
    try:
        link.init()
        return run(args, link)
    except NVLinkError as error:
        print(str(error), file=sys.stderr)
        return 1
    finally:
        link.dispose()


def run(args: argparse.Namespace, link: NVLink) -> int:
    if args.command == "open":
        return Streamer(link, FrameWriter(sys.stdout.buffer)).historical(args.dataspec, args.fromtime, args.option)
    if args.command == "rtopen":
        return Streamer(link, FrameWriter(sys.stdout.buffer)).realtime(args.dataspec, args.key)
    if args.command == "setup":
        link.set_ui_properties()
        return 0
    if args.command == "info":
        print(json.dumps(link.info(), ensure_ascii=False))
        return 0
    if args.command == "delete":
        link.file_delete(args.filename)
        return 0
    print(json.dumps(link.empty_files(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
