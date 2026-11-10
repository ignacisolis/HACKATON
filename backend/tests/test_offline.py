"""Tests sin red: configuración, parseo TAP, bandas y API con IRSA simulado."""
from __future__ import annotations

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS
from fastapi.testclient import TestClient

from app import cache, frames, irsa, main
from app.settings import load_settings

TAP_ROWS = [
    {"uri": "ibe/data/spherex/qr2/level2/2025W19_1B/l2b-v20-2025-241/3/"
            "level2_2025W19_1B_0116_1D3_spx_l2b-v20-2025-241.fits",
     "contentlength": "71634240", "time_bounds_lower": "60800.700028", "time_bounds_upper": "60800.701361",
     "time_exposure": "113.58", "energy_bandpassname": "SPHEREx-D3",
     "energy_bounds_lower": "1.6301e-06", "energy_bounds_upper": "2.4346e-06"},
    # misma exposición, versión más nueva: debe reemplazar a la anterior
    {"uri": "ibe/data/spherex/qr2/level2/2025W19_1B/l2b-v24-2026-115/3/"
            "level2_2025W19_1B_0116_1D3_spx_l2b-v24-2026-115.fits",
     "contentlength": "1", "time_bounds_lower": "60800.700028", "time_bounds_upper": "60800.701361",
     "time_exposure": "113.58", "energy_bandpassname": "SPHEREx-D3",
     "energy_bounds_lower": "1.6301e-06", "energy_bounds_upper": "2.4346e-06"},
    {"uri": "ibe/data/spherex/qr2/level2/2025W19_1B/l2b-v20-2025-241/1/"
            "level2_2025W19_1B_0100_2D1_spx_l2b-v20-2025-241.fits",
     "contentlength": "1", "time_bounds_lower": "60800.5", "time_bounds_upper": "60800.6",
     "time_exposure": "113.58", "energy_bandpassname": "SPHEREx-D1",
     "energy_bounds_lower": "7.455e-07", "energy_bounds_upper": "1.1167e-06"},
]

RA, DEC = 133.79513, -7.24515


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setenv("SPHEREX_CACHE_DIR", str(tmp_path / "cache"))
    s = load_settings()
    monkeypatch.setattr("app.settings.get_settings", lambda: s)
    for mod in (cache, frames, irsa, main):
        monkeypatch.setattr(mod, "get_settings", lambda: s, raising=False)
    return s


def fake_mef(ra=RA, dec=DEC, n=21) -> bytes:
    """MEF mínimo con la misma estructura que un cutout de SPHEREx (sin PSF)."""
    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crval = [ra, dec]
    w.wcs.crpix = [(n + 1) / 2, (n + 1) / 2]
    w.wcs.cdelt = [-6.15 / 3600, 6.15 / 3600]
    hdr = w.to_header()
    hdr["BUNIT"] = "MJy / sr"
    hdr["DATE-OBS"] = "2025-05-05T16:48:02.459"
    # WCS espectral "W" como tabla, igual que en los archivos reales
    hdr.update({
        "WCSAXESW": 2, "CTYPE1W": "WAVE-TAB", "CTYPE2W": "WAVE-TAB", "CUNIT1W": "um", "CUNIT2W": "um",
        "CRPIX1W": 0, "CRPIX2W": 0, "CDELT1W": 1, "CDELT2W": 1, "CRVAL1W": 1, "CRVAL2W": 1,
        "PV1_3W": 1, "PV2_3W": 2, "PS1_0W": "WCS-WAVE", "PS2_0W": "WCS-WAVE",
        "PS1_1W": "VALUES", "PS2_1W": "VALUES", "PS1_2W": "X", "PS2_2W": "Y",
    })
    img = np.random.default_rng(0).normal(1, 0.1, (n, n)).astype(np.float32)
    flags = np.zeros((n, n), np.int32)
    flags[n // 2, n // 2] = 1 << 21
    fh = fits.Header()
    fh["MP_SOURCE"] = (21, "Pixel mapped to a known source")
    fh["MP_HOT"] = (10, "Hot pixel")
    xs = np.array([0, n + 1], np.int32)
    ys = np.array([0, n + 1], np.int32)
    vals = np.zeros((2, 2, 2), np.float32)
    vals[..., 0] = 2.0   # λ = 2.0 µm en todo el recorte
    vals[..., 1] = 0.05
    col_x = fits.Column("X", format="2J", array=[xs])
    col_y = fits.Column("Y", format="2J", array=[ys])
    col_v = fits.Column("VALUES", format="8E", dim="(2,2,2)", array=[vals])
    wave = fits.BinTableHDU.from_columns([col_x, col_y, col_v], name="WCS-WAVE")
    hdul = fits.HDUList([
        fits.PrimaryHDU(),
        fits.ImageHDU(img, hdr, name="IMAGE"),
        fits.ImageHDU(flags, fh, name="FLAGS"),
        fits.ImageHDU(img * 0.01, name="VARIANCE"),
        fits.ImageHDU(img * 0.5, name="ZODI"),
        fits.ImageHDU(np.zeros((2, 3, 3), np.float32), name="PSF"),
        wave,
    ])
    import io
    buf = io.BytesIO()
    hdul.writeto(buf)
    return buf.getvalue()


def test_release_config(settings):
    assert settings.release_name == "qr2"
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


@pytest.fixture
def client(settings, monkeypatch):
    calls = {"tap": 0, "cutout": 0}

    def fake_tap(query, s):
        calls["tap"] += 1
        return TAP_ROWS

    def fake_fetch(uri, ra, dec, size, s=None, retries=2):
        calls["cutout"] += 1
        return fake_mef(ra, dec)

    monkeypatch.setattr(irsa, "_tap", fake_tap)
    monkeypatch.setattr(irsa, "fetch_cutout", fake_fetch)
    return TestClient(main.app), calls


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
