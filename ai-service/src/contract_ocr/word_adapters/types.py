"""The one shared input shape every `WordSource` adapter takes: `Region`.

`Region` scopes an extraction call to one crop of one page — a whole table
fragment, or (for `VisionAdapter` in "cells" mode) a set of individual cell
boxes within it. It carries no text and no source-specific state, so the
same value can be handed to `NativeAdapter`, `OcrAdapter` or `VisionAdapter`
interchangeably.
"""

from __future__ import annotations

from dataclasses import dataclass

from contract_ocr.table_reconstruct.types import Bbox


@dataclass(frozen=True)
class Region:
    page: int
    bbox: Bbox
    # Only meaningful to `VisionAdapter(mode="cells")`: the individual cell
    # boxes to crop and read within `bbox`. `None` for every other adapter
    # and for `VisionAdapter(mode="region")`.
    cells: tuple[Bbox, ...] | None = None
