"""地方競馬DATA のレイアウト定義。JV-Data の定義に、地方の定義を重ねて作る。

JV-Data と同じ並びのレコード（RA SE H1 H6 O1〜O6 BN CH KS WH WE AV …）は、
jvdata-store 同梱の JV-Data仕様書 4.9.0.1 の定義をそのまま使う。
地方だけのレコード（NU NK NC NN NB ND HA OA）と、JV-Data と中身が違うレコード
（HR WF）は、同梱の ``nv_layouts.json``（``tools/build_layouts.py`` で生成）で上書きする。
データ種別の一覧は地方のものだけにする。
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from pathlib import Path

from jvstore.layout import LayoutSet, load_layouts as load_jv_layouts

__all__ = ["load_layouts"]

_RESOURCE = "nv_layouts.json"


def load_layouts(path: Path | None = None) -> LayoutSet:
    """地方競馬DATA のレイアウト定義。``path`` を省くと同梱の定義を使う。"""
    if path is None:
        return _bundled_layouts()
    return _merge(json.loads(Path(path).read_text(encoding="utf-8")))


@cache
def _bundled_layouts() -> LayoutSet:
    resource = resources.files("nvstore.resources").joinpath(_RESOURCE)
    return _merge(json.loads(resource.read_text(encoding="utf-8")))


def _merge(nv_data: dict) -> LayoutSet:
    jv = load_jv_layouts()
    nv = LayoutSet.from_dict(nv_data)
    return LayoutSet(
        version=nv.version,
        source=nv.source,
        layouts={**jv.layouts, **nv.layouts},
        dataspecs=nv.dataspecs,
    )
