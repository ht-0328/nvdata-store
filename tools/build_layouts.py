r"""地方競馬DATA（NV-Data）のうち、JV-Data と並びが違うレコードのレイアウト定義を作る。

出力は ``spec/nv_layouts.json``。形は jvdata-store の ``layouts.json`` と同じにしてあるので、
jvdata-store の ``jvstore.layout.load_layouts`` でそのまま読める。

    uv run --no-project python tools/build_layouts.py ^
        --jv-layouts ..\jvdata-store\src\jvstore\resources\layouts.json

地方だけのレコード（NU NK NC NN NB ND HA OA）は、このファイルの表（項目名・バイト数）から組む。
JV-Data と同じ長さで一部の項目だけ違うレコード（HR WF）は、JV-Data のレイアウトを土台に
項目を差し替えるので、``--jv-layouts`` が要る。

項目名・バイト数の出どころは PC-KEIBA テーブル定義書（nvd_* の表）で、並びと中身は実データで
確かめた。確かめ方は ``docs/reference/`` の各ページにある。
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "spec" / "nv_layouts.json"

#: 1つの項目。``children`` が空なら単純項目、あれば繰返しブロック。
Item = dict[str, Any]


# ---------------------------------------------------------------- 項目の書き方


def f(name: str, size: int, comment: str = "", *, key: bool = False, default: str = "") -> Item:
    """単純な項目。"""
    return {"name": name, "size": size, "repeat": 1, "is_key": key, "default": default,
            "comment": comment, "children": []}


def rep(name: str, size: int, repeat: int, comment: str = "") -> Item:
    """内訳を持たない繰返し項目（``着回数`` 3桁×6 など）。"""
    return {"name": name, "size": size, "repeat": repeat, "is_key": False, "default": "",
            "comment": comment, "children": []}


def grp(name: str, repeat: int, children: list[Item], comment: str = "") -> Item:
    """内訳を持つ繰返しブロック。1回分のバイト数は内訳の合計。"""
    return {"name": name, "size": sum(c["size"] * c["repeat"] for c in children), "repeat": repeat,
            "is_key": False, "default": "", "comment": comment, "children": children}


def chaku(name: str, comment: str = "1着〜5着・着外(6着以下)の回数") -> Item:
    """着回数（3桁×6）。"""
    return rep(name, 3, 6, comment)


def chaku6(name: str, comment: str = "1着〜5着・着外(6着以下)の回数") -> Item:
    """成績情報の中の着回数（6桁×6）。"""
    return rep(name, 6, 6, comment)


# ---------------------------------------------------------------- 共通の部品

COMMON = [
    f("レコード種別ID", 2, "レコードフォーマットを特定する"),
    f("データ区分", 1, "どの段階の情報か。使われる値は各レコードの説明にある"),
    f("データ作成年月日", 8, "西暦4桁＋月日各2桁 yyyymmdd 形式"),
]

RACE_KEY = [
    f("開催年", 4, "該当レース施行年 西暦4桁 yyyy形式", key=True),
    f("開催月日", 4, "該当レース施行月日 各2桁 mmdd形式", key=True),
    f("競馬場コード", 2, "<コード表 2001.競馬場コード>参照。地方は 30〜57。ばんえい帯広は 83", key=True),
    f("開催回[第N回]", 2, "該当レース施行回", key=True),
    f("開催日目[N日目]", 2, "該当レース施行日目", key=True),
    f("レース番号", 2, "該当レース番号", key=True),
]

SEPARATOR = f("レコード区切", 2, "CR/LF")

#: 騎手・調教師の成績情報に並ぶ競馬場。廃止された場も含めて33場、この順で固定。
VENUES33 = ["門別", "北見", "岩見沢", "帯広", "旭川", "盛岡", "水沢", "上山", "三条", "足利", "宇都宮",
            "高崎", "浦和", "船橋", "大井", "川崎", "金沢", "笠松", "名古屋", "紀三井寺", "園田", "姫路",
            "益田", "福山", "高知", "佐賀", "荒尾", "中津", "札幌", "函館", "新潟", "中京", "春木"]

#: 出走別着度数地方の競馬場別着回数。芝は5場、ダートは33場、この順で固定。
VENUES38 = ["盛岡芝", "札幌芝", "函館芝", "新潟芝", "中京芝"] + [v + "ダ" for v in VENUES33]

#: 出走別着度数地方の距離区分。芝・ダートそれぞれ11区分。
DIST11 = ["1000以下", "1001-1200", "1201-1300", "1301-1400", "1401-1500", "1501-1600",
          "1601-1700", "1701-1800", "1801-2000", "2001-2200", "2201以上"]

#: 競走馬マスタ・騎手マスタの距離区分（JV-Data と同じ6区分）。
DIST6 = ["芝16下", "芝22下", "芝22超", "ダ16下", "ダ22下", "ダ22超"]

#: 馬場状態別の着回数の名前（JV-Data と同じ8区分）。
BABA8 = ["芝良", "芝稍", "芝重", "芝不", "ダ良", "ダ稍", "ダ重", "ダ不"]

#: 回り別の着回数の名前（JV-Data と同じ6区分）。
MAWARI6 = ["芝直", "芝右", "芝左", "ダ直", "ダ右", "ダ左"]


def seiseki_kishu_chokyoshi() -> list[Item]:
    """NK・NC の 本年･前年･累計成績情報（1,464バイト）の内訳。

    設定年＋賞金2つ＋着回数（6桁×6）が40組。40組は 合計・33場・6距離区分 の順。
    合計 ＝ 33場の和 ＝ 6距離区分の和 になることを実データで確かめた。
    """
    return ([f("設定年", 4, "本年･前年は西暦4桁。累計は 0000"),
             f("本賞金合計", 10, "単位：百円"),
             f("付加賞金合計", 10, "単位：百円"),
             chaku6("合計着回数", "全競馬場の合計。1着〜5着・着外の回数")]
            + [chaku6(v + "着回数") for v in VENUES33]
            + [chaku6(d + "・着回数") for d in DIST6])


def seiseki_banushi_seisansha_116() -> list[Item]:
    """NN・NB の 本年･累計成績情報（116バイト）の内訳。JV-Data の KS の成績情報と同じ頭の形。"""
    return [f("設定年", 4, "本年は西暦4桁。累計は 0000"),
            f("平地本賞金合計", 10, "単位：百円"),
            f("障害本賞金合計", 10, "単位：百円。観測した範囲では 0"),
            f("平地付加賞金合計", 10, "単位：百円。観測した範囲では 0"),
            f("障害付加賞金合計", 10, "単位：百円。観測した範囲では 0"),
            chaku6("平地着回数"),
            chaku6("障害着回数", "観測した範囲では 0")]


def seiseki_nd_1524() -> list[Item]:
    """ND の騎手・調教師の 本年･累計成績情報（1,524バイト）の内訳。

    芝着回数＋ダート着回数 ＝ 距離別22区分の和 ＝ 競馬場別38区分の和 になることを実データで確かめた。
    """
    return ([f("設定年", 4, "本年は西暦4桁。累計は 0000"),
             f("本賞金合計", 10, "単位：百円。調教師では観測した範囲で 0"),
             f("付加賞金合計", 10, "単位：百円"),
             rep("芝着回数", 5, 6, "1着〜5着・着外の回数"),
             rep("ダート着回数", 5, 6, "1着〜5着・着外の回数")]
            + [rep("芝" + d + "・着回数", 4, 6) for d in DIST11]
            + [rep("ダ" + d + "・着回数", 4, 6) for d in DIST11]
            + [rep(v + "・着回数", 4, 6) for v in VENUES38])


def seiseki_60() -> list[Item]:
    """ND の馬主・生産者の 本年･累計成績情報（60バイト）。JV-Data の BN と同じ。"""
    return [f("設定年", 4, "観測した範囲では 0000"),
            f("本賞金合計", 10, "単位：百円"),
            f("付加賞金合計", 10, "単位：百円"),
            chaku6("着回数")]


def jusho_info() -> list[Item]:
    """最近重賞勝利情報の内訳。JV-Data の KS・CH と同じ。"""
    return [f("年月日場回日R", 16), f("競走名本題", 60), f("競走名略称10文字", 20), f("競走名略称6文字", 12),
            f("競走名略称3文字", 6), f("グレードコード", 1), f("出走頭数", 2), f("血統登録番号", 10), f("馬名", 36)]


# ---------------------------------------------------------------- 地方だけのレコード


def nu_items() -> list[Item]:
    """NU 競走馬マスタ地方。JV-Data の UM から障害の項目を抜き、いくつかの意味を変えたもの。"""
    return (COMMON + [
        f("血統登録番号", 10, "生年4桁＋品種1桁＋数字5桁。ばんえい（品種 B）は生年と一致せず5桁目が 2", key=True),
        f("競走馬抹消区分", 1, "0:現役 1:抹消"),
        f("競走馬登録年月日", 8, "yyyymmdd。観測した範囲では 00000000"),
        f("競走馬抹消年月日", 8, "yyyymmdd"),
        f("生年月日", 8, "yyyymmdd"),
        f("馬名", 36, "全角18文字"),
        f("馬名半角ｶﾅ", 36, "半角36文字"),
        f("馬名欧字", 60, "観測した範囲では空"),
        f("在厩フラグ", 1, "JV-Data の JRA施設在きゅうフラグ の位置。0 または 1"),
        f("予備", 19),
        f("馬記号コード", 2, "<コード表 2204.馬記号コード>参照。観測した範囲では 00"),
        f("性別コード", 1, "<コード表 2202.性別コード>参照"),
        f("品種コード", 1, "<コード表 2201.品種コード>参照。ばんえいは B"),
        f("毛色コード", 2, "<コード表 2203.毛色コード>参照"),
        grp("3代血統情報", 14, [f("繁殖登録番号", 10), f("馬名", 36)],
            "父･母･父父･父母･母父･母母･父父父･父父母･父母父･父母母･母父父･母父母･母母父･母母母の順（JV-Data と同じ）。"
            "ばんえいは3代目以降の馬名が空"),
        f("東西所属コード", 1, "<コード表 2301.東西所属コード>参照。地方所属は 3"),
        f("調教師コード", 5, "NC 調教師マスタ地方へリンク"),
        f("調教師名略称", 8, "全角4文字"),
        f("招待地域名", 20, "地方では所属（大井・名古屋・ばんえい など）が入る"),
        f("生産者コード", 8, "NB 生産者マスタ地方へリンク。00000000 が多い"),
        f("生産者名(法人格無)", 72),
        f("産地名", 20),
        f("馬主コード", 6, "NN 馬主マスタ地方へリンク。000000 が多い"),
        f("馬主名(法人格無)", 64),
        f("本賞金累計", 9, "単位：百円"),
        f("付加賞金累計", 9, "単位：百円"),
        f("収得賞金累計", 9, "単位：百円"),
        chaku("総合着回数"),
        chaku("地方合計着回数", "JV-Data の 中央合計着回数 の位置。地方のみの1着〜5着・着外の回数"),
    ] + [chaku(m + "・着回数") for m in MAWARI6]
      + [chaku(b + "・着回数") for b in BABA8]
      + [chaku(d + "・着回数") for d in DIST6]
      + [rep("脚質傾向", 3, 4, "逃げ回数、先行回数、差し回数、追込回数。観測した範囲では 0"),
         f("登録レース数", 3, "観測した範囲では 000"),
         SEPARATOR])


def nk_items() -> list[Item]:
    """NK 騎手マスタ地方。JV-Data の KS に服色標示2つを足し、成績情報を地方の形にしたもの。"""
    return (COMMON + [
        f("騎手コード", 5, "", key=True),
        f("騎手抹消区分", 1, "0:現役 1:抹消"),
        f("騎手免許交付年月日", 8, "yyyymmdd"),
        f("騎手免許抹消年月日", 8, "yyyymmdd"),
        f("生年月日", 8, "yyyymmdd"),
        f("騎手名", 34, "全角17文字"),
        f("予備", 34),
        f("騎手名半角ｶﾅ", 30),
        f("騎手名略称", 8, "全角4文字"),
        f("騎手名欧字", 80),
        f("性別区分", 1, "1:男性 2:女性"),
        f("騎乗資格コード", 1, "<コード表 2302.騎乗資格コード>参照。観測した範囲では 2"),
        f("騎手見習コード", 1, "<コード表 2303.騎手見習コード>参照。観測した範囲では 0"),
        f("騎手東西所属コード", 1, "<コード表 2301.東西所属コード>参照。地方所属は 3"),
        f("招待地域名", 20, "地方では所属（大井・名古屋・ばんえい など）が入る"),
        f("所属調教師コード", 5, "フリーは 00000"),
        f("所属調教師名略称", 8),
        f("服色標示（画像取得用）", 60, "勝負服の色・模様。「緑，黒縦縞，…」のような区切り付きの表記"),
        f("服色標示（文字表示用）", 60, "勝負服の色・模様。「胴緑・黒縦じま、袖…」のような読む人向けの表記"),
        grp("初騎乗情報", 2, [f("年月日場回日R", 16), f("出走頭数", 2), f("血統登録番号", 10), f("馬名", 36),
                           f("確定着順", 2), f("異常区分コード", 1)], "JV-Data の KS と同じ並び"),
        grp("初勝利情報", 2, [f("年月日場回日R", 16), f("出走頭数", 2), f("血統登録番号", 10), f("馬名", 36)],
            "JV-Data の KS と同じ並び"),
        grp("最近重賞勝利情報", 3, jusho_info(), "JV-Data の KS と同じ並び。観測した範囲では空"),
        grp("本年･前年･累計成績情報", 3, seiseki_kishu_chokyoshi(), "本年・前年・累計の順"),
        SEPARATOR])


def nc_items() -> list[Item]:
    """NC 調教師マスタ地方。JV-Data の CH の成績情報を地方の形にしたもの。"""
    return (COMMON + [
        f("調教師コード", 5, "", key=True),
        f("調教師抹消区分", 1, "0:現役 1:抹消"),
        f("調教師免許交付年月日", 8, "yyyymmdd"),
        f("調教師免許抹消年月日", 8, "yyyymmdd"),
        f("生年月日", 8, "yyyymmdd"),
        f("調教師名", 34, "全角17文字"),
        f("調教師名半角ｶﾅ", 30),
        f("調教師名略称", 8, "全角4文字"),
        f("調教師名欧字", 80),
        f("性別区分", 1, "1:男性 2:女性"),
        f("調教師東西所属コード", 1, "<コード表 2301.東西所属コード>参照。地方所属は 3"),
        f("招待地域名", 20, "地方では所属（大井・名古屋・ばんえい など）が入る"),
        grp("最近重賞勝利情報", 3, jusho_info(), "JV-Data の CH と同じ並び。観測した範囲では空"),
        grp("本年･前年･累計成績情報", 3, seiseki_kishu_chokyoshi(), "本年・前年・累計の順"),
        SEPARATOR])


def nn_items() -> list[Item]:
    """NN 馬主マスタ地方。JV-Data の BN に服色標示2つを足し、成績情報を広げたもの。"""
    return (COMMON + [
        f("馬主コード", 6, "000000 が多いので、馬主名(法人格無) と合わせて1件を決める", key=True),
        f("馬主名(法人格有)", 64),
        f("馬主名(法人格無)", 64, "", key=True),
        f("馬主名半角ｶﾅ", 50, "馬主コードが 000000 のときは空"),
        f("馬主名欧字", 100, "馬主コードが 000000 のときは空"),
        f("服色標示", 60, "JV-Data と同じ表記"),
        f("服色標示 ホッカイドウ（画像取得用）", 60, "観測した範囲ではほとんど空"),
        f("服色標示 ホッカイドウ（文字表示用）", 60, "観測した範囲では空"),
        grp("本年･累計成績情報", 2, seiseki_banushi_seisansha_116(), "本年・累計の順"),
        SEPARATOR])


def nb_items() -> list[Item]:
    """NB 生産者マスタ地方。DIFF でだけ配信され、生産者コードと名前が旧サイズ（6・70・70）。"""
    return (COMMON + [
        f("生産者コード", 6, "000000 が多いので、生産者名(法人格無) と合わせて1件を決める", key=True),
        f("生産者名(法人格有)", 70, "外国の生産者は欧字の名前がここに入る"),
        f("生産者名(法人格無)", 70, "", key=True),
        f("生産者名半角ｶﾅ", 70, "観測した範囲では空"),
        f("生産者名欧字", 168, "観測した範囲では空"),
        f("生産者住所自治省名", 20),
        grp("本年･累計成績情報", 2, seiseki_banushi_seisansha_116(), "本年・累計の順"),
        SEPARATOR])


def nd_items() -> list[Item]:
    """ND 出走別着度数地方。JV-Data の CK を地方の競馬場・距離区分に置き換えたもの。"""
    return (COMMON + RACE_KEY + [
        f("血統登録番号", 10, "NU 競走馬マスタ地方へリンク", key=True),
        f("馬名", 36, "全角18文字"),
        f("平地本賞金累計", 9, "単位：百円"),
        f("平地付加賞金累計", 9, "単位：百円"),
        f("平地収得賞金累計", 9, "単位：百円"),
        chaku("総合着回数"),
        chaku("地方合計着回数"),
    ] + [chaku(m + "・着回数") for m in MAWARI6]
      + [chaku(b + "・着回数") for b in BABA8]
      + [chaku("芝" + d + "・着回数") for d in DIST11]
      + [chaku("ダ" + d + "・着回数") for d in DIST11]
      + [chaku(v + "・着回数") for v in VENUES38]
      + [rep("脚質傾向", 3, 4, "逃げ回数、先行回数、差し回数、追込回数。観測した範囲では 0"),
         f("登録レース数", 3, "観測した範囲では 000"),
         f("騎手コード", 5, "NK 騎手マスタ地方へリンク"),
         f("騎手名", 34),
         grp("騎手本年･累計成績情報", 2, seiseki_nd_1524(), "本年・累計の順"),
         f("調教師コード", 5, "NC 調教師マスタ地方へリンク"),
         f("調教師名", 34),
         grp("調教師本年･累計成績情報", 2, seiseki_nd_1524(), "本年・累計の順"),
         f("馬主コード", 6, "NN 馬主マスタ地方へリンク。000000 が多い"),
         f("馬主名(法人格有)", 64),
         f("馬主名(法人格無)", 64),
         grp("馬主本年･累計成績情報", 2, seiseki_60(), "本年・累計の順"),
         f("生産者コード", 6, "NB 生産者マスタ地方へリンク。000000 が多い。旧サイズ（6桁）"),
         f("生産者名(法人格有)", 70, "旧サイズ（70バイト）"),
         f("生産者名(法人格無)", 70, "旧サイズ（70バイト）"),
         grp("生産者本年･累計成績情報", 2, seiseki_60(), "本年・累計の順"),
         SEPARATOR])


def ha_items() -> list[Item]:
    """HA 票数A（枠単）。南関東4場（浦和・船橋・大井・川崎）と金沢で配信される。"""
    return (COMMON + RACE_KEY + [
        f("登録頭数", 2),
        f("出走頭数", 2),
        f("発売フラグ　枠単", 1, "枠単発売の有無（0:発売なし 7:発売あり）。観測した範囲では 7"),
        rep("返還枠番情報(枠番1～8)", 1, 8, "（0:返還なし 1:返還あり）"),
        rep("返還同枠情報(枠番1～8)", 1, 8, "（0:返還なし 1:返還あり）"),
        grp("枠単票数", 64, [f("組番", 2, "1着枠番＋2着枠番"), f("票数", 11), f("人気順", 2)],
            "1着枠1〜8 × 2着枠1〜8 の順（11,12,…,18,21,…,88）。枠に1頭しかいない同枠の組と発売のない組は空白。"
            "取消などで対象外になった組は '-' 埋め"),
        f("枠単票数合計", 11, "枠単票数の和"),
        f("枠単返還票数合計", 11),
        SEPARATOR])


def oa_items() -> list[Item]:
    """OA オッズA（枠単）。HA と同じ競馬場で配信される。"""
    return (COMMON + RACE_KEY + [
        f("発表月日時分", 8, "mmddHHmm。時系列で貯めるときはこれも鍵に足す"),
        f("登録頭数", 2),
        f("出走頭数", 2),
        f("発売フラグ　枠単", 1, "枠単発売の有無（0:発売なし 7:発売あり）。観測した範囲では 7"),
        grp("枠単オッズ", 64, [f("組番", 2, "1着枠番＋2着枠番"), f("オッズ", 6, "0.1倍単位（021897 → 2189.7倍）"),
                           f("人気順", 2)],
            "1着枠1〜8 × 2着枠1〜8 の順（11,12,…,18,21,…,88）。枠に1頭しかいない同枠の組と発売のない組は空白。"
            "取消などで対象外になった組は '-' 埋め"),
        f("枠単票数合計", 11),
        SEPARATOR])


# ---------------------------------------------------------------- JV-Data を土台にするレコード


def hr_items(jv_items: list[Item]) -> list[Item]:
    """HR 払戻。JV-Data の予備の位置に枠単が入る。"""
    items = copy.deepcopy(jv_items)
    renamed = {36: ("不成立フラグ　枠単", "枠単不成立の有無（0:不成立なし 1:不成立あり）"),
               45: ("特払フラグ　枠単", "枠単特払の有無（0:特払なし 1:特払あり）"),
               54: ("返還フラグ　枠単", "枠単返還の有無（0:返還なし 1:返還あり）")}
    out: list[Item] = []
    for it in items:
        if it["offset"] in renamed and it["name"] == "予備":
            it["name"], it["comment"] = renamed[it["offset"]]
        if it["offset"] == 405 and it["name"] == "予備":
            out.append(grp("枠単払戻", 3, [f("組番", 2, "1着枠番＋2着枠番"), f("払戻金", 9), f("人気順", 2)],
                           "JV-Data の 予備(16×3) の位置。3同着まで考慮し繰返し3回"))
            out.append(f("予備", 9))
            continue
        out.append(it)
    return out


def wf_items(jv_items: list[Item]) -> list[Item]:
    """WF 重勝式。予備の1バイトが式別コードになり、組番の表し方が違う。"""
    out: list[Item] = []
    for it in copy.deepcopy(jv_items):
        if it["offset"] == 19 and it["name"] == "予備":
            out.append(f("予備", 1))
            out.append(f("式別コード", 1, "重勝式の式別。観測した範囲では 1（3レースの馬単を当てる重勝式）のみ"))
            continue
        if it["name"] == "重勝式対象レース情報":
            it["comment"] = "重勝式対象レースを設定。3レースの重勝式では4・5番目が 00 埋め"
        if it["name"] == "重勝式払戻情報":
            for c in it["children"]:
                if c["name"] == "組番":
                    c["comment"] = ("16進表記の数。10進に直すと「1着馬番2桁＋2着馬番2桁」を対象レースの順に並べた数になる"
                                    "（3レースなら12桁。0997E40C8D → 041203010701 → 4-12, 3-1, 7-1）")
        out.append(it)
    return out


# ---------------------------------------------------------------- 組み立て


def number_items(items: list[Item], base: int = 0) -> list[Item]:
    """項番とバイト位置（0始まり）を順に振る。繰返しブロックの中は先頭からの相対位置。"""
    out: list[Item] = []
    offset = base
    for no, it in enumerate(items, 1):
        item = {"no": str(no), "name": it["name"], "offset": offset, "size": it["size"],
                "repeat": it["repeat"], "is_key": it["is_key"], "default": it["default"],
                "comment": it["comment"]}
        if it.get("children"):
            item["children"] = number_children(it["children"], str(no))
        out.append(item)
        offset += it["size"] * it["repeat"]
    return out


def number_children(children: list[Item], parent_no: str) -> list[Item]:
    """繰返しブロックの内訳。項番は親の項番＋英字。"""
    out: list[Item] = []
    offset = 0
    for i, c in enumerate(children):
        out.append({"no": f"{parent_no}{chr(ord('a') + i % 26)}", "name": c["name"], "offset": offset,
                    "size": c["size"], "repeat": c["repeat"], "is_key": False, "default": c["default"],
                    "comment": c["comment"]})
        offset += c["size"] * c["repeat"]
    return out


def layout(index: str, title: str, record_id: str, items: list[Item], expected: int) -> dict[str, Any]:
    """レコード1つぶんのレイアウト。長さが実データのレコード長と合わなければ止める。"""
    numbered = number_items(items)
    length = sum(it["size"] * it["repeat"] for it in numbered)
    if length != expected:
        raise SystemExit(f"{record_id}: レイアウトの長さ {length} が実データのレコード長 {expected} と合いません")
    return {"index": index, "title": title, "record_id": record_id, "length": length, "items": numbered}


def jv_layout(jv: dict[str, Any], record_id: str) -> dict[str, Any]:
    for lay in jv["layouts"]:
        if lay["record_id"] == record_id:
            return lay
    raise SystemExit(f"JV-Data のレイアウトに {record_id} がありません")


def dataspecs() -> list[dict[str, Any]]:
    """NVOpen / NVRTOpen に渡すデータ種別IDと、実データで確かめた中身。"""
    return [
        {"id": "RACE", "name": "レース情報", "categories": ["蓄積系", "セットアップ"],
         "record_ids": ["RA", "SE", "HR", "H1", "H6", "O1", "O2", "O3", "O4", "O5", "O6", "HA", "OA", "WF"]},
        {"id": "DIFN", "name": "蓄積情報（新サイズ）", "categories": ["蓄積系", "セットアップ"],
         "record_ids": ["BN", "CH", "KS", "NC", "NK", "NN", "NU"]},
        {"id": "DIFF", "name": "蓄積情報（旧サイズ）", "categories": ["蓄積系", "セットアップ"],
         "record_ids": ["BN", "CH", "KS", "NB", "NC", "NK", "NN", "NU"]},
        {"id": "SNAP", "name": "出走時点情報", "categories": ["蓄積系", "セットアップ"], "record_ids": ["ND"]},
        {"id": "0B11", "name": "速報馬体重", "categories": ["速報系"], "record_ids": ["WH"]},
        {"id": "0B12", "name": "速報成績", "categories": ["速報系"], "record_ids": ["RA", "SE", "HR"]},
        {"id": "0B14", "name": "速報開催情報", "categories": ["速報系"], "record_ids": ["WE", "AV"]},
        {"id": "0B15", "name": "速報レース情報", "categories": ["速報系"], "record_ids": ["RA", "SE", "HR"]},
        {"id": "0B30", "name": "速報オッズ（全賭式）", "categories": ["速報系"],
         "record_ids": ["O1", "O2", "O3", "O4", "O5", "O6", "OA"]},
        {"id": "0B31", "name": "速報オッズ（単複枠）", "categories": ["速報系"], "record_ids": ["O1"]},
        {"id": "0B32", "name": "速報オッズ（馬連）", "categories": ["速報系"], "record_ids": ["O2"]},
        {"id": "0B33", "name": "速報オッズ（ワイド）", "categories": ["速報系"], "record_ids": ["O3"]},
        {"id": "0B34", "name": "速報オッズ（馬単）", "categories": ["速報系"], "record_ids": ["O4"]},
        {"id": "0B35", "name": "速報オッズ（3連複）", "categories": ["速報系"], "record_ids": ["O5"]},
        {"id": "0B36", "name": "速報オッズ（3連単）", "categories": ["速報系"], "record_ids": ["O6"]},
        {"id": "0B41", "name": "時系列オッズ（単複枠）", "categories": ["速報系"], "record_ids": ["O1"]},
        {"id": "0B42", "name": "時系列オッズ（馬連）", "categories": ["速報系"], "record_ids": ["O2"]},
        {"id": "0B51", "name": "速報重勝式", "categories": ["速報系"], "record_ids": ["WF"]},
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jv-layouts", required=True, help="jvdata-store の layouts.json（HR・WF の土台に使う）")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    jv = json.loads(Path(args.jv_layouts).read_text(encoding="utf-8"))
    layouts = [
        layout("NV-1", "競走馬マスタ地方", "NU", nu_items(), 1492),
        layout("NV-2", "騎手マスタ地方", "NK", nk_items(), 5529),
        layout("NV-3", "調教師マスタ地方", "NC", nc_items(), 5098),
        layout("NV-4", "馬主マスタ地方", "NN", nn_items(), 709),
        layout("NV-5", "生産者マスタ地方", "NB", nb_items(), 649),
        layout("NV-6", "出走別着度数地方", "ND", nd_items(), 8179),
        layout("NV-7", "票数A（枠単）", "HA", ha_items(), 1032),
        layout("NV-8", "オッズA（枠単）", "OA", oa_items(), 693),
        layout("NV-9", "払戻", "HR", hr_items(jv_layout(jv, "HR")["items"]), 719),
        layout("NV-10", "重勝式", "WF", wf_items(jv_layout(jv, "WF")["items"]), 7215),
    ]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "version": "UmaConn 3.5.4 で配信された実データ（2026年7月〜10月）",
        "source": "PC-KEIBA テーブル定義書（nvd_*）と実データの照合",
        "layouts": layouts,
        "dataspecs": dataspecs(),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    for lay in layouts:
        print(f"{lay['record_id']} {lay['title']:<12} {lay['length']:>6} バイト {len(lay['items']):>3} 項目")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
