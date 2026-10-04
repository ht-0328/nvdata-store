"""画面の入力・保存先・排他・失敗表示を、実通信なしで固定する。"""

import json
import threading
from http.client import HTTPConnection

import pytest

from nvstore.web.server import APP, Backend, _Server, make_handler


def test_画面は名乗りと_HTML_を返し_DB_が無くても動く(tmp_path):
    backend = Backend(tmp_path / "not-created.duckdb")
    server = _Server(("127.0.0.1", 0), make_handler(backend))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    con = HTTPConnection(*server.server_address, timeout=5)
    try:
        con.request("GET", "/api/info")
        assert json.loads(con.getresponse().read()) == {"app": APP, "db": str(backend.db)}
        con.request("GET", "/")
        response = con.getresponse()
        assert response.status == 200
        assert "地方競馬DATA 取得・管理" in response.read().decode("utf-8")
        con.request("GET", "/api/history/tables")
        assert json.loads(con.getresponse().read())["ready"] is False
        con.request("GET", "/api/dataspecs")
        assert [spec["id"] for spec in json.loads(con.getresponse().read())["dataspecs"]] == ["RACE", "DIFN", "SNAP", "DIFF"]
        assert not backend.db.exists()
    finally:
        con.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture
def api(tmp_path, monkeypatch):
    backend = Backend(tmp_path / "history.duckdb")
    calls = []
    monkeypatch.setattr(backend.task, "start", lambda *a, **kw: calls.append((a, kw)) or True)
    server = _Server(("127.0.0.1", 0), make_handler(backend))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def post(query, path="/api/history/fetch"):
        con = HTTPConnection(*server.server_address, timeout=5)
        try:
            con.request("POST", path + ("?" + query if query else ""))
            response = con.getresponse()
            return response.status, json.loads(response.read())
        finally:
            con.close()

    yield backend, calls, post
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_取得は_nvstore_のコマンドを保存先付きで呼ぶ(api):
    backend, calls, post = api
    status, result = post("years=3&dataspec=RACE,DIFN&force_setup=1")
    assert status == 200 and result == {"started": True}
    (label, steps, cwd), kwargs = calls[0]
    command = steps[0]
    assert command[1:4] == ["-m", "nvstore.cli", "sync"]
    assert command[command.index("--db") + 1] == str(backend.db)
    assert command[command.index("--dataspec") + 1] == "RACE,DIFN" and "--force-setup" in command
    assert kwargs["db_lock"] is backend._lock


def test_知らないデータ種別と変な年数は断る(api):
    _, calls, post = api
    assert post("years=10&dataspec=MING")[0] == 400
    assert post("years=0")[0] == 400
    assert calls == []


def test_速報の取得は開催日ごとに引数を渡す(api):
    backend, calls, post = api
    status, _ = post("date=2026-10-04&date=2026-10-05", path="/api/realtime/fetch")
    assert status == 200
    command = calls[0][0][1][0]
    assert command[1:4] == ["-m", "nvstore.cli", "realtime"]
    assert command.count("--date") == 2 and "20261004" in command and "20261005" in command
    assert post("", path="/api/realtime/fetch")[0] == 400


def test_UmaConn_の設定画面を開く(api):
    _, calls, post = api
    assert post("", path="/api/umaconn-setup") == (200, {"started": True})
    assert calls[0][0][1][0][1:5] == ["-m", "nvstore.cli", "setup"]
