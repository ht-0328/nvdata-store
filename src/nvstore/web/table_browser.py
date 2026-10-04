"""取り込んだ表を覗く読み取り口。中身は jvdata-store のものと同じで、表の名前だけ地方の定義で引く。"""

from __future__ import annotations

from jvstore.web.tables import TableBrowser

from ..layouts import load_layouts

#: 親テーブルと繰返しブロックの子テーブルを区切る文字列（`ha__枠単票数`）。
_BLOCK_SEPARATOR = "__"

TABLES = {record_id.lower(): layout.title for record_id, layout in load_layouts().layouts.items()}


class NvTableBrowser(TableBrowser):
    """地方のレコード（nu・nk・ha …）にも表の名前が付くようにした TableBrowser。"""

    @staticmethod
    def _title(name: str) -> str:
        parent, _, block = name.partition(_BLOCK_SEPARATOR)
        title = TABLES.get(parent, parent.upper())
        return f"{title} › {block}" if block else title
