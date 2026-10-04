"""開催日の速報の取得の段取りを、NV-Link なしで固定する。"""

from __future__ import annotations

from conftest import RACE, FakeLink, make_record
from nvstore.link32.nvlink_error import NVLinkError
from nvstore.realtime import DAY_DATASPECS, RACE_DATASPECS, fetch_day, parse_day

RACE_KEY = "2026100444100101"


def test_開催日単位の速報を先に取り_レース毎のオッズはその日の全レースのキーで取る(db_path):
    other = {**RACE, "競馬場コード": "54", "レース番号": "02"}
    link = FakeLink({"0B15": [make_record("RA", **RACE), make_record("RA", **other)],
                     "0B30": [make_record("O1", **RACE, 発表月日時分="10041200")]})
    result = fetch_day(db_path, "2026-10-04", log=lambda _: None, link_factory=lambda: link)
    assert [call[1] for call in link.calls[:len(DAY_DATASPECS)]] == [name for name, _ in DAY_DATASPECS]
    assert [call for call in link.calls if call[1] == "0B30"] == [
        ("rt_open", "0B30", RACE_KEY), ("rt_open", "0B30", "2026100454100102")]
    assert result.races == 2 and result.records["0B30"] == 2
    assert [name for name, _ in RACE_DATASPECS] == ["0B30"]


def test_該当データなしは失敗にしない(db_path):
    link = FakeLink()
    result = fetch_day(db_path, "20261004", log=lambda _: None, link_factory=lambda: link)
    assert result.failed == [] and set(result.empty) == {name for name, _ in DAY_DATASPECS}


def test_1つの種別が失敗しても残りを続ける(db_path):
    link = FakeLink({"0B11": [make_record("WH", **RACE)]}, errors={"0B15:20261004": NVLinkError("NVRTOpen", -301)})
    result = fetch_day(db_path, "20261004", log=lambda _: None, link_factory=lambda: link)
    assert result.failed == ["0B15"] and result.records["0B11"] == 1


def test_その日のレースが無ければ_オッズは取りにいかない(db_path):
    link = FakeLink({"0B30": [make_record("O1", **RACE)]})
    result = fetch_day(db_path, "20261004", log=lambda _: None, link_factory=lambda: link)
    assert result.races == 0 and not [call for call in link.calls if call[1] == "0B30"]


def test_取得プロセスは種別ごとに閉じる(db_path):
    link = FakeLink({"0B15": [make_record("RA", **RACE)]})
    fetch_day(db_path, "20261004", log=lambda _: None, link_factory=lambda: link)
    assert link.closed == len(DAY_DATASPECS) + 1


def test_開催日の書き方():
    assert parse_day("2026-10-04") == "20261004" and parse_day("20261004") == "20261004"
