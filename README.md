# nvdata-store — 地方競馬DATA のデータを DuckDB に貯める（準備中）

地方競馬DATA（UmaConn / NV-Link 経由で配信される地方競馬のデータ）を、DuckDB に貯めるためのプロジェクトです。
中央競馬（JRA-VAN Data Lab.）向けの [`jvdata-store`](https://github.com/ht-0328/jvdata-store) と役割を分け、
**取得だけを担います。** 絞り込みと分析は読む側（`keiba-yosou`）の責務です。

**今あるのは、データの仕様書だけです。** 取得の仕組みはこの仕様書をもとに作ります。

## 仕様書

地方競馬DATA には公開された開発者向けの仕様書がありません。そこで、JV-Data仕様書・PC-KEIBA のテーブル定義書・
実際に UmaConn で受け取ったデータの3つを突き合わせて、仕様書を起こしました。ソースは [docs/](docs/index.md) にあります。

- [地方競馬DATA の全体像](docs/01-overview.md) — 何が配信され、どう受け取るか
- [レコードの読み方](docs/02-record-format.md) — JV-Data と同じところ・違うところ
- [データ種別と提供範囲](docs/03-dataspecs.md) — 何をいつ取れるか。セットアップの挙動
- [レコードのつながり](docs/04-relations.md) — 表の結合と鍵
- [NV-Link の呼び方](docs/05-nvlink-interface.md) — 32bit の COM をどう呼ぶか
- [レコード索引](docs/reference/index.md) / [地方特有のコード値](docs/reference/codes.md)

### 機械可読のレイアウト定義

[`spec/nv_layouts.json`](spec/nv_layouts.json) に、地方だけのレコード（NU NK NC NN NB ND HA OA）と、
JV-Data と中身が違うレコード（HR WF）のレイアウトがあります。形は jvdata-store の `layouts.json` と同じです。
JV-Data と同じ並びのレコード（RA SE H1 H6 O1〜O6 BN CH KS WH WE AV）は jvdata-store の定義をそのまま使います。

```powershell
# レイアウト定義を作り直す（HR・WF の土台に jvdata-store の定義を使う）
uv run --no-project --python 3.12 python tools/build_layouts.py --jv-layouts ..\jvdata-store\src\jvstore\resources\layouts.json

# 参照ページ（docs/reference/）を作り直す
uv run --no-project --python 3.12 python tools/gen_spec_docs.py
```

## 仕様書の確からしさ

項目名とバイト数の出どころは PC-KEIBA テーブル定義書で、並びと中身は 2026年7月〜10月に UmaConn で受け取った
実データ（レース情報 13万件、マスタ 11万件、出走別着度数 1.6万件）で確かめています。
確かめ方は各レコードのページの末尾にあります。推定にとどまる箇所は、その旨を書いています。

> [!IMPORTANT]
> 地方競馬DATA のデータは契約者向けの配信物です。実データそのもの（馬名・オッズ・払戻など）はこのリポジトリに置きません。
> ドキュメントの例は、構造が分かる最小限にとどめ、値は伏せるか作り物にしています。
