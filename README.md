# nvdata-store — 地方競馬DATA のデータを DuckDB に貯める

地方競馬DATA（UmaConn / NV-Link 経由で配信される地方競馬のデータ）を、**レコードの表単位で DuckDB に貯める**ツールです。
中央競馬（JRA-VAN Data Lab.）向けの [`jvdata-store`](https://github.com/ht-0328/jvdata-store) と役割を分け、
**取得だけを担います。** 絞り込みと分析は読む側（`keiba-yosou`）の責務です。

表の作り方と列名は jvdata-store と同じです。地方のデータは `nvdata.duckdb`（既定）に入り、中央の `jvdata.duckdb` とは別のファイルになります。

> [!TIP]
> **地方競馬DATA のデータの仕様は [ドキュメントサイト](docs/index.md) にまとめてあります。**
> 提供元に公開の仕様書が無いので、JV-Data仕様書・PC-KEIBA テーブル定義書・実データを突き合わせて起こしたものです。

## 使うまでに要るもの

| 要るもの | 補足 |
| :--- | :--- |
| 地方競馬DATA の契約と利用キー | 月額の会員登録で発行される |
| UmaConn のインストール | NV-Link（32bit の COM）と設定画面が入る |
| 利用キーの登録 | 画面の「UmaConn設定」か `uv run nvstore setup` で設定画面を開いて登録する |
| uv | 本体（64bit）と、NV-Link を呼ぶ 32bit の Python を用意する |

**NV-Link は 32bit でしか動かず、DuckDB は 32bit で動きません。** そのため本ツールは、NV-Link を呼ぶ小さな 32bit の取得プロセスと、
DuckDB に書く 64bit の本体に分かれています。32bit の Python（`cpython-3.12-windows-x86` と pywin32）は、初回に uv が自動で用意します。
uv を使わないときは、環境変数 `NVSTORE_PYTHON32` に pywin32 入りの 32bit の python.exe を指定してください。

## 画面で取得する

**このフォルダの [`run.bat`](run.bat) をダブルクリック**してください。操作パネル（小さなウィンドウ）が開き、
サーバーが止まっていれば起動して、ブラウザで取得・管理画面を開きます。使い方は jvdata-store と同じで、
画面右上の「使い方」にも書いてあります。

1. 利用キーが未登録なら「UmaConn設定」で登録します（設定画面はこの PC に開きます）。
2. 年数（1〜40年）とデータ種別を選び、「取得する」を押します。
3. 取得後は表を選んで件数・期間・中身を確認できます。

```powershell
# 保存先とポートを変える（既定はこのフォルダの nvdata.duckdb と 8767。jvdata-store の 8766 と同時に開ける）
run.bat --db D:\keiba\nvdata.duckdb --port 9001
```

通常は初回に指定年数のうち提供されている範囲（2005年〜）を取り、2回目以降は差分を更新します。
期間を広げるときは「期間を広げて再取得する」にチェックしてください。

> [!IMPORTANT]
> **セットアップは年ごとに区切れません。** NV-Link は読み出し終了時刻を無視するので、指定した年から今までを一度に開きます。
> 2005年からの全期間はレース情報だけで約 96,000 ファイルあり、数時間かかります。途中で止めず、終わるまで待ってください。

## コマンドで取得する

```powershell
uv sync

# 過去10年ぶんの蓄積系データ（RACE DIFN SNAP DIFF）をまとめて取る
uv run nvstore sync --years 10 --db nvdata.duckdb

# 件数だけ先に確認する / 種別を絞る
uv run nvstore sync --years 10 --dry-run
uv run nvstore sync --years 3 --dataspec RACE,DIFN

# 開催日の速報（出馬表・成績・馬体重・天候馬場・取消・全賭式のオッズ）を取る。realtime_today.bat は今日の分を取る
uv run nvstore realtime --date 2026-10-04

# 1回ぶんだけ取って中身を確かめる
uv run nvstore fetch --dataspec RACE --from 20261001000000 --db check.duckdb
uv run nvstore rt --dataspec 0B30 --key 2026100444100101 --db check.duckdb

# 利用キーの登録の有無・保存先・UmaConn のバージョン
uv run nvstore info
```

## 取得する範囲

| データ種別ID | 内容 | 収録される表 |
| --- | --- | --- |
| `RACE` | レース情報 | RA SE HR H1 H6 O1〜O6 HA OA WF |
| `DIFN` | マスタ | NU KS NK CH NC BN NN |
| `SNAP` | 出走別着度数地方 | ND |
| `DIFF` | 生産者マスタ地方 | NB（**この種別からは NB だけを取り込みます**。ほかの表は DIFN より短い旧サイズで届くため） |

速報（`realtime`）は、開催日単位の `0B15` `0B14` `0B11` `0B51` と、その日の全レースの `0B30`（全賭式のオッズ。枠単発売場は枠単も）です。
何が届いて何が届かないかは [データ種別と提供範囲](docs/03-dataspecs.md) にあります。

## 中身の読み方

値は仕様の桁のままの文字列で入ります（`競馬場コード='54'`、`単勝オッズ='0360'`）。地方特有の読み方が3つあります。

- ばんえい（競馬場コード `83`）の負担重量・馬体重は **16進**。
- 発売のない組のオッズ・票数は `*` 埋め（取消は `-` 埋め）。
- 馬主コード・生産者コードが `000000` の馬主・生産者が多く、名前と合わせて引く。

くわしくは [レコードの読み方](docs/02-record-format.md) と [地方特有のコード値](docs/reference/codes.md) にあります。

## 開発

```powershell
uv run pytest -q

# レイアウト定義（src/nvstore/resources/nv_layouts.json）を作り直す。HR・WF の土台に jvdata-store の定義を使う
uv run --no-project --python 3.12 python tools/build_layouts.py --jv-layouts ..\jvdata-store\src\jvstore\resources\layouts.json

# 参照ページ（docs/reference/）を作り直す
uv run --no-project --python 3.12 python tools/gen_spec_docs.py
```

レコードの解釈・DuckDB への書き込み・画面の部品は、依存パッケージとして入れた jvdata-store（`jvstore`）のものを使っています。
地方だけの違い（レイアウトの上書き・32bit の取得プロセス・データ種別・DIFF の絞り込み）だけがこのリポジトリにあります。

> [!IMPORTANT]
> 地方競馬DATA のデータは契約者向けの配信物です。実データそのもの（馬名・オッズ・払戻など）はこのリポジトリに置きません。
> ドキュメントの例は、構造が分かる最小限にとどめ、値は伏せるか作り物にしています。
