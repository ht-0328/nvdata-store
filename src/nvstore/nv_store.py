"""DuckDB への書き込み。jvdata-store の DuckStore を、幅の広い子テーブルでも速く書けるようにしたもの。

地方の出走別着度数（ND）の騎手・調教師の成績情報は、子テーブルが 383 列ある。
DuckStore は子テーブルに入れるとき、同じ鍵と連番の行を1つに絞るために
``row_number() OVER (PARTITION BY …)`` を **全列を並べたまま** 計算する。
幅が広いとこれが重く、2,000 件の書き込みで 23 秒かかり（INSERT そのものは 1 秒）、
10 年分の取り込みが半日かかっても終わらなかった。

ここでは、残す行を **鍵と連番と版の列だけ** で先に決め（rowid の最小値）、
その行だけを全列で写す。結果は DuckStore と同じ（同じ鍵・連番が1行、親の勝った版の子だけ）。
"""

from __future__ import annotations

from jvstore.store import SEQ_COLUMN, VERSION_COLUMN, ChildSpec, DuckStore, TableSpec, _quoted

__all__ = ["NvStore"]


class NvStore(DuckStore):
    """子テーブルへの書き込みだけを、幅の広い表でも速い形に差し替えた DuckStore。"""

    def _merge_child(self, spec: TableSpec, child: ChildSpec) -> None:
        rows = self._rows.get(child.table)
        table = _quoted(child.table)
        # 親が入れ替わったら子は丸ごと入れ替える。頭数が減ったときに前回の組が残るのを防ぐ。
        parent_on = self._join_condition(spec.keys, "t", "s")
        self.con.execute(f"DELETE FROM {table} t USING tmp_won s WHERE {parent_on}")
        if not rows:
            return
        columns = spec.child_columns(child)
        self._insert("tmp_child", columns + [VERSION_COLUMN], rows, seq_index=len(spec.keys))
        group = ", ".join(f"c.{_quoted(key)}" for key in spec.keys + [SEQ_COLUMN])
        join = self._join_condition(spec.keys, "c", "w")
        version = _quoted(VERSION_COLUMN)
        # 親の勝った版に対応する子のうち、鍵と連番ごとに最初の1行だけを残す。狭い列だけで決める。
        self.con.execute(
            f"CREATE OR REPLACE TEMP TABLE tmp_keep AS SELECT min(c.rowid) AS kept FROM tmp_child c "
            f"JOIN tmp_won w ON {join} AND c.{version} = w.{version} GROUP BY {group}"
        )
        select = ", ".join(f"c.{_quoted(column)}" for column in columns)
        self.con.execute(
            f"INSERT INTO {table} SELECT {select} FROM tmp_child c SEMI JOIN tmp_keep k ON c.rowid = k.kept"
        )
        self.con.execute("DROP TABLE tmp_keep")
        self.con.execute("DROP TABLE tmp_child")
        rows.clear()
