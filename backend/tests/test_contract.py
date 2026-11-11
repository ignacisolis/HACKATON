"""Las respuestas cumplen contracts/api.md: cada campo de los fixtures está, con el mismo tipo.

Si alguien cambia el contrato o los fixtures, estos tests avisan qué endpoint quedó atrás.
El backend puede devolver campos de más (ready, meta_url, collection…), nunca de menos.
"""
from __future__ import annotations

import json

import pytest

from app import science
from app.settings import REPO_ROOT
from core.datatypes import SpectrumPoint

FIXTURES = REPO_ROOT / "contracts" / "fixtures"


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


def assert_shape(got: dict, expected: dict, where: str) -> None:
    for key, value in expected.items():
        if key.startswith("_"):
            continue  # notas internas del fixture
        assert key in got, f"{where}: falta '{key}'"
        if value is None or got[key] is None:
            continue
        if isinstance(value, bool):
            assert isinstance(got[key], bool), f"{where}.{key}: se esperaba bool"
        elif isinstance(value, (int, float)):
            assert isinstance(got[key], (int, float)), f"{where}.{key}: se esperaba número"
        else:
            assert isinstance(got[key], type(value)), f"{where}.{key}: se esperaba {type(value).__name__}"


@pytest.fixture
def cached_target(client):
    """WISE 0855 pedido por target y con un cuadro ya en caché."""
    c, _ = client
    body = c.get("/api/frames", params={"target": "wise_0855", "prefetch": False}).json()
    c.get(body["frames"][1]["meta_url"])  # baja y cachea ese cuadro
    return c, c.get("/api/frames", params={"target": "wise_0855", "prefetch": False}).json()


def test_frames_matches_fixture(cached_target):
    _, body = cached_target
    exp = fixture("frames")
    assert_shape(body, exp, "frames")
    assert_shape(body["query"], exp["query"], "frames.query")
    ready = next(f for f in body["frames"] if f["ready"])
    assert_shape(ready, exp["frames"][0], "frames.frames[]")
    assert ready["detector"] in {f"D{i}" for i in range(1, 7)}
    assert len(ready["target_xy"]) == 2 and ready["quality"] in {"ok", "suspect", "bad"}


def test_frame_meta_matches_fixture(cached_target):
    c, body = cached_target
    ready = next(f for f in body["frames"] if f["ready"])
    meta = c.get(ready["meta_url"]).json()
    exp = fixture("frame-meta")
    assert_shape(meta, exp, "meta")
    assert_shape(meta["flags"], exp["flags"], "meta.flags")
    assert_shape(meta["flags"]["cutout_counts"][0], exp["flags"]["cutout_counts"][0], "meta.flags.cutout_counts[]")
    assert_shape(meta["wcs"], exp["wcs"], "meta.wcs")


def test_spectrum_y_lightcurve_ya_funcionan(cached_target):
    """La tarea 23 esta implementada: los dos endpoints responden con el contrato.

    Antes este test afirmaba lo contrario, que devolvian 501 mientras
    core.extract_spectrum fuera un stub. Al mergear la rama ciencias dejo de ser
    un stub, asi que el test fallaba porque la integracion habia funcionado.

    No se comprueba que las listas vengan con datos: la cache de prueba tiene
    pocos cuadros y de un solo detector, asi que lo normal es que salgan vacias.
    Lo que se fija aca es la FORMA de la respuesta, que es lo que el frontend
    consume.
    """
    c, _ = cached_target

    r = c.get("/api/spectrum", params={"target": "wise_0855"})
    assert r.status_code == 200, r.text
    body = r.json()
    for campo in ("query", "aperture_px", "mask_purpose", "n_points", "points"):
        assert campo in body, campo
    assert body["mask_purpose"] == "photometry", (
        "medir la fuente con la mascara de fondo enmascara SOURCE y borra el objetivo")
    assert isinstance(body["points"], list)

    r = c.get("/api/lightcurve", params={"target": "wise_0855", "band": 30})
    assert r.status_code == 200, r.text
    body = r.json()
    for campo in ("query", "band_range_um", "mjds", "flux", "flux_err"):
        assert campo in body, campo
    assert len(body["mjds"]) == len(body["flux"]) == len(body["flux_err"])


def test_spectrum_matches_fixture_with_core_stub(cached_target, monkeypatch):
    """Con un core falso que respeta las firmas, la respuesta ya tiene la forma del contrato."""
    c, _ = cached_target
    seen = {}

    def fake_extract(frames, target_key=None, ra=None, dec=None, mask_purpose=None, **_):
        seen.update(n=len(frames), key=target_key, purpose=mask_purpose, frame=frames[0])
        return [SpectrumPoint(f.wavelength_um, f.bandwidth_um, 0.3, 0.02, f.mjd, f.detector, 20, 0.1)
                for f in frames]

    monkeypatch.setattr(science.core, "extract_spectrum", fake_extract)
    monkeypatch.setattr(science.core, "combine", lambda pts: pts)
    body = c.get("/api/spectrum", params={"target": "wise_0855"}).json()
    exp = fixture("spectrum")
    assert_shape(body, exp, "spectrum")
    assert_shape(body["points"][0], exp["points"][0], "spectrum.points[]")
    assert body["mask_purpose"] == "photometry" and seen["purpose"] == "photometry"
    assert seen["key"] == "wise_0855" and seen["n"] == 1
    f = seen["frame"]  # el core.Frame que arma el backend
    assert f.detector == "D3" and f.wavelength_um == pytest.approx(2.0) and f.release.startswith("l2b-")
