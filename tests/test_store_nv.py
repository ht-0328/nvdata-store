"""地方のレコードが、jvdata-store と同じ作りの表に入ることを固定する。"""

from __future__ import annotations

import duckdb
from jvstore.store import DuckStore

from conftest import LAYOUTS, RACE, make_record


def test_枠単票数は親と子の表に分かれる(db_path):
    with DuckStore(db_path, LAYOUTS) as store:
        store.write(make_record("HA", **RACE, 枠単票数合計="00000008759"))
    with duckdb.connect(str(db_path), read_only=True) as con:
        tables = {name for (name,) in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}
        assert {"ha", "ha__枠単票数"} <= tables
        assert con.execute('SELECT "枠単票数合計" FROM ha').fetchone() == ("00000008759",)


def test_枠単オッズは発表時刻ごとに行が残る(db_path):
    with DuckStore(db_path, LAYOUTS) as store:
        store.write(make_record("OA", **RACE, 発表月日時分="10041200", データ作成年月日="20261004"))
        store.write(make_record("OA", **RACE, 発表月日時分="10041230", データ作成年月日="20261004"))
    with duckdb.connect(str(db_path), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM oa").fetchone()[0] == 2


def test_競走馬マスタ地方は血統登録番号で1件(db_path):
    with DuckStore(db_path, LAYOUTS) as store:
        store.write(make_record("NU", 血統登録番号="2022100001", データ作成年月日="20261001", データ区分="1"))
        store.write(make_record("NU", 血統登録番号="2022100001", データ作成年月日="20261004", データ区分="4"))
    with duckdb.connect(str(db_path), read_only=True) as con:
        assert con.execute('SELECT "データ作成年月日" FROM nu').fetchall() == [("20261004",)]
        assert con.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = 'nu__3代血統情報'").fetchone()[0] == 1


def test_払戻には枠単の列と子テーブルがある(db_path):
    with DuckStore(db_path, LAYOUTS) as store:
        store.write(make_record("HR", **RACE))
    with duckdb.connect(str(db_path), read_only=True) as con:
        columns = {c for (c,) in con.execute("SELECT column_name FROM duckdb_columns() WHERE table_name = 'hr'").fetchall()}
        assert "返還フラグ　枠単" in columns
        assert con.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = 'hr__枠単払戻'").fetchone()[0] == 1


def test_すべての表でスキーマを作れる(db_path):
    with DuckStore(db_path, LAYOUTS) as store:
        for record_id in LAYOUTS.layouts:
            store.ensure_tables(record_id)
