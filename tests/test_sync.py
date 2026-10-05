"""過去N年ぶんの取得の段取りを、NV-Link なしで固定する。"""

from __future__ import annotations

from datetime import date

import duckdb
import pytest

from conftest import RACE, FakeLink, during_read, make_record
from nvstore.link32.broken_file_error import BrokenFileError
from nvstore.link32.nvlink_error import NVLinkError
from nvstore.sync import SYNC_DATASPECS, start_time, sync


def test_開始時刻は年の1月1日まで切り下げる():
    assert start_time(1, today=date(2026, 10, 5)) == "20250101000000"


def test_開始時刻は2005年より前にならない():
    assert start_time(40, today=date(2026, 10, 5)) == "20050101000000"


def test_年数の指定は1から40まで():
    for years in (0, 41):
        with pytest.raises(ValueError):
            start_time(years)


def test_既定で4種別を回す(db_path):
    link = FakeLink()
    sync(db_path, years=1, log=lambda _: None, link_factory=lambda: link)
    assert [call[1] for call in link.calls] == [name for name, _ in SYNC_DATASPECS]


def test_初回はセットアップ_2回目は続きから(db_path):
    link = FakeLink({"RACE": [make_record("RA", **RACE)]}, timestamps={"RACE": "20261004231021"})
    sync(db_path, years=1, dataspecs=["RACE"], log=lambda _: None, link_factory=lambda: link)
    assert link.calls[0] == ("open", "RACE", start_time(1), 4)
    sync(db_path, years=1, dataspecs=["RACE"], log=lambda _: None, link_factory=lambda: link)
    assert link.calls[1] == ("open", "RACE", "20261004231021", 1)


def test_force_setup_でセットアップからやり直せる(db_path):
    link = FakeLink({"RACE": [make_record("RA", **RACE)]})
    sync(db_path, years=1, dataspecs=["RACE"], log=lambda _: None, link_factory=lambda: link)
    sync(db_path, years=1, dataspecs=["RACE"], log=lambda _: None, link_factory=lambda: link, force_setup=True)
    assert link.calls[1][3] == 4


def test_受け取ったレコードがテーブルに入る(db_path):
    link = FakeLink({"RACE": [make_record("RA", **RACE), make_record("HA", **RACE)]})
    result = sync(db_path, years=1, dataspecs=["RACE"], log=lambda _: None, link_factory=lambda: link)
    assert result.records == 2 and result.counts["ra"] == 1 and result.counts["ha"] == 1


def test_DIFF_からは生産者マスタ地方だけを取り込む(db_path):
    link = FakeLink({"DIFF": [make_record("NB", 生産者コード="000001"), make_record("NU", 血統登録番号="2022100001"),
                              make_record("KS", 騎手コード="05001")]})
    result = sync(db_path, years=1, dataspecs=["DIFF"], log=lambda _: None, link_factory=lambda: link)
    assert result.records == 1 and result.counts["nb"] == 1 and "nu" not in result.counts


def test_SNAP_からは出走別着度数地方だけを取り込む(db_path):
    nd = make_record("ND", **RACE, 血統登録番号="2022100001")
    ck = make_record("CK", **RACE, 血統登録番号="2022100001")
    link = FakeLink({"SNAP": [nd, ck]})
    result = sync(db_path, years=1, dataspecs=["SNAP"], log=lambda _: None, link_factory=lambda: link)
    assert result.records == 1 and result.counts["nd"] == 1 and "ck" not in result.counts


def test_DIFN_は全部取り込む(db_path):
    link = FakeLink({"DIFN": [make_record("NU", 血統登録番号="2022100001"), make_record("KS", 騎手コード="05001")]})
    result = sync(db_path, years=1, dataspecs=["DIFN"], log=lambda _: None, link_factory=lambda: link)
    assert result.counts["nu"] == 1 and result.counts["ks"] == 1


def test_該当データなしは失敗にせず_続きの起点も動かさない(db_path):
    link = FakeLink()
    result = sync(db_path, years=1, dataspecs=["SNAP"], log=lambda _: None, link_factory=lambda: link)
    assert result.failed == []
    sync(db_path, years=1, dataspecs=["SNAP"], log=lambda _: None, link_factory=lambda: link)
    assert link.calls[1][3] == 4


def test_dry_run_では書き込まず_取得位置も進めない(db_path):
    link = FakeLink({"RACE": [make_record("RA", **RACE)]})
    sync(db_path, years=1, dataspecs=["RACE"], log=lambda _: None, link_factory=lambda: link, dry_run=True)
    with duckdb.connect(str(db_path), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name = 'ra'").fetchone()[0] == 0
    sync(db_path, years=1, dataspecs=["RACE"], log=lambda _: None, link_factory=lambda: link)
    assert link.calls[1][3] == 4


def test_1種別が失敗しても残りは続ける(db_path):
    link = FakeLink({"DIFN": [make_record("NU", 血統登録番号="2022100001")]}, errors={"RACE": NVLinkError("NVOpen", -301)})
    result = sync(db_path, years=1, dataspecs=["RACE", "DIFN"], log=lambda _: None, link_factory=lambda: link)
    assert result.failed == ["RACE"] and result.counts["nu"] == 1


def test_取得プロセスは必ず閉じる(db_path):
    link = FakeLink({"RACE": [make_record("RA", **RACE)]}, errors={"DIFN": NVLinkError("NVOpen", -301)})
    sync(db_path, years=1, dataspecs=["RACE", "DIFN"], log=lambda _: None, link_factory=lambda: link)
    assert link.closed == 2


def test_壊れたファイルは消して開き直す(db_path):
    class Flaky(FakeLink):
        attempts = 0

        def records(self, on_file=None, on_progress=None):
            Flaky.attempts += 1
            if Flaky.attempts == 1:
                raise BrokenFileError(-402, "RANV2026.nvd")
            yield from super().records(on_file, on_progress)

    link = Flaky({"RACE": [make_record("RA", **RACE)]})
    result = sync(db_path, years=1, dataspecs=["RACE"], log=lambda _: None, link_factory=lambda: link)
    assert link.deleted == ["RANV2026.nvd"] and result.failed == [] and result.counts["ra"] == 1


def test_消すファイルが分からなければ失敗にする(db_path):
    link = FakeLink({"RACE": [make_record("RA", **RACE)]}, errors={"RACE": during_read(BrokenFileError(-402, ""))})
    result = sync(db_path, years=1, dataspecs=["RACE"], log=lambda _: None, link_factory=lambda: link)
    assert result.failed == ["RACE"] and link.deleted == []
