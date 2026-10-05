"""コマンドの引数と、32bit の取得プロセスの起動の仕方を固定する。"""

from __future__ import annotations

from nvstore import python32
from nvstore.cli import DEFAULT_DB, DEFAULT_PORT, build_parser
from nvstore.link32.__main__ import build_parser as build_link32_parser


def test_既定の保存先とポートは中央とぶつからない():
    args = build_parser().parse_args(["sync"])
    assert args.db == DEFAULT_DB == "nvdata.duckdb" and args.years == 10
    assert build_parser().parse_args(["serve"]).port == DEFAULT_PORT == 8768


def test_コマンドの引数():
    args = build_parser().parse_args(["realtime", "--date", "2026-10-04", "--date", "2026-10-05"])
    assert args.date == ["2026-10-04", "2026-10-05"]
    args = build_parser().parse_args(["fetch", "--dataspec", "RACE", "--from", "20261001000000", "--option", "4"])
    assert (args.dataspec, args.from_, args.option) == ("RACE", "20261001000000", 4)
    args = build_link32_parser().parse_args(["--sid", "X", "rtopen", "--dataspec", "0B30", "--key", "2026100444100101"])
    assert (args.sid, args.command, args.key) == ("X", "rtopen", "2026100444100101")


def test_32bit_の_Python_は環境変数で差し替えられる(monkeypatch):
    monkeypatch.setenv(python32.PYTHON32_ENV, r"C:\py32\python.exe")
    assert python32.worker_command() == [r"C:\py32\python.exe", "-m", "nvstore.link32"]


def test_既定では_uv_に_32bit_の_Python_を用意させる(monkeypatch):
    monkeypatch.delenv(python32.PYTHON32_ENV, raising=False)
    monkeypatch.setattr(python32, "uv_executable", lambda: "uv")
    command = python32.worker_command()
    assert command[:2] == ["uv", "run"] and python32.UV_PYTHON32 in command and "pywin32" in command
    assert command[-3:] == ["python", "-m", "nvstore.link32"]


def test_取得プロセスの環境には_nvstore_の場所が入る(monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "elsewhere")
    env = python32.worker_env()
    assert env["PYTHONPATH"].startswith(str(python32.package_root())) and env["PYTHONPATH"].endswith("elsewhere")
    assert env["PYTHONIOENCODING"] == "utf-8"
