import re
import unicodedata

# Shared with facts.py: the nearest preceding header establishes which clause a fact
# or fragment belongs to, and comparison.py requires both sides of a pair to share it
# before treating them as comparable.
#
# Matched against strip_diacritics(text), not the raw line, so "Dieu 1." matches
# exactly like "Điều 1." does — a real scanned contract routinely loses its diacritics
# entirely (a degraded scan, a legacy TCVN3/VNI font whose bytes decode to the wrong
# codepoints, or ASCII-only source text), and _nfc() upstream only fixes a DIFFERENT
# problem (decomposed vs. precomposed accents on text that already has them) — it does
# nothing for text that never had diacritics to begin with. Written in their
# diacritic-stripped form here since strip_diacritics runs before every match.
ARTICLE_PATTERN = re.compile(r"^(Dieu|Article)\s+(\d+)", re.IGNORECASE)
# "1. ..." / "1) ..." or explicit "Khoan 1. ...". Requires the digits to be immediately
# followed by the "." or ")" (no space), so amounts like "100.000.000 VND" and bare
# "30 days" don't match.
CLAUSE_PATTERN = re.compile(r"^(?:Khoan\s+)?(\d{1,2})[.\)]\s+\S", re.IGNORECASE)
# "a) ..." / "a. ..." or explicit "Diem a) ...". Only checked once article/clause have
# both failed, so a stray leading letter can't be mistaken for a higher level.
POINT_PATTERN = re.compile(r"^(?:Diem\s+)?([a-z])[.\)]\s+\S", re.IGNORECASE)


def strip_diacritics(text):
    """Vietnamese-diacritic-insensitive form of `text`: "Điều"/"Khoản"/"Điểm" and
    their ASCII-only equivalents ("Dieu"/"Khoan"/"Diem") both reduce to the same
    string, so ARTICLE_PATTERN/CLAUSE_PATTERN/POINT_PATTERN only need to know one
    spelling. Reused by facts.py, which shares ARTICLE_PATTERN.
    """
    decomposed = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))
# A fragment ending in one of these reads as a complete sentence: nothing that follows
# should be glued onto it. Without one, the fragment is assumed to still be mid-sentence
# (e.g. wrapped onto the next line by the PDF's own layout).
_SENTENCE_END_PATTERN = re.compile(r"[.!?:;]\s*$")
# A new bullet/dash item, or a line that clearly opens a fresh sentence (leading
# uppercase), never continues the previous fragment even when it lacked terminal
# punctuation — only a plain lowercase continuation does.
_NEW_FRAGMENT_START_PATTERN = re.compile(r"^[-•*+]\s|^[A-ZÀ-Ỹ]")


def clauses(pages, run_id):
    """Three-level hierarchy per document: article ("Điều/Article N") > clause
    ("Khoản N" / a leading "N.") > point ("Điểm x" / a leading "x)"). Any other
    line attaches as a "fragment" under the deepest node currently open for its
    document, so running text between headers still traces back to a clause.

    Two consecutive fragments under the same node are merged into one — keeping
    every source line's citation — when the first doesn't end a sentence and the
    second doesn't look like a new sentence or bullet: this is what lets a clause
    that the PDF wrapped across two (or more) lines display as one continuous
    sentence instead of scattered, half-finished rows.

    Regex-only: cross-page continuation is simple ordering, and numbering that
    doesn't follow this exact "N." / "x)" shape (roman numerals, "1.1", inline
    lettering) is not recognized and falls back to "fragment".
    """
    result = []
    open_node = {}
    for page in pages:
        document_id = page["document_id"]
        state = open_node.setdefault(document_id, {"article": None, "clause": None, "point": None})
        for line in page["lines"]:
            text = line["text"]
            normalized = strip_diacritics(text)
            node_id = f"clause:{line['id']}"
            citation_id = f"{run_id}:{line['id']}"
            article = ARTICLE_PATTERN.match(normalized)
            clause = None if article else CLAUSE_PATTERN.match(normalized)
            point = None if article or clause else POINT_PATTERN.match(normalized)
            if article:
                state["article"], state["clause"], state["point"] = node_id, None, None
                parent_id = None
                node_type = "article"
            elif clause and state["article"]:
                state["clause"], state["point"] = node_id, None
                parent_id = state["article"]
                node_type = "clause"
            elif point and (state["clause"] or state["article"]):
                state["point"] = node_id
                parent_id = state["clause"] or state["article"]
                node_type = "point"
            elif state["article"]:
                parent_id = state["point"] or state["clause"] or state["article"]
                node_type = "fragment"
            else:
                continue

            previous = result[-1] if result else None
            continues_previous = (
                node_type == "fragment"
                and previous is not None
                and previous["type"] == "fragment"
                and previous["parent_id"] == parent_id
                and previous["document_id"] == document_id
                and not _SENTENCE_END_PATTERN.search(previous["label"])
                and not _NEW_FRAGMENT_START_PATTERN.match(text)
            )
            if continues_previous:
                previous["label"] = f"{previous['label'].rstrip()} {text.lstrip()}"
                previous["citation_ids"].append(citation_id)
                continue

            result.append(
                {
                    "id": node_id,
                    "type": node_type,
                    "label": text,
                    "parent_id": parent_id,
                    "document_id": document_id,
                    "citation_ids": [citation_id],
                }
            )
    return result
