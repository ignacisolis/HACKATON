"""Tests sin red: configuración, parseo TAP, bandas y API con IRSA simulado."""
from __future__ import annotations

import numpy as np
import pytest

from app import cache, irsa
from conftest import DEC, RA, TAP_ROWS, fake_mef


def test_release_config(settings):
    assert "spherex_qr2" in settings.collections
    assert not any(c.endswith("_cal") for c in settings.collections)


def test_bands_come_from_core():
    """La banda la decide core.bands con el par (detector, λ): en las costuras no hay ambigüedad."""
    from app import science
    for band in (1, 17, 18, 50, 102):
        det, lo, hi = science.band_range(band)
        assert science.band_of(det, (lo + hi) / 2) == band
    # 1.11 µm cae en la costura D1/D2: el detector decide
    assert science.band_of(1, 1.11) == 17 and science.band_of(2, 1.11) == 18
    with pytest.raises(KeyError):
        science.band_range(103)


def test_query_is_numeric_only(settings):
    with pytest.raises(ValueError):
        irsa.build_query("1); DROP", 0, settings)  # type: ignore[arg-type]


def test_parse_rows_dedupes_versions(settings):
    obs = irsa.parse_rows(TAP_ROWS, settings)
    assert [o.id for o in obs] == ["2025W19_1B_0100_2D1", "2025W19_1B_0116_1D3"]
    d3 = obs[1]
    assert d3.version == "l2b-v24-2026-115" and d3.detector == 3
    assert d3.lambda_min_um == pytest.approx(1.6301)


def test_compact_cutout_drops_psf_and_reads_flags(settings, tmp_path):
    c = cache.compact_from_fits(fake_mef())
    assert c.flag_bits == {"SOURCE": 21, "HOT": 10}
    assert c.wavelength_at(RA, DEC) == pytest.approx(2.0)
    p = tmp_path / "x.npz"
    cache._save(c, p)
    assert p.stat().st_size < 50_000
    c2 = cache._load(p)
    np.testing.assert_array_equal(c2.flags, c.flags)
    assert c2.wcs.wcs.ctype[0].startswith("RA---TAN")


def test_frames_then_cache(client):
    c, calls = client
    r = c.get("/api/frames", params={"ra": RA, "dec": DEC, "prefetch": False})
    assert r.status_code == 200
    body = r.json()
    assert body["n_frames"] == 2 and body["pending"] == 2 and not body["complete"]
    f = body["frames"][1]
    assert f["detector"] == "D3" and f["ready"] is False and f["wavelength_um"] is None

    png = c.get(f["image_url"])
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"
    meta = c.get(f["meta_url"]).json()
    assert meta["wavelength_um"] == pytest.approx(2.0)
    assert meta["bandwidth_um"] == pytest.approx(0.05)
    src = next(x for x in meta["flags"]["cutout_counts"] if x["name"] == "SOURCE")
    assert src["bit"] == 21 and src["pixels"] == 1
    assert "SOURCE" in meta["flags"]["at_target"] and "SOURCE" in meta["mask_layers"]

    # 2ª consulta: misma posición en sexagesimal -> ni TAP ni cutout tocan IRSA
    r2 = c.get("/api/frames", params={"ra": "08h55m10.831s", "dec": "-7d14m42.53s", "prefetch": False})
    f2 = next(x for x in r2.json()["frames"] if x["id"] == f["id"])
    assert f2["ready"] and f2["wavelength_um"] == pytest.approx(2.0)
    assert f2["quality"] == "ok" and 0 <= f2["flagged_fraction"] < 0.5
    n = 59  # ceil(0.1° / 6.15″)
    assert f2["target_xy"] == pytest.approx([(n - 1) / 2, (n - 1) / 2], abs=0.6)
    assert calls == {"tap": 1, "cutout": 1}


def test_band_filter_and_detector_format(client):
    c, _ = client
    body = c.get("/api/frames", params={"ra": RA, "dec": DEC, "band": 18, "prefetch": False}).json()
    assert {f["detector"] for f in body["frames"]} <= {"D2"}
    body = c.get("/api/frames", params={"ra": RA, "dec": DEC, "detector": "D1", "prefetch": False}).json()
    assert [f["detector"] for f in body["frames"]] == ["D1"]
    assert c.get("/api/frames", params={"ra": RA, "dec": DEC, "detector": "D9"}).status_code == 422


def test_pagination(client):
    c, _ = client
    body = c.get("/api/frames", params={"ra": RA, "dec": DEC, "limit": 1, "offset": 1, "prefetch": False}).json()
    assert body["n_frames"] == 2 and len(body["frames"]) == 1 and body["frames"][0]["detector"] == "D3"


def test_flags_layer_and_errors_are_json(client):
    c, _ = client
    c.get("/api/frames", params={"ra": RA, "dec": DEC, "prefetch": False})
    for bits in ("21", "SOURCE", "SOURCE,HOT"):
        url = f"/api/frame/2025W19_1B_0116_1D3/png?ra={RA}&dec={DEC}&layer=flags&bits={bits}"
        assert c.get(url).status_code == 200
    legacy = c.get(f"/api/frame/2025W19_1B_0116_1D3/image.png?ra={RA}&dec={DEC}")
    assert legacy.status_code == 200
    for url, code in [
        (f"/api/frame/no_existe/meta?ra={RA}&dec={DEC}", 404),
        (f"/api/frame/../etc/meta?ra={RA}&dec={DEC}", 404),
        (f"/api/frames?ra=abc&dec={DEC}", 422),
        (f"/api/frames?ra={RA}&dec={DEC}&size=5", 422),
        ("/api/frames?ra=1", 422),
        ("/api/frames?target=pluton", 422),
        (f"/api/frame/2025W19_1B_0116_1D3/png?ra={RA}&dec={DEC}&layer=flags&bits=NO_EXISTE", 422),
    ]:
        r = c.get(url)
        assert r.status_code == code, url
        if code != 404 or "etc" not in url:
            assert set(r.json()) == {"error", "detail"}, url


def test_meta_with_nan_target_pixel(client, monkeypatch):
    """Un píxel NaN en el objetivo (estrella saturada) no rompe el JSON: viaja como null."""
    from app import cache as cache_mod
    real = cache_mod.compact_from_fits

    def with_nan(raw):
        c = real(raw)
        c.image[:] = np.nan
        return c

    monkeypatch.setattr(cache_mod, "compact_from_fits", with_nan)
    c, _ = client
    f = c.get("/api/frames", params={"ra": RA, "dec": DEC, "prefetch": False}).json()["frames"][1]
    r = c.get(f["meta_url"])
    assert r.status_code == 200 and r.json()["target"]["value"] is None
