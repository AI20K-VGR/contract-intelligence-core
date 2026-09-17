from collections import defaultdict

import pymupdf
import pytesseract
from PIL import Image

from app.domain import require


def process_page(payload, config, store):
    with pymupdf.open(store.path(payload["storage_key"])) as pdf:
        page = pdf[payload["page_number"] - 1]
        scale = config["dpi"] / 72
        require(
            page.rect.width * page.rect.height * scale * scale <= config["max_pixels"],
            "PIXEL_BUDGET_EXCEEDED",
            422,
        )
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        image_key = store.put(pix.tobytes("png"), "png")
        raw_words = page.get_text("words", sort=True)
        # Any embedded image makes native coverage uncertain: OCR the rendered page once.
        native = bool(raw_words) and not page.get_images()
        groups = defaultdict(list)
        if native:
            for word in raw_words:
                box = pymupdf.Rect(word[:4]) * page.rotation_matrix
                groups[(word[5], word[6])].append(
                    {
                        "text": word[4],
                        "bbox": [
                            box.x0 / page.rect.width,
                            box.y0 / page.rect.height,
                            box.x1 / page.rect.width,
                            box.y1 / page.rect.height,
                        ],
                    }
                )
            engine = "pymupdf"
        else:
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            data = pytesseract.image_to_data(
                image,
                lang=config["ocr_languages"],
                output_type=pytesseract.Output.DICT,
                timeout=config["ocr_timeout_seconds"],
            )
            for i, text in enumerate(data["text"]):
                if not text.strip():
                    continue
                x, y, w, h = (data[key][i] for key in ("left", "top", "width", "height"))
                groups[(data["block_num"][i], data["par_num"][i], data["line_num"][i])].append(
                    {
                        "text": text,
                        "bbox": [
                            x / pix.width,
                            y / pix.height,
                            (x + w) / pix.width,
                            (y + h) / pix.height,
                        ],
                    }
                )
            engine = "tesseract"
        lines = []
        for words in groups.values():
            text = " ".join(w["text"] for w in words)
            boxes = [w["bbox"] for w in words]
            lines.append(
                {
                    "id": f"{payload['document_id']}:{payload['page_number']}:{len(lines)}",
                    "text": text,
                    "words": words,
                    "bbox": [
                        min(b[0] for b in boxes),
                        min(b[1] for b in boxes),
                        max(b[2] for b in boxes),
                        max(b[3] for b in boxes),
                    ],
                }
            )
        # OCR empty output is not proof of a blank page.
        return {
            **payload,
            "width": pix.width,
            "height": pix.height,
            "rotation": page.rotation,
            "image_key": image_key,
            "lines": lines,
            "engine": engine,
            "status": "completed" if lines else "needs_review",
            "issue": None if lines else "EMPTY_OCR_REQUIRES_REVIEW",
        }
