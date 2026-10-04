# NV-Link の呼び方

**NV-Link は JV-Link の名前を `JV` → `NV` に置き換えた COM コンポーネントです。** 呼ぶ順番も引数も戻り値も、
確かめた範囲では JV-Link インターフェース仕様書 4.9.0.1 のとおりに動きます。違うのは **32bit でしか作れない**ことと、
投票や動画のメソッドが追加されていることです。

## 基本情報

| | NV-Link | JV-Link（参考） |
| :--- | :--- | :--- |
| ProgID | `NVDTLabLib.NVLink` | `JVDTLab.JVLink` |
| 本体 | `C:\Windows\SysWOW64\NVDTLab.dll`（32bit） | 64bit 版あり |
| 設定画面 | `NVSetUIProperties()`、または `C:\UmaConn\chiho.k-ba\UmaConn設定.exe` | `JVSetUIProperties()` |
| 利用キー | 設定画面で登録。`m_servicekey` で登録の有無が分かる | 同じ |
| 保存先 | `m_savepath`（既定 `C:\UmaConn\chiho.k-ba\data\`） | `m_savepath` |
| バージョン | `m_NVLinkVersion`（UmaConn 3.5.4 で `0354`） | `m_JVLinkVersion` |

> [!CAUTION]
> **64bit のプロセスからは作れません**
>
> NV-Link は 32bit の DLL しかなく、64bit の Python や PowerShell から `Dispatch("NVDTLabLib.NVLink")` すると
> 「クラスが登録されていません」（`REGDB_E_CLASSNOTREG`）になります。**32bit のプロセスで呼んでください。**
> 32bit の PowerShell は `C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe`、32bit の Python は
> `uv python install cpython-3.12-windows-x86` で入ります（pywin32 は 32bit 版の wheel があります）。
> DuckDB には 32bit 版の wheel が無いので、**NV-Link を呼ぶ 32bit の処理と、DuckDB に書く 64bit の処理は別のプロセスに分ける**ことになります。
> レジストリに DLL サロゲートを設定して 64bit から呼ぶ方法が外部で紹介されていますが、UmaConn の更新で壊れるおそれがあるので勧めません。

## 呼び出しの順番

JV-Link と同じです。

```
NVInit("UNKNOWN")                 → 0
NVOpen(dataspec, fromtime, option, 0, 0, "")     蓄積系
  または NVRTOpen(dataspec, key)                速報系
  （NVStatus でダウンロードの進み具合を見る）
NVGets(buff, size, filename) を 0 が返るまで繰り返す
NVClose()
```

`NVOpen` は Python（pywin32）では `(戻り値, 読み込むファイル数, ダウンロードするファイル数, 最終ファイル時刻)` のタプルで返ります。
`NVGets` は `(バイト数, バイト列, ファイル名)` で、戻り値の意味も JV-Link と同じです。

| `NVGets` の戻り値 | 意味 | すること |
| ---: | :--- | :--- |
| 正の数 | 1レコード読めた。値はそのバイト数 | バイト列を先頭からその長さで切る |
| `-1` | ファイルの切り替わり | 続けて呼ぶ |
| `-3` | 次のファイルがまだダウンロード中 | 少し待って呼び直す |
| `0` | 全部読み終えた | `NVClose` |

実データでの観測: `NVOpen("RACE", "20261003000000", 1)` → `(0, 25, 24, "20261004231021")`。
2日分で25ファイル（レコード種別ごとに1日1ファイル）。読み出しは 13万レコードを約6分（ダウンロード込み）。

## メソッド一覧

`Get-Member` で見えたものです。取得に使うのは最初の表だけで、残りは本プロジェクトでは使いません。

| 取得 | 対応する JV-Link | 確かめた挙動 |
| :--- | :--- | :--- |
| `NVInit(sid)` | `JVInit` | `0` |
| `NVOpen(dataspec, fromtime, option, …)` | `JVOpen` | 上記。`-1` 該当なし、`-111` 種別不正、`-116` 組み合わせ不正 |
| `NVRTOpen(dataspec, key)` | `JVRTOpen` | `0`、`-1` 該当なし、`-111` 種別不正、`-114` キー不正 |
| `NVGets` / `NVRead` | `JVGets` / `JVRead` | `NVGets` は上記のとおり |
| `NVStatus` | `JVStatus` | 未使用 |
| `NVSkip` / `NVCancel` / `NVClose` | 同名 | `NVClose` は `0` |
| `NVFiledelete(filename)` | `JVFiledelete` | 未使用 |
| `NVSetSaveFlag` / `NVSetSavePath` / `NVSetServiceKey` / `NVSetUIProperties` | 同名 | `NVSetUIProperties` は設定画面を開き、閉じると `0` |
| `NVWatchEvent` / `NVWatchEventClose` | 同名 | 未使用 |
| `NVStarts` | （無し） | 未調査 |

| そのほか | 何か |
| :--- | :--- |
| `NVCourseFile` `NVCourseFile2` `NVFuku` `NVFukuFile` | コース図・勝負服の画像 |
| `NVMVCheck` `NVMVOpen` `NVMVPlay` `NVMVPlayWithType` `NVMVRead` | 動画 |
| `OddsParkLogin` `OddsParkBet` `OddsParkDeposit` `OddsParkZandaka` `OddsParkLogout` | オッズパークへの投票 |
| `RakutenLogin` `RakutenBet` `RakutenDeposit` `RakutenZandaka` `RakutenLogout` | 楽天競馬への投票 |
| `SPAT4Login` `SPAT4Bet` `SPAT4Deposit` `SPAT4Zandaka` `SPAT4Logout` | SPAT4 への投票 |

| プロパティ | 何か |
| :--- | :--- |
| `m_servicekey` | 利用キー。登録済みなら17文字 |
| `m_savepath` `m_saveflag` | 保存先と、ファイルを残すか |
| `m_payflag` | 有料会員か（未確認） |
| `m_NVLinkVersion` | バージョン |
| `m_CurrentFileTimeStamp` `m_CurrentReadFilesize` `m_TotalReadFilesize` | 読み出し中のファイルの情報 |
| `ParentHWnd` | 設定画面の親ウィンドウ |

## エラーコード

確かめられたのは `-1` `-111` `-114` `-116` で、いずれも JV-Link インターフェース仕様書「３．コード表」と同じ意味でした。
ほかのコード（`-301` 認証エラー、`-303` 利用キー未設定、`-502` ダウンロード失敗 など）も同じ表で読めるとみて設計し、
初めて見た値はログに残して確かめてください。

## 外部で報告されている注意点

本ドキュメントでは確かめていませんが、設計で備えておくべき報告です。

- **長く使い続けると COM の内部でメモリが漏れ、`NVRead` が `-1` を返し続ける**という報告があります。
  対策として「1日分ごとに別プロセスで取得し、終わったらプロセスを終える」方法が紹介されています。
  本プロジェクトは 32bit の取得処理をもともと別プロセスにするので、この形に合わせられます。
- 2005年からのセットアップは 96,000 ファイル以上です。`NVOpen` の返りに数分かかり、ダウンロードには長い時間がかかります。
  途中で止めると `NVFiledelete` で壊れたファイルを消してやり直す、という JV-Link と同じ手当てが要るとみてください。
