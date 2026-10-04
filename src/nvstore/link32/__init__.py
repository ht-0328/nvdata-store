"""NV-Link を呼ぶ側。**32bit の Python で動かす。**

NV-Link（UmaConn）は 32bit の COM コンポーネントで、64bit のプロセスからは作れない。
ここにあるものは 32bit の Python（pywin32 入り）で ``python -m nvstore.link32`` として
動かし、読んだレコードを標準出力にフレーム（:mod:`nvstore.frame`）で流す。
64bit の本体は :class:`nvstore.link_process.LinkProcess` を通してこれを起動する。

このパッケージは標準ライブラリと pywin32 以外に依存しない。
"""
