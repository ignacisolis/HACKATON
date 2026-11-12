# HackatonNASA — a web viewer for SPHEREx: the sky over time

**NASA Space Apps · SPHEREx challenge.** Type sky coordinates, get that patch of
sky as a video across time. Pick a detector and a band, share the exact view by
URL, subtract two epochs to reveal moving objects, inspect contamination masks,
and read a spectrum.

> *Este README está en inglés para la entrega. La versión de trabajo del equipo,
> en español y con el roadmap completo, está en [`README.md`](README.md).*

**Live demo:** https://hackaton-lufkey-w.vercel.app

> ⚠️ **Read this before judging the demo.** The public site currently serves the
> **example fixtures** in `contracts/fixtures/`, not live SPHEREx observations.
> The science core and the API both work against real data — this README shows
> measurements taken from real cutouts — but the backend service is not hosted
> yet, so the deployed front end falls back to sample data. Everything is
> reproducible locally against real IRSA data with the commands below.

---

## The challenge

SPHEREx maps the whole sky every six months in **102 near-infrared bands**
(0.75–5.0 µm), sensitive to water, carbon dioxide, and other molecules. The
archive holds images of more than a billion objects — brown dwarfs, quasars,
comets, asteroids, stars, supernovae, galaxies — which **overlap each other and
vary in brightness**. The community needs tools to see and analyse that change.

## What we built

| Challenge requirement | Status |
|---|---|
| **O1** Public, accessible web page | ✅ deployed (sample data, see note above) |
| **O2** Coordinate entry (RA/Dec) | ✅ degrees and sexagesimal |
| **O3** Image series played as video | ✅ play/pause, speed, timeline |
| **O4** Make object motion visible | ✅ via image subtraction — see below |
| **O5** The four required test objects | ✅ validated against real data |
| **C1** Easy to update to new data releases | ✅ release and URLs in `config/release.yaml` |
| **C2/C3** Deliver the 102 bands, user picks one | ✅ `config/bands.yaml`, selector per detector |
| **C4** Coordinates in the URL | ✅ `?target=` or `?ra=&dec=`, plus `fov`, `det`, `band`, `t` |
| **C5** Add/subtract images | ✅ `GET /api/diff`, pairs from `GET /api/pairs` |
| **C6** Metadata and contamination masks | ✅ every FLAGS bit present can be toggled as a layer |
| **C7** Instant spectra | ✅ `GET /api/spectrum` and `/api/lightcurve` |
| **C8** Combine detectors for signal-to-noise | ✅ measured — with an important caveat below |
| **C9** Look at public astronomy sites | ✅ Aladin Lite embedded, links to SIMBAD |

## What we learned from the data

These are the findings that changed the design. All of them came from opening
real files, not from the challenge text. Sources and full detail in
[`docs/ciencia.md`](docs/ciencia.md).

### The coordinates in the challenge are from 2010

WISE 0855's listed position is its **discovery-epoch** position. Its proper
motion is **8.15″/yr**, so by the SPHEREx era the object sits **21.4 pixels**
away from it.

Pointing at the given coordinates does not raise an error. It returns a normal
looking patch of sky, full of other sources, **without the target**. We verified
the catalogue epoch rather than assuming it: propagating the SIMBAD J2000
position forward to 2010.5 reproduces the WISE designation to **0.41″**, where
one year of epoch error would cost 8.15″.

### The flag covering 41 % of pixels is not a defect

Bit 21 of the `FLAGS` layer is **`SOURCE`** — the pipeline's source mask. The
Explanatory Supplement gives **two different masking lists**, and the difference
decides whether photometry works at all:

| | Background estimation | Photometry |
|---|---|---|
| `SOURCE` masked? | **yes** | **no** |

Masking "everything flagged" before measuring deletes the target. Measured on a
real R Draconis cutout: the photometry mask leaves **790 of 841** pixels usable;
the background mask leaves **zero**. Our `mask_for()` therefore refuses to run
without an explicit purpose.

### The six detectors chain, they do not overlap

They tile 0.75–5.01 µm with only ~0.02 µm seams. So **C8 cannot mean stacking
the six detectors onto one band** — they measure different wavelengths. The
signal-to-noise gain comes from **repeat visits to the same band**.

### The 102 bands are logarithmic, and they overlap at the seams

SPHEREx is a constant-resolving-power spectrometer, so bandwidth grows with
wavelength. We derived this from six consecutive real D2 exposures: λ/Δλ is
constant at ~41.4, matching IRSA's published resolving power, and the ratio
between consecutive wavelengths is a constant 1.0244 = 1 + 1/41.4.

Independent check: those six exposures land in bands **28, 29, 30, 31, 32, 33** —
consecutive, one channel apart. A wrongly spaced grid would not do that.

And because the detectors overlap slightly, **a wavelength alone does not
identify a band**: there are six overlapping band pairs, so the band selector
always needs the detector too.

### Consecutive exposures change spectral channel

This one surprised us. Six consecutive D2 exposures gave six *different* bands,
not six measurements of one. Of 45 possible pairs from ten exposures, only
**four were comparable**. And the channel **is not in IRSA's TAP metadata** —
the per-pixel wavelength comes from `WCS-WAVE`, which means opening the FITS.
That is why the backend keeps an on-disk index of the wavelength at the target.

### R Draconis saturates

We first picked R Dra as the best demo target because it has **2,483
observations across 222 dates** — ten times any other. Then we opened the files:
in six of eight cutouts, **zero of ~20 aperture pixels are usable**, with
`BLOOM` and `HALO` set. It is too bright for SPHEREx.

It is still the best target for the **video**. It is not usable for photometry
or spectra. **RW Aurigae** is the one for variability: 6/6 detectors, median
S/N 371, 8 epochs over 372 days, varying by a factor of **7.6**.

### Two results we are proud of

**The spectrum validates against published photometry.** Our spectrum of
WISE 0855, extracted from 18 real cutouts, reproduces the object's known WISE
**W2 flux to within 1 %** at 4.96 µm. The whole chain — proper motion, WCS,
masks, `WCS-WAVE`, aperture, unit conversion — lands on the right number where
the object dominates.

**Motion is detectable.** Subtracting two sky-aligned epochs of **Epsilon Indi B**
separated by 525 days yields a clear dipole, measured by the backend at **72σ and
94σ**. That is objective O4 demonstrated on real data.

### What we are honest about

- **Below 3 µm, WISE 0855's "spectrum" is a blend.** It measures 38–47× the flux
  physically possible for a Y dwarf — a neighbouring source inside the 15.5″
  aperture. This *is* the overlap problem the challenge names, quantified. Fixing
  it needs PSF fitting, not aperture photometry.
- **WISE 0855's motion is not detectable in a single pair.** It moves only
  **1.35 px** across the whole archive, and at the wavelengths we tried it is not
  detected at all. The motion demo works with eps Ind B.
- **Image subtraction does not match PSFs.** Frames resampled with different
  sub-pixel shifts leave residuals up to 6σ around every source.
- `WCS-WAVE` carries a ~0.003 µm systematic (9 % of a bandwidth) from a SIP
  ambiguity. Fine for a viewer, not for published numbers.

## Architecture

```
browser                server                      archive
┌──────────┐          ┌─────────────────────┐     ┌──────┐
│ frontend │ ──────►  │ backend  ──►  core/ │ ──► │ IRSA │
│  React   │ ◄──────  │ FastAPI    pure fns │ ◄── │ NASA │
└──────────┘   JSON   └─────────────────────┘     └──────┘
                 PNG
```

- **`core/`** — pure science functions: arrays in, arrays out. No network, no
  disk, no web framework. Target astrometry, FLAGS decoding, WCS alignment with
  proper motion, comparable-frame subtraction, spectra, the 102-band grid.
- **`backend/`** — the only code that talks to IRSA. TAP queries, compact cache
  without the PSF extension (~100 KB per exposure instead of ~5 MB), an on-disk
  index, retries with exponential backoff, and 11 endpoints.
- **`frontend/`** — Vite + React + TypeScript. Video player, band selector,
  URL-encoded views, FLAGS mask layers, difference panel, spectrum charts,
  Aladin Lite. Interface in English and Spanish.
- **`contracts/api.md`** — the agreed API contract, v1. Frontend and backend only
  talk through it.

## Run it locally, against real data

```bash
pip install -r requirements.txt

# Science layer: regenerate catalogues and check them against real archives
python core/fetch_targets.py          # astrometry from SIMBAD
python core/fetch_coverage.py         # coverage from IRSA
python core/bands.py                  # the 102-band table
python core/validate_targets.py       # validate the four targets (downloads ~250 MB)

# Backend
uvicorn app.main:app --app-dir backend --port 8000
curl "localhost:8000/api/pairs?target=eps_ind_b&detector=D2&limit=1"

# Frontend
cd frontend && npm install && npm run dev        # against the backend on :8000
VITE_USE_FIXTURES=1 npm run dev                  # without a backend
```

## Tests

**164 Python tests**, plus the front-end suite, all run in CI on every push and
pull request.

```bash
python core/test_targets.py     # 10  astrometry, incl. the epoch check
python core/test_flags.py       # 35  FLAGS bits and the two masks
python core/test_align.py       # 26  alignment, incl. the O4 acceptance test
python core/test_subtract.py    # 25  subtraction, co-add, dipole detection
python core/test_spectrum.py    # 34  the 102 bands and spectra
python -m pytest backend/tests  # 34  API contract and offline behaviour
```

CI also enforces two project rules: no module in `core/` opens the network, and
no module in `core/` shadows a Python standard-library name.

## Team

| Role | Owner | Area |
|---|---|---|
| A · Data and backend, integration | Camilo | `backend/`, deployment |
| B · Front end and experience | Bruno | `frontend/`, the web deployment |
| C · Science and processing | Nacho | `core/`, `config/`, `docs/ciencia.md` |

## Sources

- [IRSA · SPHEREx Data Access](https://caltech-ipac.github.io/spherex-archive-documentation/spherex-data-access/)
- [SPHEREx Explanatory Supplement](https://irsa.ipac.caltech.edu/data/SPHEREx/docs/SPHEREx_Expsupp_QR.pdf) (SSDC-DP-017 v2.0) — the `FLAGS` bit table
- SIMBAD (Harvard mirror) for target astrometry; Gaia EDR3 and Kirkpatrick et al. 2021 for the individual measurements, cited per target in `config/targets.yaml`
