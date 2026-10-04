"""32bit の取得プロセス（:mod:`nvstore.link32`）をどう起動するか。

NV-Link は 32bit の Python からしか呼べない。本体（64bit）は、uv に 32bit の Python と
pywin32 を用意させて ``python -m nvstore.link32`` を動かす。uv を使わないときは、
環境変数 ``NVSTORE_PYTHON32`` に pywin32 入りの 32bit の python.exe を指定する。
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

__all__ = ["PYTHON32_ENV", "UV_PYTHON32", "package_root", "uv_executable", "worker_command", "worker_env"]

#: 32bit の python.exe を直接指定する環境変数。
PYTHON32_ENV = "NVSTORE_PYTHON32"

#: uv に用意させる 32bit の Python。``uv python install cpython-3.12-windows-x86`` で入るもの。
UV_PYTHON32 = "cpython-3.12-windows-x86"

#: winget で入れた uv の置き場所。PATH に無いときはここを見る。
_WINGET_UV = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages" / \
    "astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe" / "uv.exe"


def package_root() -> Path:
    """``nvstore`` パッケージが入っているフォルダ。32bit 側の PYTHONPATH に渡す。"""
    return Path(__file__).resolve().parent.parent


def uv_executable() -> str:
    found = shutil.which("uv")
    if found:
        return found
    if _WINGET_UV.exists():
        return str(_WINGET_UV)
    raise FileNotFoundError(
        "uv が見つかりません。uv を入れるか、環境変数 NVSTORE_PYTHON32 に "
        "pywin32 入りの 32bit の python.exe を指定してください。")


def worker_command() -> list[str]:
    """``python -m nvstore.link32`` までの部分。後ろに link32 の引数を足して使う。"""
    python32 = os.environ.get(PYTHON32_ENV)
    if python32:
        return [python32, "-m", "nvstore.link32"]
    return [uv_executable(), "run", "--no-project", "--python", UV_PYTHON32,
            "--with", "pywin32", "python", "-m", "nvstore.link32"]


def worker_env() -> dict[str, str]:
    """32bit 側の環境変数。``nvstore`` を見つけられるよう PYTHONPATH を足す。"""
    root = str(package_root())
    existing = os.environ.get("PYTHONPATH", "")
    return {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": root + (os.pathsep + existing if existing else ""),
    }
