#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Poster Design Core - shared utilities for analyze/cluster/search/generate.

Two responsibilities in one module (mirrors the logo/cip cores' self-contained shape):
  1. The BM25 search engine + CSV config over the curated poster knowledge (style / palette /
     layout / texture). This is the SAME BM25 the logo/cip cores use — one engine, reused, not
     a second divergent copy.
  2. The data-build infra for analyze/cluster: env loading (GEMINI_API_KEY), a Gemini client
     factory, the extraction-JSON validator, and the raw-JSON reader/writer. google-genai is
     imported LAZILY inside gemini_client() so this module (and search/generate) import with no
     extra dependency; the vision dep only loads when you actually rebuild the CSVs.
"""

import csv
import json
import os
import re

from rank_bm25 import BM25Okapi
from pathlib import Path
from typing import Iterable

# ============ PATHS ============
SKILL_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = SKILL_ROOT / "data" / "poster"
RAW_DIR = DATA_DIR / "analysis" / "raw"
CLUSTERS_AUDIT = DATA_DIR / "analysis" / "clusters.json"
MAX_RESULTS = 3

# ============ CSV CONFIG (search) ============
CSV_CONFIG = {
    "style": {
        "file": "poster-styles.csv",
        "search_cols": ["Style Name", "Category", "Keywords", "Mood", "When To Use"],
        "output_cols": ["Style Name", "Category", "Keywords", "Mood", "Description",
                        "Specs", "Shape Pool", "When To Use", "Avoid For", "Hints",
                        "Recommendations", "Era"],
    },
    "palette": {
        "file": "poster-palettes.csv",
        "search_cols": ["Palette Name", "Color Mood", "Pairs With Styles", "When To Use"],
        "output_cols": ["Palette Name", "Hex Colors", "Color Mood", "Contrast Level",
                        "Pairs With Styles", "When To Use"],
    },
    "layout": {
        "file": "poster-layouts.csv",
        "search_cols": ["Layout Name", "Grid System", "Focal Anchor", "Best For Content"],
        "output_cols": ["Layout Name", "Grid System", "Focal Anchor", "Element Hierarchy",
                        "Whitespace Ratio", "Best For Content"],
    },
    "texture": {
        "file": "poster-textures.csv",
        "search_cols": ["Texture Name", "Material", "Grain/Finish", "Pairs With Styles"],
        "output_cols": ["Texture Name", "Material", "Grain/Finish", "Effect Description",
                        "Pairs With Styles", "Rendering Hints"],
    },
}


# ============ BM25 IMPLEMENTATION ============
class BM25:
    """BM25 ranking over rank-bm25's BM25Okapi.

    The tokeniser stays here, not in the library: BM25Okapi takes an already-tokenised
    corpus, and the token-length floor below is a per-catalog decision.

    Ordering shifts slightly against the hand-written scorer this replaces — measured
    across 231 queries with real hits on seven live catalogs, BM25Okapi reproduces the
    old top-5 exactly 91.3% of the time; 6.9% reshuffle within the same five documents,
    1.7% return a different set, 1.7% change the top hit.
    """

    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.corpus = []
        self._model = None

    def tokenize(self, text):
        """Lowercase, split, remove punctuation, filter short words"""
        text = re.sub(r'[^\w\s]', ' ', str(text).lower())
        return [w for w in text.split() if len(w) > 2]

    def fit(self, documents):
        """Build BM25 index from documents"""
        self.corpus = [self.tokenize(doc) for doc in documents]
        # BM25Okapi divides by the mean document length, so an empty corpus — or one
        # where every document tokenises to nothing — raises ZeroDivisionError. Callers
        # reach this by typing a query that matches nothing, and that must be an empty
        # result, not a dead script.
        self._model = (BM25Okapi(self.corpus, k1=self.k1, b=self.b)
                       if any(self.corpus) else None)

    def score(self, query):
        """Score all documents against query; returns [(idx, score)] sorted desc."""
        if self._model is None:
            # One zero-scored entry per document: callers slice before filtering on
            # `score > 0`, so a short list would truncate rather than return nothing.
            return [(i, 0.0) for i in range(len(self.corpus))]
        raw = self._model.get_scores(self.tokenize(query))
        # float(): the library returns numpy scalars and these results are printed as
        # JSON, which numpy floats do not serialise.
        return sorted(((i, float(s)) for i, s in enumerate(raw)),
                      key=lambda x: x[1], reverse=True)


# ============ SEARCH FUNCTIONS ============
def _load_csv(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _search_csv(filepath, search_cols, output_cols, query, max_results):
    """Core search function using BM25 (mirrors the logo/cip cores)."""
    if not Path(filepath).exists():
        return []
    data = _load_csv(filepath)
    documents = [" ".join(str(row.get(col, "")) for col in search_cols) for row in data]
    bm25 = BM25()
    bm25.fit(documents)
    ranked = bm25.score(query)
    results = []
    for idx, score in ranked[:max_results]:
        if score > 0:
            row = data[idx]
            results.append({col: row.get(col, "") for col in output_cols if col in row})
    return results


def detect_domain(query):
    """Auto-detect the most relevant poster domain from a query."""
    q = query.lower()
    domain_keywords = {
        "style": ["style", "swiss", "editorial", "brutalist", "minimal", "retro", "geometric",
                  "typographic", "grunge", "risograph", "modern"],
        "palette": ["palette", "color", "colour", "hex", "warm", "cool", "muted", "vibrant",
                    "monochrome", "pastel", "earthy"],
        "layout": ["layout", "grid", "columns", "centered", "asymmetric", "stacked", "focal",
                   "whitespace", "composition"],
        "texture": ["texture", "material", "grain", "halftone", "paper", "foil", "gradient",
                    "risograph", "newsprint", "matte", "glossy"],
    }
    scores = {d: sum(1 for kw in kws if kw in q) for d, kws in domain_keywords.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "style"


def search(query, domain=None, max_results=MAX_RESULTS):
    """Main search over one poster domain (auto-detected when omitted)."""
    if domain is None:
        domain = detect_domain(query)
    config = CSV_CONFIG.get(domain, CSV_CONFIG["style"])
    filepath = DATA_DIR / config["file"]
    if not filepath.exists():
        return {"error": "File not found: %s" % filepath, "domain": domain}
    results = _search_csv(filepath, config["search_cols"], config["output_cols"], query, max_results)
    return {"domain": domain, "query": query, "file": config["file"],
            "count": len(results), "results": results}


# ============ DATA-BUILD INFRA (analyze / cluster) ============
EXTRACTION_REQUIRED_KEYS = {
    "image", "style_cues", "palette_hexes", "layout", "texture", "mood",
    "shape_primitives", "typography",
}
LAYOUT_REQUIRED_KEYS = {"grid", "focal", "whitespace_ratio"}
TEXTURE_REQUIRED_KEYS = {"material", "finish"}


def load_env() -> None:
    """Load .env in priority order: project → skills → home. Idempotent."""
    candidates = [
        SKILL_ROOT.parent.parent / ".env",
        Path.home() / ".claude" / "skills" / ".env",
        Path.home() / ".claude" / ".env",
    ]
    for path in candidates:
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def get_api_key() -> str:
    """Return GEMINI_API_KEY, raising with an actionable message if missing."""
    load_env()
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set. Add to ~/.claude/.env or project .env.")
    return key


def gemini_client():
    """Return a google-genai Client configured with the API key (lazy dep import)."""
    from google import genai
    return genai.Client(api_key=get_api_key())


def validate_extraction(data: dict):
    """Strict-validate that an extraction JSON has all required keys."""
    if not isinstance(data, dict):
        return False, "not a dict"
    missing = EXTRACTION_REQUIRED_KEYS - set(data.keys())
    if missing:
        return False, "missing keys: %s" % sorted(missing)
    if not isinstance(data.get("layout"), dict):
        return False, "layout must be dict"
    if LAYOUT_REQUIRED_KEYS - set(data["layout"].keys()):
        return False, "layout missing: %s" % (LAYOUT_REQUIRED_KEYS - set(data["layout"].keys()))
    if not isinstance(data.get("texture"), dict):
        return False, "texture must be dict"
    if TEXTURE_REQUIRED_KEYS - set(data["texture"].keys()):
        return False, "texture missing material/finish"
    for list_key in ("style_cues", "palette_hexes", "mood", "shape_primitives", "typography"):
        if not isinstance(data.get(list_key), list):
            return False, "%s must be list" % list_key
    return True, ""


def write_raw(image_name: str, payload: dict) -> Path:
    """Write extraction JSON to RAW_DIR keyed by image filename stem."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / ("%s.json" % Path(image_name).stem)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return out


def load_all_raw() -> list:
    """Load every valid raw extraction JSON; skip invalid ones."""
    if not RAW_DIR.exists():
        return []
    items = []
    for path in sorted(RAW_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        ok, _ = validate_extraction(data)
        if ok:
            items.append(data)
    return items


def iter_images(input_dir: Path, exts: Iterable = (".jpg", ".jpeg", ".png")) -> list:
    """Sorted list of image files in input_dir filtered by extension."""
    return sorted(p for p in input_dir.iterdir() if p.suffix.lower() in exts)
