"""`.docsignore` matching (`discover._is_ignored`) — gitignore semantics.

Pins the existing directory-prefix behavior (the only shape the real
`docs/.docsignore` uses today) AND the wildcard capability the hand-written
matcher never had — its own docstring says so ("Đủ cho exclude cả cây
product/, không cần globstar/fnmatch full"). The wildcard case is the live gap:
before the pathspec swap `_is_ignored` silently returns False for a `*`
pattern (no error, no warning — the file is just never excluded), which is
exactly the "quiet no-op" failure mode a future `.docsignore` author would hit
writing `*.draft.md` expecting real gitignore behavior.

Everything below `_is_ignored` alone only pins the private matcher — the
`TestIterMdEndToEnd` class at the bottom is the one that goes through the
production entrypoint (`iter_md`), because a passing `_is_ignored` suite alone
does not prove the shipped mechanism does the same thing (verified by review:
swapping the real `iter_md` call to `_build_ignore_spec([])` — disabling
`.docsignore` filtering outright — left every one of these tests green).
"""
import pytest

from docslib.discover import _is_ignored, _build_ignore_spec, iter_md, DocsIgnoreError


# --- existing shape: directory-prefix pattern (docs/.docsignore today: "research/") ---

def test_directory_pattern_matches_top_level_file():
    assert _is_ignored("research/foo.md", ["research/"]) is True


def test_directory_pattern_matches_nested_file():
    assert _is_ignored("research/sub/bar.md", ["research/"]) is True


def test_directory_pattern_does_not_match_prefix_collision():
    # "researchxyz/" must NOT be swallowed by a "research/" pattern.
    assert _is_ignored("researchxyz/foo.md", ["research/"]) is False


def test_directory_pattern_does_not_match_unrelated_file():
    assert _is_ignored("modules/core/mod-01/README.md", ["research/"]) is False


# --- wildcard capability: the hand-written matcher's documented gap ---

def test_wildcard_pattern_matches_top_level_file():
    assert _is_ignored("notes.draft.md", ["*.draft.md"]) is True


def test_wildcard_pattern_matches_nested_file():
    assert _is_ignored("sub/notes.draft.md", ["*.draft.md"]) is True


def test_wildcard_pattern_does_not_match_non_matching_file():
    assert _is_ignored("notes.md", ["*.draft.md"]) is False


# --- real gitignore semantics: the exact 3 divergences the review reproduced ---
#
# Switching the matcher to `pathspec`'s real gitignore semantics changed
# matching in BOTH directions relative to the old hand-rolled matcher — these
# pin the NEW (intended, real-gitignore) behavior as correct going forward.
# `docs/.docsignore`'s own header now documents exactly this, instead of the
# old ("no globstar", "dir/* recursively excludes") claims that were never
# true of the pathspec-backed matcher.

def test_single_star_dir_pattern_matches_immediate_child_only():
    # "dir/*" is ONE LEVEL — "*" does not cross "/". A direct child (a file OR
    # a directory name) matches; a grandchild through that child does not.
    assert _is_ignored("product/sub", ["product/*"]) is True
    assert _is_ignored("product/x.md", ["product/*"]) is True
    assert _is_ignored("product/sub/x.md", ["product/*"]) is False


def test_dir_slash_double_star_is_the_recursive_form():
    # The header points authors at "dir/**" for the old "dir/* means
    # everything under dir" behavior — pin that it actually works.
    assert _is_ignored("product/sub/x.md", ["product/**"]) is True


def test_bare_directory_pattern_matches_at_any_depth_not_just_top_level():
    # "research/" (no leading "/") matches a `research` dir ANYWHERE in the
    # tree, per real gitignore semantics — not only docs/research/.
    assert _is_ignored("modules/research/a.md", ["research/"]) is True


def test_bare_file_pattern_matches_at_any_depth_not_just_top_level():
    assert _is_ignored("guides/README.md", ["README.md"]) is True


def test_leading_slash_anchors_a_pattern_to_the_top_level_only():
    # The anchoring escape hatch the header now documents for an author who
    # wants the OLD top-level-only behavior back for one specific pattern.
    assert _is_ignored("README.md", ["/README.md"]) is True
    assert _is_ignored("guides/README.md", ["/README.md"]) is False


# --- malformed pattern: wrapped, not a raw pathspec traceback ---

class TestMalformedPatternIsWrapped:
    def test_lone_bang_raises_named_error(self):
        with pytest.raises(DocsIgnoreError, match=r"!"):
            _build_ignore_spec(["!"])

    def test_lone_trailing_backslash_raises_named_error(self):
        with pytest.raises(DocsIgnoreError):
            _build_ignore_spec(["\\"])

    def test_error_names_the_offending_pattern_among_valid_ones(self):
        with pytest.raises(DocsIgnoreError, match=r"pattern #2"):
            _build_ignore_spec(["research/", "!", "*.draft.md"])

    def test_error_names_the_real_file_line_number_via_iter_md(self, tmp_path):
        (tmp_path / ".docsignore").write_text(
            "# a comment\nresearch/\n!\n", encoding="utf-8")
        (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
        with pytest.raises(DocsIgnoreError, match=r"line 3"):
            list(iter_md(tmp_path))


# --- production entrypoint: the mechanism that actually ships -------------

class TestIterMdEndToEnd:
    """Goes through `iter_md` with a REAL `.docsignore` on disk — the one
    thing every `_is_ignored`-only test above cannot prove: that the
    filtering mechanism `iter_md`/`discover` actually calls behaves the same
    way. (Regression check performed by review: swapping iter_md's real
    `_build_ignore_spec(patterns, ...)` call for `_build_ignore_spec([])`
    — turning `.docsignore` filtering off entirely — left the whole
    `_is_ignored`-only suite green; these tests fail under that swap.)"""

    def _tree(self, tmp_path, docsignore_text):
        (tmp_path / ".docsignore").write_text(docsignore_text, encoding="utf-8")
        (tmp_path / "research").mkdir()
        (tmp_path / "research" / "notes.md").write_text("# notes\n", encoding="utf-8")
        (tmp_path / "guides").mkdir()
        (tmp_path / "guides" / "README.md").write_text("# g\n", encoding="utf-8")
        (tmp_path / "kept.md").write_text("# kept\n", encoding="utf-8")

    def test_ignored_dir_is_excluded_from_iter_md(self, tmp_path):
        self._tree(tmp_path, "research/\n")
        got = {str(p.relative_to(tmp_path)) for p in iter_md(tmp_path)}
        assert "research/notes.md" not in got
        assert "kept.md" in got
        assert "guides/README.md" in got

    def test_bare_file_pattern_excludes_at_any_depth_through_iter_md(self, tmp_path):
        self._tree(tmp_path, "README.md\n")
        got = {str(p.relative_to(tmp_path)) for p in iter_md(tmp_path)}
        assert "guides/README.md" not in got
        assert "kept.md" in got

    def test_no_docsignore_file_excludes_nothing(self, tmp_path):
        self._tree(tmp_path, "")
        (tmp_path / ".docsignore").unlink()
        got = {str(p.relative_to(tmp_path)) for p in iter_md(tmp_path)}
        assert got == {"research/notes.md", "guides/README.md", "kept.md"}
