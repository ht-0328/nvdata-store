"""64bit の本体が 32bit の取得プロセスをどう動かすかを、偽の取得プロセスで固定する。

偽の取得プロセスは、引数に応じてフレームを流すだけの小さな Python スクリプト。
NV-Link（COM）無しで、起動・フレームの受け取り・エラー・途中終了を確かめる。
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

import pytest

from nvstore.link32.broken_file_error import BrokenFileError
from nvstore.link32.nvlink_error import NVLinkError
from nvstore.link_process import LinkProcess
from nvstore.python32 import package_root

FAKE_WORKER = textwrap.dedent('''
    import sys
    from nvstore import frame
    out = sys.stdout.buffer
    args = sys.argv[1:]
    had_sid = args[:1] == ["--sid"]      # LinkProcess は先頭に --sid を付けて起動する
    if had_sid:
        args = args[2:]
    command = args[0]
    def send(kind, payload=b""):
        frame.write_frame(out, kind, payload); out.flush()
    if command == "open":
        dataspec = args[args.index("--dataspec") + 1]
        if dataspec == "NONE":
            send(frame.OPEN, frame.encode_json({"code": -1})); send(frame.END); sys.exit(0)
        if dataspec == "BAD":
            send(frame.ERROR, frame.encode_json({"func": "NVOpen", "code": -111, "message": "dataspec が不正"})); sys.exit(1)
        send(frame.OPEN, frame.encode_json({"code": 0, "read_count": 2, "download_count": 1, "last_file_timestamp": "20261004231021"}))
        send(frame.PROGRESS, frame.encode_json({"done": 1, "total": 1}))
        send(frame.FILE, "RANV2026.nvd".encode("utf-8"))
        send(frame.RECORD, b"RA" + b"1" * 10)
        if dataspec == "BROKEN":
            send(frame.ERROR, frame.encode_json({"func": "NVGets", "code": -402, "message": "size 0", "filename": "RANV2026.nvd"})); sys.exit(1)
        if dataspec == "CRASH":
            print("Traceback: boom", file=sys.stderr); sys.exit(3)
        send(frame.RECORD, b"SE" + b"2" * 10)
        send(frame.END)
    elif command == "rtopen":
        key = args[args.index("--key") + 1]
        if key == "none":
            send(frame.OPEN, frame.encode_json({"code": -1})); send(frame.END); sys.exit(0)
        send(frame.OPEN, frame.encode_json({"code": 0, "read_count": 1}))
        send(frame.RECORD, b"O1" + b"3" * 10)
        send(frame.END)
    elif command == "info":
        print('{"service_key_registered": true, "save_path": "C:/UmaConn", "version": "0354"}')
    elif command == "delete":
        pass
    elif command == "empty-files":
        print('["RANV2026.nvd"]')
    elif command == "setup":
        if not had_sid: sys.exit(2)
''')


@pytest.fixture
def link(tmp_path: Path) -> LinkProcess:
    script = tmp_path / "fake_worker.py"
    script.write_text(FAKE_WORKER, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(package_root()), "PYTHONIOENCODING": "utf-8"}
    return LinkProcess(command=[sys.executable, str(script)], env=env)


def test_開いて_ファイル名と進捗を受け取りながら_レコードを読み切る(link: LinkProcess):
    result = link.open("RACE", "20261003000000", 1)
    assert (result.code, result.read_count, result.download_count, result.last_file_timestamp) == (0, 2, 1, "20261004231021")
    files, progress = [], []
    records = list(link.records(on_file=files.append, on_progress=lambda d, t: progress.append((d, t))))
    link.close()
    assert records == [b"RA" + b"1" * 10, b"SE" + b"2" * 10]
    assert files == ["RANV2026.nvd"] and progress == [(1, 1)]


def test_該当データなしは_code_が_1(link: LinkProcess):
    assert link.open("NONE", "20261003000000", 1).code == -1
    assert list(link.records()) == []
    link.close()


def test_速報は読めるときだけ_True(link: LinkProcess):
    assert link.rt_open("0B30", "2026100444100101") is True
    assert list(link.records()) == [b"O1" + b"3" * 10]
    link.close()
    assert link.rt_open("0B30", "none") is False
    link.close()


def test_NV_Link_のエラーは例外になる(link: LinkProcess):
    with pytest.raises(NVLinkError) as caught:
        link.open("BAD", "20261003000000", 1)
    assert caught.value.code == -111
    link.close()


def test_壊れたファイルはファイル名付きの例外になる(link: LinkProcess):
    link.open("BROKEN", "20261003000000", 1)
    with pytest.raises(BrokenFileError) as caught:
        list(link.records())
    assert caught.value.filename == "RANV2026.nvd" and caught.value.code == -402
    link.close()


def test_取得プロセスが途中で落ちたら_標準エラーの中身を添えて例外(link: LinkProcess):
    link.open("CRASH", "20261003000000", 1)
    with pytest.raises(NVLinkError) as caught:
        list(link.records())
    assert "途中で終わりました" in str(caught.value) and "boom" in str(caught.value)
    link.close()


def test_開いたまま_もう一度開けない(link: LinkProcess):
    link.open("RACE", "20261003000000", 1)
    with pytest.raises(NVLinkError) as caught:
        link.open("RACE", "20261003000000", 1)
    assert caught.value.code == -202
    link.close()


def test_情報_削除_空ファイル_設定画面は同期の命令(link: LinkProcess):
    assert link.info()["service_key_registered"] is True
    link.file_delete("RANV2026.nvd")
    assert link.empty_files() == ["RANV2026.nvd"]
    link.set_ui_properties()
