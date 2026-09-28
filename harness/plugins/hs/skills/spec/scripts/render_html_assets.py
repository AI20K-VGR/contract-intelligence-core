#!/usr/bin/env python3
"""Vendor/asset loaders and body-render helpers for render_html.

Isolated from render_html.py so the vendored-JS loading concern can be
maintained independently of the page-assembly concern.

Exports:
  _load_vendored_mermaid_js()  — None when vendored file is absent
  _load_mermaid_js()           — the vendored payload, or "" when absent
  _load_vendored_markdown_libs()
  viewer_head()
  embed_spec_data(payload)
  markdown_libs_banner()
  body_render_values(spec_payload)

Not a CLI entry point; imported by render_html.

Offline-only invariant: NOTHING in this module ever emits a CDN URL / an
external `<script src=...>`. When a vendored asset is missing, every loader
here degrades to an empty/inert value; the caller (render_html) is
responsible for falling back to escaped plaintext.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

from encoding_utils import dumps_json
from render_common import strip_control

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = SKILL_ROOT / "assets" / "templates"
VENDOR = SKILL_ROOT / "assets" / "vendor"
VIEWER_HEAD_PARTIAL = TEMPLATES / "_viewer-head.html"
VENDOR_MERMAID = VENDOR / "mermaid.min.js"
VENDOR_MARKED = VENDOR / "marked.min.js"
VENDOR_PURIFY = VENDOR / "purify.min.js"

# The sanitize chokepoint, shipped INSIDE the {{markdown_libs}} block (body views
# only) so legacy graph views inline no marked/DOMPurify code at all. Always
# defined — when the libs are absent it FAILS CLOSED to escaped text, never a CDN.
_BODY_RENDER_JS = (
    "\nfunction psRenderMarkdown(md){"
    "if(window.marked&&window.DOMPurify){return window.DOMPurify.sanitize(window.marked.parse(String(md==null?'':md)));}"
    "return '<pre class=\"ps-fallback\">'+psEscapeHtml(md)+'</pre>';}"
    # Shared detail-panel controls for board + explorer. Defined HERE (body-view
    # only) — not in the shared head — because they call psRenderMarkdown, so the
    # 9 legacy graph views stay free of any sanitizer reference. Each
    # body shell registers its id->record map via psRegisterDetail(byId); inert in
    # the linear export (it has no #ps-detail). Body is the only innerHTML sink.
    "\nvar psDetailById={},psDetailCache={};"
    "\nfunction psRegisterDetail(byId){psDetailById=byId||{};}"
    "\nwindow.psOpenDetail=function(id){var c=psDetailById[id];if(!c){return;}"
    "var t=document.getElementById('ps-detail-title'),b=document.getElementById('ps-detail-body'),d=document.getElementById('ps-detail');"
    "if(!t||!b||!d){return;}"
    "t.textContent=c.id+(c.title?' \\u2014 '+c.title:'');"
    # Memoize the sanitized body per id (immutable) so re-opening the same card
    # does not re-tokenize + re-sanitize — matches the table-tree dataset.loaded guard.
    "b.innerHTML=(psDetailCache[id]||(psDetailCache[id]=psRenderMarkdown(c.body||'_(no body)_')));d.hidden=false;};"
    "\nwindow.psCloseDetail=function(){var d=document.getElementById('ps-detail');if(d){d.hidden=true;}};"
    "\ndocument.addEventListener('keydown',function(e){if(e.key==='Escape'){psCloseDetail();}});"
    # Shared facet/search engine for board + explorer (body views only). Pure,
    # parameterized helpers so both shells share ONE implementation: each shell
    # owns its records array + state shape (board has no mode; explorer adds one)
    # + its render callback; the filter machinery below is identical. Hoisting it
    # here (mirroring psRegisterDetail) closes the board/explorer divergence risk
    # the detail-panel comment calls out. psBuildFacets localizes the Layer-facet
    # chip values (L[v]) so a --lang vi facet matches the Flat-tabs tab labels.
    "\nvar psFacetGroups=['status','moscow','horizon','persona','layer'];"
    "\nfunction psDistinct(records,group){var seen={};records.forEach(function(c){var v=group==='persona'?c.personas:[c[group]];(v||[]).forEach(function(x){if(x){seen[x]=true;}});});return Object.keys(seen).sort();}"
    # `state.facets[g]||{}` guards let the engine tolerate a shell that hasn't
    # pre-declared every psFacetGroups bucket (the group LIST is the single source
    # of truth; a missing bucket no longer throws on first paint). psBuildFacets
    # seeds the bucket for each group it renders.
    "\nfunction psFacetActive(state,g){return Object.keys(state.facets[g]||{}).length>0;}"
    "\nfunction psSelfMatch(state,c){if(state.q){var hay=(c.id+' '+c.title+' '+(c.body||'')).toLowerCase();if(hay.indexOf(state.q)===-1){return false;}}for(var i=0;i<psFacetGroups.length;i++){var g=psFacetGroups[i];if(!psFacetActive(state,g)){continue;}var vals=g==='persona'?(c.personas||[]):[c[g]];if(!vals.some(function(v){return (state.facets[g]||{})[v];})){return false;}}return true;}"
    "\nfunction psBadge(text,cls){var s=document.createElement('span');s.className='badge '+cls;s.textContent=text;return s;}"
    # Shared card-badge emitter (type/status/moscow/persona, in order) — board cards
    # and explorer nodes both call it so the badge set stays identical across viewers.
    "\nfunction psMetaBadges(c,el){if(c.type){el.appendChild(psBadge(c.type,'badge--type'));}if(c.status){el.appendChild(psBadge(c.status,'badge--status'));}if(c.moscow){el.appendChild(psBadge(c.moscow,'badge--moscow'));}(c.personas||[]).forEach(function(p){el.appendChild(psBadge(p,'badge--persona'));});}"
    # Shared search-input wiring (placeholder + lowercased query → onChange) so both
    # shells wire the #ps-search box identically; pass the localized label + the
    # shell's render callback.
    "\nfunction psWireSearch(state,onChange,label){var s=document.getElementById('ps-search');if(!s){return;}s.placeholder=label||'Search…';s.addEventListener('input',function(){state.q=this.value.toLowerCase();onChange();});}"
    "\nfunction psBuildFacets(records,labels,state,onChange){var host=document.getElementById('ps-facets');if(!host){return;}var L=labels||{};psFacetGroups.forEach(function(g){var vals=psDistinct(records,g);if(!vals.length){return;}state.facets[g]=state.facets[g]||{};var lab=document.createElement('span');lab.className='badge badge--type';lab.textContent=(L[g]||g)+':';host.appendChild(lab);vals.forEach(function(v){var b=document.createElement('button');b.type='button';b.textContent=(L[v]||v);b.setAttribute('aria-pressed','false');b.addEventListener('click',function(){if(state.facets[g][v]){delete state.facets[g][v];b.setAttribute('aria-pressed','false');}else{state.facets[g][v]=true;b.setAttribute('aria-pressed','true');}onChange();});host.appendChild(b);});});}"
)


def _load_vendored_mermaid_js() -> Optional[str]:
    """Return the inline Mermaid JS payload if vendored; else None.

    Split out from the CDN-fallback path so each path has a single
    responsibility: this one only reads the local file, returns None on
    miss. The caller decides whether to fall back.
    """
    if VENDOR_MERMAID.is_file():
        return VENDOR_MERMAID.read_text(encoding="utf-8")
    return None


def _load_mermaid_js() -> str:
    """Return the vendored Mermaid JS payload, or "" when it is absent.

    Offline-only invariant: there is no CDN fallback. When the vendored file
    is missing, the caller (render_html) degrades the whole view body to an
    inert escaped `<pre>` diagram source instead of loading the Mermaid
    runtime at all — never an external `<script src=...>`.
    """
    return _load_vendored_mermaid_js() or ""


def _load_vendored_markdown_libs() -> Optional[str]:
    """Return the inlined marked + DOMPurify payload, or None if either is
    missing. Escapes the `</script` close-tag hazard at inline time so the
    vendored files stay byte-identical to the CDN originals (hash-pin intact)."""
    if not (VENDOR_MARKED.exists() and VENDOR_PURIFY.exists()):
        return None
    marked_js = VENDOR_MARKED.read_text(encoding="utf-8")
    purify_js = VENDOR_PURIFY.read_text(encoding="utf-8")
    payload = purify_js + "\n" + marked_js
    # The only HTML hazard for inline <script> content is the literal substring
    # `</script` (case-insensitive). A blanket `</`→`<\/` would corrupt minified
    # comparisons like `a</b/`, so escape only the actual close-tag token.
    return re.sub(r"</(script)", r"<\\/\1", payload, flags=re.IGNORECASE)


def viewer_head() -> str:
    """The shared design-system head partial (one source for every HTML output)."""
    return VIEWER_HEAD_PARTIAL.read_text(encoding="utf-8")


def embed_spec_data(payload: Any) -> str:
    """Serialize `payload` into an inert JSON data island.

    Every literal `<` is rewritten to its JSON `\\u003c` escape. This neutralizes
    ALL three script-data hazards at once — `</script>` (breakout), `<script` and
    the `<!--` comment primer (which together drive the WHATWG script-data-double-
    escaped state, where the island's own `</script>` no longer closes the tag and
    the page-bootstrap script is swallowed → a blank render from valid PO prose).
    `\\u003c` round-trips through JSON.parse straight back to `<`, so the rendered
    body is unchanged; only the raw transport is neutered. (HTML entities like
    `&#x3c;` would NOT work here: a <script> element's text is not entity-decoded,
    so the body would show the literal `&#x3c;`.)

    Control/bidi neutralization: the payload is run through `strip_control`
    (render_common's shared `_CONTROL_RE`) BEFORE serialization, so a bidi
    override (Trojan-Source, CVE-2021-42574) or a C0/DEL byte in any card field
    or body cannot ride raw into the JSON island and reorder/hide text when the
    board/explorer paint it via `textContent`. This closes the drift where the
    graph views stripped but the board/explorer island did not — honoring
    render_common's "stripped at EVERY render chokepoint" invariant."""
    blob = dumps_json(strip_control(payload), ensure_ascii=False, sort_keys=True).replace("<", "\\u003c")
    return f'<script type="application/json" id="ps-spec-data">{blob}</script>'


def markdown_libs_banner() -> str:
    """A visible fail-closed banner shown when the sanitizer libs are absent."""
    return (
        '<div class="ps-banner">Markdown libraries not vendored — bodies shown as '
        'plain text. Run <code>install.sh</code> to enable rich rendering '
        '(offline, no CDN).</div>'
    )


def body_render_values(spec_payload: Any) -> Dict[str, str]:
    """The shared token set every body-bearing shell interpolates:
    `viewer_head` (design system), `markdown_libs` (sanitizer or ""),
    `libs_banner` (fail-closed notice or ""), `spec_data` (inert JSON island)."""
    libs = _load_vendored_markdown_libs()
    return {
        "viewer_head": viewer_head(),
        # libs (or "" when fail-closed) + the always-present sanitize chokepoint.
        "markdown_libs": (libs or "") + _BODY_RENDER_JS,
        "libs_banner": "" if libs is not None else markdown_libs_banner(),
        "spec_data": embed_spec_data(spec_payload),
    }
