"""P5 — TDD cho e2e_static: phải BẮT ref vỡ (hard) + phân loại soft đúng."""
import e2e_static as E


def _html(body):
    return f"<!DOCTYPE html><html><head></head><body>{body}</body></html>"


def test_missing_asset_is_hard(tmp_path):
    pub = tmp_path / "public"
    pub.mkdir()
    (pub / "index.html").write_text(_html('<link href="assets/x.css"><img src="img/missing.png">'),
                                    encoding="utf-8")
    hard, soft, _ = E.run(pub)
    assert any("x.css" in h for h in hard)
    assert any("missing.png" in h for h in hard)


def test_dangling_atkey_is_hard(tmp_path):
    pub = tmp_path / "public"
    pub.mkdir()
    (pub / "index.html").write_text(_html('<a href="@ghost@">x</a>'), encoding="utf-8")
    hard, soft, _ = E.run(pub)
    assert any("@ghost@" in h or "ghost" in h for h in hard)


def test_md_yaml_crossdoc_link_is_soft(tmp_path):
    pub = tmp_path / "public"
    pub.mkdir()
    (pub / "index.html").write_text(
        _html('<a href="../modules/README.md">x</a><a href="../_index/showcase.yaml">y</a>'),
        encoding="utf-8")
    hard, soft, _ = E.run(pub)
    assert not hard, hard
    assert len(soft) == 2


def test_portable_singlefile_is_soft(tmp_path):
    pub = tmp_path / "public"
    pub.mkdir()
    (pub / "vsf-aio-platform-showcase.html").write_text(
        _html('<img src="../diagram/png/x.png">'), encoding="utf-8")
    hard, soft, _ = E.run(pub)
    assert not hard
    assert len(soft) == 1


def test_resolved_refs_pass(tmp_path):
    pub = tmp_path / "public"
    (pub / "assets").mkdir(parents=True)
    (pub / "assets" / "x.css").write_text("/* */", encoding="utf-8")
    (pub / "index.html").write_text(_html('<link href="assets/x.css">'), encoding="utf-8")
    hard, soft, _ = E.run(pub)
    assert not hard and not soft


def test_external_links_ignored(tmp_path):
    pub = tmp_path / "public"
    pub.mkdir()
    (pub / "index.html").write_text(
        _html('<a href="https://x.com">a</a><a href="#sec">b</a><a href="mailto:a@b.c">c</a>'),
        encoding="utf-8")
    hard, soft, _ = E.run(pub)
    assert not hard and not soft
