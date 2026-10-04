"""64bit の本体から見た NV-Link。実体は 32bit の取得プロセス（:mod:`nvstore.link32`）。

使い方は jvdata-store の ``JVLink`` と同じ形にしてある:

    link = LinkProcess()
    result = link.open("RACE", "20260101000000", option=4)
    for data in link.records(on_file=print):
        ...
    link.close()

``open`` / ``rt_open`` のたびに取得プロセスを1つ起動し、``close`` で終える。
レコードは標準出力のフレーム（:mod:`nvstore.frame`）で受け取る。
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Iterator

from . import frame
from .link32.broken_file_error import BROKEN_FILE_CODES, BrokenFileError
from .link32.nvlink_error import NVLinkError
from .open_result import OpenResult
from .python32 import worker_command, worker_env

__all__ = ["LinkProcess"]

#: 取得プロセスの終了を待つ上限（秒）。読み終えたあとなので、すぐ終わるはず。
_CLOSE_TIMEOUT = 30

#: 取得プロセスが落ちたとき、標準エラーの末尾をこの行数だけ理由に添える。
_STDERR_TAIL_LINES = 10

#: 取得プロセスがフレームを返さずに終わったときのコード。NV-Link のコードと重ならない値。
_WORKER_CRASHED = -9999


class LinkProcess:
    """1回の NVOpen / NVRTOpen を担う 32bit の取得プロセスの操作口。"""

    def __init__(self, sid: str = "UNKNOWN", command: list[str] | None = None,
                 env: dict[str, str] | None = None) -> None:
        self.sid = sid
        self._command = command
        self._env = env
        self._process: subprocess.Popen[bytes] | None = None
        self._stderr_path: Path | None = None

    # ------------------------------------------------------------------ 取得
    def open(self, dataspec: str, fromtime: str, option: int = 1) -> OpenResult:
        """蓄積系データの取得要求。結果の ``code`` が -1 なら該当データ無し。"""
        self._spawn(["open", "--dataspec", dataspec, "--fromtime", fromtime, "--option", str(option)])
        return self._open_result()

    def rt_open(self, dataspec: str, key: str) -> bool:
        """速報系データの取得要求。読めるデータがあれば True。"""
        self._spawn(["rtopen", "--dataspec", dataspec, "--key", key])
        return self._open_result().code == 0

    def records(
        self,
        on_file: Callable[[str], None] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> Iterator[bytes]:
        """終わりのフレームが来るまで、1 レコードずつ返す。"""
        for kind, payload in frame.read_frames(self._stdout()):
            if kind == frame.RECORD:
                yield payload
            elif kind == frame.FILE and on_file:
                on_file(payload.decode("utf-8"))
            elif kind == frame.PROGRESS and on_progress:
                progress = frame.decode_json(payload)
                on_progress(int(progress["done"]), int(progress["total"]))
            elif kind == frame.ERROR:
                raise self._error(frame.decode_json(payload))
            elif kind == frame.END:
                return
        raise self._crashed()

    def close(self) -> None:
        """取得プロセスを終える。読み切る前に呼ばれたら止める。"""
        process = self._process
        if process is None:
            return
        self._process = None
        if process.stdout is not None:
            process.stdout.close()
        try:
            process.wait(timeout=_CLOSE_TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        self._discard_stderr()

    # ------------------------------------------------------------------ 補助
    def set_ui_properties(self) -> None:
        """UmaConn の設定画面を開く。閉じるまで戻らない。"""
        self._run(["setup"])

    def info(self) -> dict[str, Any]:
        """利用キーの登録の有無・保存先・バージョン。"""
        return json.loads(self._run(["info"]))

    def file_delete(self, filename: str) -> None:
        self._run(["delete", "--filename", filename])

    def empty_files(self) -> list[str]:
        return list(json.loads(self._run(["empty-files"])))

    # ------------------------------------------------------------------ 内部
    def _base_command(self) -> list[str]:
        command = list(self._command) if self._command is not None else worker_command()
        return command + ["--sid", self.sid]

    def _environment(self) -> dict[str, str]:
        return dict(self._env) if self._env is not None else worker_env()

    def _spawn(self, arguments: list[str]) -> None:
        if self._process is not None:
            raise NVLinkError("open", -202)
        self._stderr_path = Path(tempfile.mkstemp(prefix="nvstore-link32-", suffix=".log")[1])
        stderr = self._stderr_path.open("wb")
        try:
            self._process = subprocess.Popen(
                self._base_command() + arguments, env=self._environment(),
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=stderr,
            )
        finally:
            stderr.close()

    def _run(self, arguments: list[str]) -> str:
        """レコードを流さない命令を同期で動かし、標準出力を返す。"""
        completed = subprocess.run(
            self._base_command() + arguments, env=self._environment(),
            stdin=subprocess.DEVNULL, capture_output=True,
        )
        if completed.returncode != 0:
            message = completed.stderr.decode("utf-8", errors="replace").strip()
            raise NVLinkError(arguments[0], _WORKER_CRASHED, message or f"取得プロセスが終了コード {completed.returncode} で終わりました")
        return completed.stdout.decode("utf-8", errors="replace")

    def _stdout(self):
        if self._process is None or self._process.stdout is None:
            raise NVLinkError("NVGets", -203)
        return self._process.stdout

    def _open_result(self) -> OpenResult:
        read = frame.read_frame(self._stdout())
        if read is None:
            raise self._crashed()
        kind, payload = read
        if kind == frame.ERROR:
            raise self._error(frame.decode_json(payload))
        if kind != frame.OPEN:
            raise NVLinkError("open", _WORKER_CRASHED, f"取得プロセスから予期しないフレーム {kind!r} が来ました")
        return OpenResult.from_dict(frame.decode_json(payload))

    @staticmethod
    def _error(payload: dict[str, Any]) -> NVLinkError:
        code = int(payload.get("code", 0))
        message = str(payload.get("message", ""))
        if code in BROKEN_FILE_CODES:
            return BrokenFileError(code, str(payload.get("filename", "")), message)
        return NVLinkError(str(payload.get("func", "")), code, message)

    def _crashed(self) -> NVLinkError:
        tail = self._stderr_tail()
        return NVLinkError("link32", _WORKER_CRASHED,
                           "取得プロセスが途中で終わりました。" + (f"\n{tail}" if tail else ""))

    def _stderr_tail(self) -> str:
        if self._stderr_path is None or not self._stderr_path.exists():
            return ""
        lines = self._stderr_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(line for line in lines if line.strip())[-2000:] if lines else ""

    def _discard_stderr(self) -> None:
        if self._stderr_path is None:
            return
        try:
            self._stderr_path.unlink()
        except OSError:
            pass
        self._stderr_path = None
