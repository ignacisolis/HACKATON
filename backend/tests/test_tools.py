"""Tests sin red: colecciones, cobertura, precálculo y actualización de release."""
from __future__ import annotations

import json

import pytest

from app import irsa, precompute, release_update
from app.settings import load_settings
from conftest import DEC, RA, TAP_ROWS


def test_query_filters_by_collection(settings):
    q = irsa.build_query(RA, DEC, settings)
    for c in settings.collections:
        assert f"ivo://irsa.ipac/{c}?%" in q
    assert "_cal" not in q


def test_bad_collection_name_rejected(settings, monkeypatch):
    bad = settings.__class__(**{**settings.__dict__, "collections": ("spherex_qr2'; --",)})
    with pytest.raises(ValueError):
        irsa.build_query(RA, DEC, bad)


def test_collection_parsed_from_did(settings):
    obs = irsa.parse_rows(TAP_ROWS, settings)
    by_id = {o.id: o for o in obs}
    assert by_id["2025W19_1B_0116_1D3"].collection == "" or by_id["2025W19_1B_0116_1D3"].collection.startswith("spherex_")
    row = {**TAP_ROWS[2], "obs_publisher_did": "ivo://irsa.ipac/spherex_qr3_deep?2026W30_1B_0150_3/D1"}
    assert irsa.parse_rows([row], settings)[0].collection == "spherex_qr3_deep"


def test_coverage(client, settings):
    c, calls = client
    body = c.get("/api/coverage", params={"ra": RA, "dec": DEC}).json()
    assert body["total"] == 2
    assert body["detectors"] == {"D1": 1, "D3": 1}
    assert body["bands_known"] == 0 and body["bands"] == {}
    assert len(body["epochs"]) == 1 and body["epochs"][0]["count"] == 2
    assert calls["cutout"] == 0  # la cobertura nunca baja cutouts

    frames = c.get("/api/frames", params={"ra": RA, "dec": DEC, "prefetch": False}).json()["frames"]
    c.get(frames[1]["meta_url"])  # cachea un cutout (λ = 2.0 µm en D3)
    body = c.get("/api/coverage", params={"ra": RA, "dec": DEC}).json()
    assert body["bands_known"] == 1
    from app import science
    assert body["bands"] == {str(science.band_of(3, 2.0)): 1}


def test_target_position_matches_core():
    """La interpolación del backend reproduce core.targets.target_position (< 0.001″)."""
    from app import science
    from core import targets as tg
    a, b = science.window_mjd()
    for key in science.target_keys():
        for m in (a, (a + b) / 2, b, a + 123.4):
            ra1, dec1 = science.target_radec(key, m)
            ra2, dec2 = tg.target_position(key, m)
            assert tg.separation_arcsec(ra1, dec1, ra2, dec2) < 1e-3, key


def test_target_query_uses_core_position(client):
    """?target=wise_0855 centra el recorte donde está el objeto en 2026, no en el enunciado."""
    from app import science
    c, _ = client
    body = c.get("/api/frames", params={"target": "wise_0855", "prefetch": False}).json()
    q = body["query"]
    ra, dec, epoch = science.window_center("wise_0855")
    assert (q["ra"], q["dec"], q["target"]) == (ra, dec, "wise_0855")
    assert q["resolved_from"] == "targets.yaml + movimiento propio" and q["coord_epoch_applied"] == epoch
    # el enunciado da 08h55m10.831s -7d14m42.53s: ~2′ (≈ 21 px) de distancia
    assert abs(ra - 133.79513) * 3600 > 100
    assert "target=wise_0855" in body["frames"][0]["image_url"]


def test_precompute_and_targets(client, monkeypatch):
    from app import science
    c, calls = client
    monkeypatch.setattr(science, "target_keys", lambda: ["wise_0855"])
    assert precompute.main([]) == 0
    targets = c.get("/api/targets").json()["targets"]
    assert targets[0]["key"] == "wise_0855" and targets[0]["cached"] == targets[0]["frames"] == 2
    # la demo ya no toca IRSA
    before = dict(calls)
    body = c.get(targets[0]["frames_url"] + "&prefetch=false").json()
    assert body["complete"] and calls == before


def test_write_collections_keeps_comments(tmp_path):
    from app.settings import DEFAULT_CONFIG
    p = tmp_path / "release.yaml"
    p.write_text(DEFAULT_CONFIG.read_text())
    release_update.write_collections(p, ["spherex_qr2", "spherex_qr4"])
    text = p.read_text()
    assert "collections: [spherex_qr2, spherex_qr4]" in text
    assert "# Colecciones de IRSA" in text
    assert load_settings(p).collections == ("spherex_qr2", "spherex_qr4")


def test_release_update_check_and_apply(settings, monkeypatch, tmp_path):
    cfg = tmp_path / "release.yaml"
    from app.settings import DEFAULT_CONFIG
    cfg.write_text(DEFAULT_CONFIG.read_text())
    monkeypatch.setenv("SPHEREX_CONFIG", str(cfg))
    available = [
        {"collection": c, "n": 1, "mjd_min": 60800.0 + i, "mjd_max": 60900.0 + i}
        for i, c in enumerate(["spherex_qr2", "spherex_qr2_cal", "spherex_qr3", "spherex_qr4"])
    ]
    available[1].update(mjd_min=None, mjd_max=None)  # IRSA devuelve calibraciones sin fechas
    monkeypatch.setattr(irsa, "list_collections", lambda s=None: available)
    monkeypatch.setattr(release_update, "get_settings", lambda: load_settings(cfg))
    monkeypatch.setattr(release_update, "run_tests", lambda: 0)
    (settings.cache_dir / "queries").mkdir(parents=True)
    (settings.cache_dir / "queries" / "x.json").write_text(json.dumps([]))

    assert release_update.main([]) == 0
    assert "spherex_qr4" not in cfg.read_text()  # sin --apply no cambia nada

    monkeypatch.setattr(release_update, "get_settings", lambda: load_settings(cfg))
    assert release_update.main(["--apply"]) == 0
    cols = load_settings(cfg).collections
    assert "spherex_qr4" in cols and "spherex_qr2_cal" not in cols
    assert not (load_settings(cfg).cache_dir / "queries").exists()
