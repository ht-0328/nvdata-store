"""nvstore — 地方競馬DATA（UmaConn / NV-Link）のデータを DuckDB に貯める。

このパッケージの入口（``__init__``）では何も読み込まない。32bit の取得プロセス
（:mod:`nvstore.link32`）も同じパッケージを使うので、DuckDB など 64bit でしか
入らないものをここで読み込むと、32bit 側が起動できなくなる。
"""
