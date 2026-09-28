#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Three.js Skill Core - BM25 search engine for Three.js examples and API
"""

import csv
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

# ============ CONFIGURATION ============
DATA_DIR = Path(__file__).parent.parent / "data"
MAX_RESULTS = 5

CSV_CONFIG = {
    "examples": {
        "file": "examples-all.csv",
        "search_cols": ["Category", "Name", "Keywords", "Use Cases", "Description"],
        "output_cols": ["ID", "Category", "Name", "File", "Keywords", "URL", "Complexity", "Use Cases", "Description"]
    },
    "categories": {
        "file": "categories.csv",
        "search_cols": ["Category", "Keywords", "Description", "Primary Use Cases"],
        "output_cols": ["Category", "Keywords", "Description", "Complexity Range", "Example Count", "Primary Use Cases", "Related Categories"]
    },
    "use-cases": {
        "file": "use-cases.csv",
        "search_cols": ["Use Case", "Keywords", "Description", "Technologies"],
        "output_cols": ["Use Case", "Keywords", "Recommended Examples", "Complexity", "Technologies", "Description"]
    },
    "api": {
        "file": "api-reference.csv",
        "search_cols": ["Category", "Class", "Keywords", "Description", "Common Methods"],
        "output_cols": ["Category", "Class", "Keywords", "Description", "Common Methods", "Related Classes"]
    }
}

# Domain keyword mapping for auto-detection
DOMAIN_KEYWORDS = {
    "examples": ["example", "demo", "showcase", "webgl", "webgpu", "animation", "loader", "material", "geometry", "light", "shadow", "postprocessing", "effect", "particle", "physics", "vr", "xr"],
    "categories": ["category", "group", "section", "list all", "types of"],
    "use-cases": ["use case", "project", "application", "build", "create", "make", "implement", "for", "suitable"],
    "api": ["api", "class", "method", "function", "property", "how to", "what is", "parameter", "constructor"]
}


# ============ BM25 IMPLEMENTATION ============
class BM25:
    """BM25 ranking over rank-bm25's BM25Okapi.

    The tokeniser stays here, not in the library: BM25Okapi takes an already-tokenised
    corpus, and the token-length floor below is a per-catalog decision.\n    This catalog keeps two-character tokens — `3d`, `gl`, `vr`, `ar` are the terms\n    people search a Three.js catalog by, and a two-character floor drops every one\n    of them. That is the ONE way this copy is allowed to differ from the others.

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
        return [w for w in text.split() if len(w) > 1]

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
    """Load CSV and return list of dicts"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _search_csv(filepath, search_cols, output_cols, query, max_results):
    """Core search function using BM25"""
    if not filepath.exists():
        return []

    data = _load_csv(filepath)

    # Build documents from search columns
    documents = [" ".join(str(row.get(col, "")) for col in search_cols) for row in data]

    # BM25 search
    bm25 = BM25()
    bm25.fit(documents)
    ranked = bm25.score(query)

    # Get top results with score > 0
    results = []
    for idx, score in ranked[:max_results]:
        if score > 0:
            row = data[idx]
            results.append({col: row.get(col, "") for col in output_cols if col in row})

    return results


def detect_domain(query):
    """Auto-detect the most relevant domain from query"""
    query_lower = query.lower()

    scores = {
        domain: sum(1 for kw in keywords if kw in query_lower)
        for domain, keywords in DOMAIN_KEYWORDS.items()
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "examples"


def search(query, domain=None, max_results=MAX_RESULTS):
    """Main search function with auto-domain detection"""
    if domain is None:
        domain = detect_domain(query)

    config = CSV_CONFIG.get(domain, CSV_CONFIG["examples"])
    filepath = DATA_DIR / config["file"]

    if not filepath.exists():
        return {"error": f"File not found: {filepath}", "domain": domain}

    results = _search_csv(filepath, config["search_cols"], config["output_cols"], query, max_results)

    return {
        "domain": domain,
        "query": query,
        "file": config["file"],
        "count": len(results),
        "results": results
    }


def search_by_complexity(complexity, max_results=MAX_RESULTS):
    """Search examples by complexity level"""
    filepath = DATA_DIR / "examples-all.csv"
    if not filepath.exists():
        return {"error": f"File not found: {filepath}"}

    data = _load_csv(filepath)
    results = [row for row in data if row.get("Complexity", "").lower() == complexity.lower()][:max_results]

    return {
        "domain": "examples",
        "complexity": complexity,
        "count": len(results),
        "results": results
    }


def search_by_category(category, max_results=MAX_RESULTS):
    """Search examples by category"""
    filepath = DATA_DIR / "examples-all.csv"
    if not filepath.exists():
        return {"error": f"File not found: {filepath}"}

    data = _load_csv(filepath)
    results = [row for row in data if category.lower() in row.get("Category", "").lower()][:max_results]

    return {
        "domain": "examples",
        "category": category,
        "count": len(results),
        "results": results
    }


def get_recommended_examples(use_case, max_results=MAX_RESULTS):
    """Get recommended examples for a specific use case"""
    # First search use cases
    use_case_result = search(use_case, domain="use-cases", max_results=1)

    if use_case_result.get("count", 0) == 0:
        return {"error": f"No use case found for: {use_case}"}

    # Get recommended examples
    recommended = use_case_result["results"][0].get("Recommended Examples", "")
    example_names = [e.strip() for e in recommended.split(";")]

    # Search for each example
    all_results = []
    for name in example_names[:max_results]:
        result = search(name, domain="examples", max_results=1)
        if result.get("count", 0) > 0:
            all_results.extend(result["results"])

    return {
        "domain": "examples",
        "use_case": use_case,
        "count": len(all_results),
        "results": all_results
    }
