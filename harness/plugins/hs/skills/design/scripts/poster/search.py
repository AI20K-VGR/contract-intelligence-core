#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Poster Search — query poster CSVs by domain or build a design brief.

Reuses the shared BM25 engine (core.BM25) — no second copy of the scoring math.

Usage:
    search.py --domain style --query "swiss minimal"
    search.py --domain palette --query "warm earthy"
    search.py --poster-brief --topic "AI Conference"
    search.py --domain layout --query "centered"
    search.py --domain texture --query "risograph"
"""

import argparse
import csv
import json
import random
import sys
from pathlib import Path

import core

DOMAIN_CSV = {
    "style": "poster-styles.csv",
    "palette": "poster-palettes.csv",
    "layout": "poster-layouts.csv",
    "texture": "poster-textures.csv",
}

SEARCH_COLS = {
    "style": ["Style Name", "Category", "Keywords", "Mood", "When To Use"],
    "palette": ["Palette Name", "Color Mood", "Pairs With Styles", "When To Use"],
    "layout": ["Layout Name", "Grid System", "Focal Anchor", "Best For Content"],
    "texture": ["Texture Name", "Material", "Grain/Finish", "Pairs With Styles"],
}


def load_csv(domain: str) -> list:
    path = core.DATA_DIR / DOMAIN_CSV[domain]
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def bm25_rank(rows: list, query: str, search_cols: list, top_k: int = 5) -> list:
    """Rank rows by BM25 over the selected columns, reusing the shared core.BM25 engine.
    Returns rows with score > 0 (falls back to the head slice when nothing matches)."""
    if not rows or not query:
        return rows[:top_k]
    documents = [" ".join(str(r.get(c, "")) for c in search_cols) for r in rows]
    bm25 = core.BM25()
    bm25.fit(documents)
    ranked = bm25.score(query)
    hits = [rows[idx] for idx, score in ranked if score > 0][:top_k]
    return hits or rows[:top_k]


def build_brief(topic: str, query: str) -> dict:
    """Pick one row per domain to assemble a brief."""
    rng = random.Random(query + topic)
    out = {"topic": topic, "query": query}
    for domain in ("style", "palette", "layout", "texture"):
        rows = load_csv(domain)
        if not rows:
            continue
        ranked = bm25_rank(rows, query, SEARCH_COLS[domain], top_k=3) or rows[:3]
        out[domain] = rng.choice(ranked)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", choices=list(DOMAIN_CSV))
    parser.add_argument("--query", default="")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--poster-brief", action="store_true")
    parser.add_argument("--topic", default="")
    parser.add_argument("--json", action="store_true", help="output JSON")
    args = parser.parse_args()

    if args.poster_brief:
        brief = build_brief(args.topic, args.query)
        print(json.dumps(brief, indent=2, ensure_ascii=False))
        return 0

    if not args.domain:
        parser.error("--domain required when not using --poster-brief")
    rows = load_csv(args.domain)
    if not rows:
        print("no data in %s; run cluster.py first" % DOMAIN_CSV[args.domain], file=sys.stderr)
        return 2
    results = bm25_rank(rows, args.query, SEARCH_COLS[args.domain], top_k=args.top)
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for r in results:
            print("---")
            for k, v in r.items():
                print("%s: %s" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
