"""Tests sin red: configuración, parseo TAP, bandas y API con IRSA simulado."""
from __future__ import annotations

import numpy as np
import pytest

from app import cache, irsa
from conftest import DEC, RA, TAP_ROWS, fake_mef


def test_release_config(settings):
    assert "spherex_qr2" in settings.collections
    assert not any(c.endswith("_cal") for c in settings.collections)
    assert set(settings.detectors_um) == {1, 2, 3, 4, 5, 6}


def test_bands_roundtrip(settings):
    for band in (1, 17, 18, 50, 102):
        det, lo, hi = settings.band_range_um(band)
        assert settings.band_of(det, (lo + hi) / 2) == band
    with pytest.raises(ValueError):
        settings.band_range_um(103)


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
    assert body["count"] == 2 and body["pending"] == 2 and not body["complete"]
    f = body["frames"][1]
    assert f["detector"] == 3 and f["ready"] is False

    png = c.get(f["image_url"])
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"
    meta = c.get(f["meta_url"]).json()
    assert meta["wavelength_um"] == pytest.approx(2.0)
    src = next(x for x in meta["flags"] if x["name"] == "SOURCE")
    assert src["bit"] == 21 and src["at_target"] is True

    # 2ª consulta: misma posición en sexagesimal -> ni TAP ni cutout tocan IRSA
    r2 = c.get("/api/frames", params={"ra": "08h55m10.831s", "dec": "-7d14m42.53s", "prefetch": False})
    f2 = next(x for x in r2.json()["frames"] if x["id"] == f["id"])
    assert f2["ready"] and f2["wavelength_um"] == pytest.approx(2.0)
    assert calls == {"tap": 1, "cutout": 1}


def test_band_filter(client):
    c, _ = client
    body = c.get("/api/frames", params={"ra": RA, "dec": DEC, "band": 18, "prefetch": False}).json()
    assert {f["detector"] for f in body["frames"]} == {2} or body["count"] == 0


def test_flags_layer_and_errors(client):
    c, _ = client
    c.get("/api/frames", params={"ra": RA, "dec": DEC, "prefetch": False})
    url = f"/api/frame/2025W19_1B_0116_1D3/image.png?ra={RA}&dec={DEC}&layer=flags&bits=21"
    assert c.get(url).status_code == 200
    assert c.get(f"/api/frame/no_existe/meta?ra={RA}&dec={DEC}").status_code == 404
    assert c.get(f"/api/frame/../etc/meta?ra={RA}&dec={DEC}").status_code == 404
    assert c.get("/api/frames", params={"ra": "abc", "dec": DEC}).status_code == 422
    assert c.get("/api/frames", params={"ra": RA, "dec": DEC, "size": 5}).status_code == 422
