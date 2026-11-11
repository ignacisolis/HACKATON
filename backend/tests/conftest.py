"""Fixtures compartidas: config temporal, IRSA simulado y un MEF falso con estructura SPHEREx."""
from __future__ import annotations

import io

import numpy as np
import pytest
from astropy.io import fits
from astropy.wcs import WCS
from fastapi.testclient import TestClient

from app import cache, frames, irsa, main, precompute
from app.settings import load_settings

TAP_ROWS = [
    {"uri": "ibe/data/spherex/qr2/level2/2025W19_1B/l2b-v20-2025-241/3/"
            "level2_2025W19_1B_0116_1D3_spx_l2b-v20-2025-241.fits",
     "obs_publisher_did": "ivo://irsa.ipac/spherex_qr2?2025W19_1B_0116_1/D3",
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
    for mod in (cache, frames, irsa, main, precompute):
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
    buf = io.BytesIO()
    hdul.writeto(buf)
    return buf.getvalue()


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


