import numpy as np
import pymupdf


class PdfRenderer:
    def render(self, page: pymupdf.Page, dpi: int = 300) -> np.ndarray:
        if not 72 <= dpi <= 600:
            raise ValueError("DPI must be between 72 and 600")
        pix = page.get_pixmap(dpi=dpi, alpha=False, colorspace=pymupdf.csRGB)
        image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()
        # MuPDF keeps decoded page images in a store of up to 256 MB. Pages are
        # rendered once each, so that cache never pays off and only holds memory.
        pymupdf.TOOLS.store_shrink(100)
        return image
