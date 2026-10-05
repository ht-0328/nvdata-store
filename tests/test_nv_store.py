"""速くした書き込み（NvStore）が、jvdata-store の DuckStore と同じ結果になることを固定する。"""

from __future__ import annotations

import duckdb
from jvstore.store import DuckStore

from conftest import LAYOUTS, RACE, make_record
from nvstore.nv_store import NvStore

HORSE = {**RACE, "血統登録番号": "2022100001"}


def _rows(db_path, table):
    with duckdb.connect(str(db_path), read_only=True) as con:
        return sorted(con.execute(f'SELECT * FROM "{table}"').fetchall())


def _write(store_class, db_path, records):
    with store_class(db_path, LAYOUTS) as store:
        for record in records:
            store.write(record)


def _nd(created: str, kind: str, **values: str) -> bytes:
    return make_record("ND", **HORSE, データ作成年月日=created, データ区分=kind, 騎手コード="05001", 騎手名="騎手", **values)


def test_DuckStore_と同じ行になる(tmp_path):
    records = [
        _nd("20261001", "1"),
        make_record("ND", **{**HORSE, "血統登録番号": "2022100002"}, データ作成年月日="20261001", データ区分="1", 騎手コード="05002"),
        _nd("20261003", "1"),  # 同じ鍵の新しい版。子も入れ替わる
        _nd("20261002", "1"),  # 古い版。勝たない
    ]
    _write(DuckStore, tmp_path / "jv.duckdb", records)
    _write(NvStore, tmp_path / "nv.duckdb", records)
    for table in ("nd", "nd__騎手本年_累計成績情報", "nd__馬主本年_累計成績情報"):
        assert _rows(tmp_path / "nv.duckdb", table) == _rows(tmp_path / "jv.duckdb", table), table


def test_同じ取得の中に同じ鍵が2回来ても子は1行ずつ(db_path):
    record = _nd("20261001", "1")
    _write(NvStore, db_path, [record, record])
    with duckdb.connect(str(db_path), read_only=True) as con:
        counts = con.execute('SELECT "_連番", count(*) FROM "nd__騎手本年_累計成績情報" GROUP BY 1 ORDER BY 1').fetchall()
    assert all(count == 1 for _, count in counts)


def test_払戻や枠単でも_DuckStore_と同じ行になる(tmp_path):
    records = [make_record("HA", **RACE, データ作成年月日="20261004", 枠単票数合計="00000000100"),
               make_record("HR", **RACE, データ作成年月日="20261004")]
    _write(DuckStore, tmp_path / "jv.duckdb", records)
    _write(NvStore, tmp_path / "nv.duckdb", records)
    for table in ("ha", "ha__枠単票数", "hr", "hr__枠単払戻"):
        assert _rows(tmp_path / "nv.duckdb", table) == _rows(tmp_path / "jv.duckdb", table), table
