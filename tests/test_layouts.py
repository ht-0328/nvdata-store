"""地方のレイアウト定義が、JV-Data の定義に正しく重なることを固定する。"""

from nvstore.layouts import load_layouts

LAYOUTS = load_layouts()

#: 実データで確かめたレコード長（docs/reference/index.md）。
NV_LENGTHS = {"NU": 1492, "NK": 5529, "NC": 5098, "NN": 709, "NB": 649, "ND": 8179, "HA": 1032, "OA": 693,
              "HR": 719, "WF": 7215}


def test_地方だけのレコードと中身が違うレコードが入っている():
    for record_id, length in NV_LENGTHS.items():
        assert LAYOUTS.get(record_id).length == length, record_id


def test_JV_Data_と同じレコードはそのまま使える():
    for record_id, length in {"RA": 1272, "SE": 555, "H1": 28955, "O1": 962, "O6": 83285, "KS": 4173, "WH": 847}.items():
        assert LAYOUTS.get(record_id).length == length, record_id


def test_払戻は予備の位置に枠単が入る():
    names = [item.name for item in LAYOUTS.get("HR").items]
    assert "不成立フラグ　枠単" in names and "返還フラグ　枠単" in names
    wakutan = next(item for item in LAYOUTS.get("HR").items if item.name == "枠単払戻")
    assert wakutan.offset == 405 and wakutan.repeat == 3
    assert [child.name for child in wakutan.children] == ["組番", "払戻金", "人気順"]


def test_枠単オッズは発表月日時分も鍵にする():
    keys = [item.name for item in LAYOUTS.get("OA").items if item.is_key]
    assert keys[-1] == "発表月日時分"


def test_馬主マスタ地方と生産者マスタ地方は名前も鍵にする():
    assert [i.name for i in LAYOUTS.get("NN").items if i.is_key] == ["馬主コード", "馬主名(法人格無)"]
    assert [i.name for i in LAYOUTS.get("NB").items if i.is_key] == ["生産者コード", "生産者名(法人格無)"]


def test_データ種別は地方のものだけ():
    ids = set(LAYOUTS.dataspecs)
    assert {"RACE", "DIFN", "DIFF", "SNAP", "0B30", "0B41"} <= ids
    assert "BLDN" not in ids and "MING" not in ids
    assert "OA" in LAYOUTS.dataspecs["0B30"].record_ids
    assert "NB" in LAYOUTS.dataspecs["DIFF"].record_ids and "NB" not in LAYOUTS.dataspecs["DIFN"].record_ids
