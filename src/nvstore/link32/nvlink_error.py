"""NV-Link が負の戻り値を返したときの例外と、コードの説明。"""

from __future__ import annotations

__all__ = ["NVLinkError", "describe_error"]

#: JV-Link インターフェース仕様書「３．コード表」の主要コード。NV-Link も同じ意味で返す
#: （実データで確かめたのは -1 -111 -114 -116）。
_ERRORS: dict[int, str] = {
    -1: "該当データ無し",
    -2: "セットアップダイアログでキャンセルが押された",
    -111: "dataspec パラメータが不正",
    -112: "fromtime パラメータが不正（読み出し開始ポイント時刻不正）",
    -113: "fromtime パラメータが不正（読み出し終了ポイント時刻不正）",
    -114: "key パラメータが不正",
    -115: "option パラメータが不正",
    -116: "dataspec と option の組み合わせが不正",
    -118: "filepath パラメータが不正",
    -201: "NVInit が行われていない",
    -202: "前回の NVOpen/NVRTOpen に対して NVClose が呼ばれていない（オープン中）",
    -203: "NVOpen が行われていない",
    -211: "レジストリ内容が不正",
    -301: "認証エラー（利用キーが正しくない／複数マシンでの同一キー使用）",
    -302: "利用キーの有効期限切れ",
    -303: "利用キーが設定されていない（UmaConn の設定画面で利用キーを登録してください）",
    -305: "利用規約に同意していない（UmaConn の設定画面で同意してください）",
    -401: "NV-Link 内部エラー",
    -402: "ダウンロードしたファイルが異常（ファイルサイズ＝0）",
    -403: "ダウンロードしたファイルが異常（データ内容）",
    -411: "サーバーエラー（HTTP 404 NotFound）",
    -412: "サーバーエラー（HTTP 403 Forbidden）",
    -413: "サーバーエラー（HTTP 200,403,404 以外）",
    -421: "サーバーエラー（サーバーの応答が不正）",
    -431: "サーバーエラー（サーバーアプリケーション内部エラー）",
    -501: "セットアップ処理においてスタートキットが無効",
    -502: "ダウンロード失敗（通信エラーやディスクエラーなど）",
    -503: "ファイルが見つからない",
    -504: "サーバーメンテナンス中",
}


def describe_error(code: int) -> str:
    return _ERRORS.get(code, "未定義のエラーコード")


class NVLinkError(RuntimeError):
    """NV-Link が負の戻り値を返した。``func`` はメソッド名、``code`` は戻り値。"""

    def __init__(self, func: str, code: int, message: str = "") -> None:
        super().__init__(message or f"{func} エラー: {code} ({describe_error(code)})")
        self.func = func
        self.code = code
