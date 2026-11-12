"""Resta (/api/diff), pares restables, display_range, índice en disco y reintentos a IRSA."""
from __future__ import annotations

import httpx
import pytest

from app import frames, irsa
from conftest import DEC, RA, TAP_ROWS, fake_mef

# Otra exposición de D3 (λ = 2.0 µm en el MEF falso): comparable con 2025W19_1B_0116_1D3.
ROW_D3_B = {**TAP_ROWS[0],
            "uri": TAP_ROWS[0]["uri"].replace("0116_1D3", "0200_1D3"),
            "obs_publisher_did": "ivo://irsa.ipac/spherex_qr2?2025W45_1B_0200_1/D3",
            "time_bounds_lower": "60990.5", "time_bounds_upper": "60990.6"}
A, B, D1 = "2025W19_1B_0200_1D3", "2025W19_1B_0116_1D3", "2025W19_1B_0100_2D1"


@pytest.fixture
def three(client, monkeypatch):
    c, calls = client
    monkeypatch.setattr(irsa, "_tap", lambda q, s: TAP_ROWS + [ROW_D3_B])
    for f in c.get("/api/frames", params={"ra": RA, "dec": DEC, "prefetch": False}).json()["frames"]:
        c.get(f["meta_url"])  # deja los 3 cuadros en caché
    return c, calls


def test_frames_bring_display_range(three):
    c, _ = three
    body = c.get("/api/frames", params={"ra": RA, "dec": DEC, "prefetch": False}).json()
    dr = body["frames"][0]["display_range"]
    lo, hi = dr["zscale"]
    assert lo < hi and dr["p99_7"] >= lo


def test_diff_png_and_json(three):
    c, _ = three
    r = c.get("/api/diff", params={"a": A, "b": B, "ra": RA, "dec": DEC})
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert float(r.headers["X-Dipole-SNR"]) >= 0 and r.headers["X-Dipole-Detected"] in {"true", "false"}
    j = c.get("/api/diff", params={"a": A, "b": B, "ra": RA, "dec": DEC, "format": "json"}).json()
    assert j["unit"] == "MJy/sr" and j["dt_days"] > 0 and "detected" in j["dipole"]
    assert j["a"]["detector"] == j["b"]["detector"] == "D3"


def test_diff_cors_exposes_headers(three):
    c, _ = three
    r = c.get("/api/diff", params={"a": A, "b": B, "ra": RA, "dec": DEC}, headers={"Origin": "https://x.vercel.app"})
    assert "X-Dipole-SNR" in r.headers["access-control-expose-headers"]


def test_diff_rejects_other_detector_and_unknown_id(three):
    c, _ = three
    r = c.get("/api/diff", params={"a": A, "b": D1, "ra": RA, "dec": DEC})
    assert r.status_code == 422 and r.json()["error"] == "not_comparable"
    assert "detectores distintos" in r.json()["detail"]
    r = c.get("/api/diff", params={"a": A, "b": "no_existe", "ra": RA, "dec": DEC})
    assert r.status_code == 404 and r.json()["error"] == "not_found"


def test_pairs_from_index(three):
    c, _ = three
    body = c.get("/api/pairs", params={"ra": RA, "dec": DEC}).json()
    assert body["n_pairs"] == 1 and body["pending"] == 0
    p = body["pairs"][0]
    assert (p["a"], p["b"], p["detector"]) == (A, B, "D3") and p["dt_days"] > 0  # a = la más reciente
    assert c.get(p["diff_url"]).status_code == 200


def test_index_on_disk_avoids_npz(three, settings, monkeypatch):
    """Con el índice escrito, una consulta nueva (memoria vacía) no abre ningún .npz."""
    c, _ = three
    c.get("/api/frames", params={"ra": RA, "dec": DEC, "prefetch": False})
    assert list((settings.cache_dir / "index").glob("*.json"))
    frames._summary_memo.clear()
    frames._index_loaded.clear()

    def boom(*a, **k):
        raise AssertionError("abrió un .npz pese al índice")

    monkeypatch.setattr(frames.cache, "get_cached", boom)
    body = c.get("/api/frames", params={"ra": RA, "dec": DEC, "prefetch": False}).json()
    assert body["complete"] and all(f["wavelength_um"] == pytest.approx(2.0) for f in body["frames"]
                                    if f["detector"] == "D3")


# ---------- reintentos ----------

def _resp(status, content=b"", headers=None):
    return httpx.Response(status, content=content, headers=headers or {},
                          request=httpx.Request("GET", "https://irsa.example/x"))


@pytest.fixture
def no_sleep(monkeypatch):
    """Reloj falso: sleep() no espera, solo adelanta monotonic(). Así la pausa compartida termina."""
    clock = {"t": 1000.0}
    slept = []

    def fake_sleep(sec):
        slept.append(sec)
        clock["t"] += sec

    monkeypatch.setattr(irsa.time, "sleep", fake_sleep)
    monkeypatch.setattr(irsa.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(irsa, "_pause_until", 0.0)
    return slept


def test_retry_503_then_ok_respects_retry_after(settings, monkeypatch, no_sleep):
    seq = [_resp(503, headers={"Retry-After": "7"}), _resp(503), _resp(200, fake_mef())]
    monkeypatch.setattr(irsa.httpx, "request", lambda *a, **k: seq.pop(0))
    assert irsa.fetch_cutout("ibe/x.fits", RA, DEC, 0.1, settings).startswith(b"SIMPLE")
    assert no_sleep[0] == 7  # Retry-After manda (lo que se durmió después es la pausa compartida)
    assert irsa._pause_until > 0  # el 503 pausó a todos los hilos


def test_no_retry_on_404(settings, monkeypatch, no_sleep):
    calls = []
    monkeypatch.setattr(irsa.httpx, "request", lambda *a, **k: calls.append(1) or _resp(404))
    with pytest.raises(irsa.IrsaError):
        irsa.fetch_cutout("ibe/x.fits", RA, DEC, 0.1, settings)
    assert len(calls) == 1 and no_sleep == []


def test_gives_up_after_max_attempts(settings, monkeypatch, no_sleep):
    def down(*a, **k):
        raise httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(irsa.httpx, "request", down)
    with pytest.raises(irsa.IrsaError, match="6 intentos"):
        irsa.fetch_cutout("ibe/x.fits", RA, DEC, 0.1, settings)
    assert len(no_sleep) == irsa.MAX_ATTEMPTS - 1
    assert no_sleep == sorted(no_sleep) or max(no_sleep) <= irsa.MAX_DELAY_S * 1.25


def test_backoff_grows_and_caps():
    assert irsa.backoff_delay(0) <= 2.5 and irsa.backoff_delay(3) >= 12
    assert irsa.backoff_delay(10) <= irsa.MAX_DELAY_S * 1.25
    assert irsa.backoff_delay(0, retry_after=500) == irsa.MAX_DELAY_S


def test_spectrum_saved_to_disk_and_memory_guard(three, settings, monkeypatch):
    from app import science
    from core.datatypes import SpectrumPoint

    c, _ = three
    monkeypatch.setattr(science.core, "extract_spectrum", lambda frames, **kw: [
        SpectrumPoint(f.wavelength_um, f.bandwidth_um, 1.0, 0.1, f.mjd, f.detector, 9, 0.0) for f in frames])
    monkeypatch.setattr(science.core, "combine", lambda pts: pts)
    assert c.get("/api/spectrum", params={"ra": RA, "dec": DEC}).status_code == 200
    saved = list((settings.cache_dir / "spectra").glob("*.json"))
    assert len(saved) == 1

    # con el archivo en disco ya no se recalcula (core puede ni existir)
    frames._spectrum_memo.clear()
    monkeypatch.setattr(science.core, "extract_spectrum", lambda *a, **k: 1 / 0)
    assert c.get("/api/spectrum", params={"ra": RA, "dec": DEC}).json()["n_frames_cached"] == 3

    # sin precálculo y con más cuadros que el límite: 503 en JSON, no un servidor sin memoria
    frames._spectrum_memo.clear()
    saved[0].unlink()
    monkeypatch.setenv("SPHEREX_SPECTRUM_MAX_FRAMES", "2")
    r = c.get("/api/spectrum", params={"ra": RA, "dec": DEC})
    assert r.status_code == 503 and r.json()["error"] == "too_heavy"


def test_lightcurve_reads_stored_exposures(three, monkeypatch):
    """Con el espectro guardado, la curva de luz no vuelve a abrir cuadros ni a hacer fotometría."""
    from app import science
    from core.datatypes import SpectrumPoint

    c, _ = three
    monkeypatch.setattr(science.core, "extract_spectrum", lambda frames, **kw: [
        SpectrumPoint(f.wavelength_um, f.bandwidth_um, 1.0 + i, 0.1, f.mjd, f.detector, 9, 0.0,
                      band=science.band_of(int(f.detector[1]), f.wavelength_um))
        for i, f in enumerate(frames)])
    monkeypatch.setattr(science.core, "combine", lambda pts: pts)
    assert c.get("/api/spectrum", params={"ra": RA, "dec": DEC}).status_code == 200

    monkeypatch.setattr(science.core, "extract_spectrum", lambda *a, **k: 1 / 0)
    band = science.band_of(3, 2.0)
    r = c.get("/api/lightcurve", params={"ra": RA, "dec": DEC, "band": band})
    assert r.status_code == 200
    body = r.json()
    assert len(body["mjds"]) == 2 and body["mjds"] == sorted(body["mjds"])  # los dos cuadros de D3


def test_root_redirects_to_docs(client):
    c, _ = client
    r = c.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/docs"


# ---------- comprobación física del dipolo y mejores pares ----------

def test_motion_check_direction_and_size(settings):
    from app import science

    q = frames.resolve(None, None, 0.1, "eps_ind_b")
    a, b = science.window_mjd()  # ~525 días: eps Ind B se corre ~1.1 px
    ok = frames.motion_check(q, b, a, {"detected": True, "pos_xy": None, "neg_xy": None})
    ex, ey = ok["expected_px"]
    assert 0.9 < ok["expected_len_px"] < 1.3
    # dipolo en la dirección esperada -> consistente; al revés -> no
    good = {"detected": True, "pos_xy": [10 + round(ex), 10 + round(ey)], "neg_xy": [10, 10]}
    bad = {"detected": True, "pos_xy": [10 - round(ex), 10 - round(ey)], "neg_xy": [10, 10]}
    assert frames.motion_check(q, b, a, good)["consistent"]
    assert not frames.motion_check(q, b, a, bad)["consistent"]
    # sin movimiento esperado (misma fecha) nunca se afirma movimiento
    assert not frames.motion_check(q, a, a, good)["consistent"]
    # un dipolo no detectado tampoco
    assert not frames.motion_check(q, b, a, {**good, "detected": False})["consistent"]


def test_best_pairs_and_targets(three, settings, monkeypatch):
    from app import best_pairs, precompute, science

    c, _ = three
    monkeypatch.setattr(science, "target_keys", lambda: ["wise_0855"])
    monkeypatch.setattr(irsa, "_tap", lambda q, s: TAP_ROWS + [ROW_D3_B])
    assert precompute.main([]) == 0
    assert best_pairs.main(["--per-detector", "5"]) == 0
    t = c.get("/api/targets").json()["targets"][0]
    assert t["motion"]["claim"] in {"confirmado", "indicio", "no"}
    assert t["best_pair"] is None or t["best_pair"]["diff_url"].startswith("/api/diff?")
