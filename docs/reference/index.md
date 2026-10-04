# レコード索引

地方競馬DATA（NV-Data）で届くレコードの一覧です。実データで確かめた範囲を載せています。

## 地方だけのレコード・JV-Data と中身が違うレコード

`spec/nv_layouts.json` から生成しています。

| ID | 名前 | レコード長 | 項目数 | 届くデータ種別 | キー |
| :--- | :--- | ---: | ---: | :--- | :--- |
| [NU](NU.md) | 競走馬マスタ地方 | 1,492 | 55 | DIFN DIFF | 血統登録番号 |
| [NK](NK.md) | 騎手マスタ地方 | 5,529 | 27 | DIFN DIFF | 騎手コード |
| [NC](NC.md) | 調教師マスタ地方 | 5,098 | 18 | DIFN DIFF | 調教師コード |
| [NN](NN.md) | 馬主マスタ地方 | 709 | 13 | DIFN DIFF | 馬主コード、馬主名(法人格無) |
| [NB](NB.md) | 生産者マスタ地方 | 649 | 11 | DIFF | 生産者コード、生産者名(法人格無) |
| [ND](ND.md) | 出走別着度数地方 | 8,179 | 107 | SNAP | 開催年、開催月日、競馬場コード、開催回[第N回]、開催日目[N日目]、レース番号、血統登録番号 |
| [HA](HA.md) | 票数A（枠単） | 1,032 | 18 | RACE | 開催年、開催月日、競馬場コード、開催回[第N回]、開催日目[N日目]、レース番号 |
| [OA](OA.md) | オッズA（枠単） | 693 | 16 | RACE 0B30 | 開催年、開催月日、競馬場コード、開催回[第N回]、開催日目[N日目]、レース番号 |
| [HR](HR.md) | 払戻 | 719 | 52 | RACE 0B12 0B15 | 開催年、開催月日、競馬場コード、開催回[第N回]、開催日目[N日目]、レース番号 |
| [WF](WF.md) | 重勝式 | 7,215 | 18 | RACE 0B51 | 開催年、開催月日 |

## JV-Data と同じ並びのレコード

レコード長が JV-Data仕様書 4.9.0.1 と一致し、日付・コード・数値の項目が同じ位置で読めることを実データで確かめました。
項目の説明は [jvdata-store のドキュメント](https://ht-0328.github.io/jvdata-store/) を見てください。
コード値の一部は地方特有です（[地方特有のコード値](codes.md)）。

| ID | 名前 | レコード長 | 届くデータ種別 | 地方での注意 |
| :--- | :--- | ---: | :--- | :--- |
| [RA](https://ht-0328.github.io/jvdata-store/reference/RA/) | レース詳細 | 1,272 | RACE 0B12 0B15 | コード値の一部が地方特有（コード表のページ） |
| [SE](https://ht-0328.github.io/jvdata-store/reference/SE/) | 馬毎レース情報 | 555 | RACE 0B12 0B15 | ばんえいの負担重量・馬体重は16進 |
| [H1](https://ht-0328.github.io/jvdata-store/reference/H1/) | 票数1 | 28,955 | RACE | 発売のない組は '*' 埋め |
| [H6](https://ht-0328.github.io/jvdata-store/reference/H6/) | 票数6（3連単） | 102,890 | RACE |  |
| [O1](https://ht-0328.github.io/jvdata-store/reference/O1/) | オッズ1（単複枠） | 962 | RACE 0B30 0B31 0B41 | 発売のない組は '*' 埋め |
| [O2](https://ht-0328.github.io/jvdata-store/reference/O2/) | オッズ2（馬連） | 2,042 | RACE 0B30 0B32 0B42 |  |
| [O3](https://ht-0328.github.io/jvdata-store/reference/O3/) | オッズ3（ワイド） | 2,654 | RACE 0B30 0B33 |  |
| [O4](https://ht-0328.github.io/jvdata-store/reference/O4/) | オッズ4（馬単） | 4,031 | RACE 0B30 0B34 |  |
| [O5](https://ht-0328.github.io/jvdata-store/reference/O5/) | オッズ5（3連複） | 12,293 | RACE 0B30 0B35 |  |
| [O6](https://ht-0328.github.io/jvdata-store/reference/O6/) | オッズ6（3連単） | 83,285 | RACE 0B30 0B36 | 発売のない組は '*' 埋め |
| [BN](https://ht-0328.github.io/jvdata-store/reference/BN/) | 馬主マスタ | 477 | DIFN DIFF | 馬主コードが 000000 の馬主が多い |
| [CH](https://ht-0328.github.io/jvdata-store/reference/CH/) | 調教師マスタ | 3,862 | DIFN DIFF |  |
| [KS](https://ht-0328.github.io/jvdata-store/reference/KS/) | 騎手マスタ | 4,173 | DIFN DIFF |  |
| [WH](https://ht-0328.github.io/jvdata-store/reference/WH/) | 馬体重 | 847 | 0B11 |  |
| [WE](https://ht-0328.github.io/jvdata-store/reference/WE/) | 天候馬場状態 | 42 | 0B14 |  |
| [AV](https://ht-0328.github.io/jvdata-store/reference/AV/) | 出走取消・競走除外 | 78 | 0B14 |  |

## 届かないレコード

JV-Data にあって、観測した範囲（2026年7月〜10月の蓄積系と速報系）では一度も届かなかったレコードです。

| ID | 名前 | 補足 |
| :--- | :--- | :--- |
| UM | 競走馬マスタ | 地方は NU が代わり。PC-KEIBA は nvd_um を定義しているが、DIFN・DIFF のどちらにも入ってこなかった |
| BR | 生産者マスタ | 地方は NB が代わり |
| CK | 出走別着度数 | 地方は ND が代わり |
| TK HN SK RC HC HS HY YS BT CS DM TM JG WC | 特別登録・血統・調教・マイニング・開催スケジュール など | 対応するデータ種別が「該当データ無し」か「不正」になる |
| JC TC CC | 騎手変更・発走時刻変更・コース変更 | 0B14 に含まれる可能性はあるが、観測した日には出なかった |
