"""Input/output JSON contracts.

`block` and `page` (the OCR input contract) have no dependency on the rest
of reconstruction and are re-exported here for convenience. `document` (the
output contract) depends on `..models` — import it directly
(`from .schemas.document import Clause`) rather than through this package,
to avoid a circular import through `..models`.
"""

from .block import Block
from .page import Page

__all__ = ["Block", "Page"]
