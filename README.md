# Morocco Drought & Water Security

Satellite-based assessment of how Morocco's water system responded to the recent
multi-year drought, basin by basin: reservoirs, groundwater and farmland.

**Status:** scaffolding. No analysis code yet.

## Current scope (MVP)

Al Massira reservoir surface area from Sentinel-2 NDWI, compared against CHIRPS
rainfall, 2016–present. Al Massira is the main storage on the Oum Er-Rbia and
supplies Casablanca plus the Doukkala irrigation scheme, so it is the single most
consequential reservoir in the country.

## Planned

- GRACE / GRACE-FO terrestrial water storage as a groundwater proxy
- NDVI for irrigated-farmland response
- Additional basins: Oum Er-Rbia, Sebou, Tensift, Moulouya, Souss-Massa
- Sentinel-1 InSAR subsidence as an independent groundwater-depletion signal
- A reusable datacube tool generalising the pipeline across basins and variables

## Data

All imagery via the [Microsoft Planetary Computer](https://planetarycomputer.microsoft.com/)
STAC API (`sentinel-2-l2a`). CHIRPS rainfall is **not** hosted on Planetary
Computer and is sourced separately from the Climate Hazards Center (UCSB) — see
`docs/decisions.md`.

## Setup

```bash
uv sync --extra dev
```

## Usage

```bash
uv run pytest
uv run ruff check
uv run jupyter lab
```

## Layout

```
src/moroccowater/   importable pipeline code
notebooks/          exploration; imports from src, holds no durable logic
tests/              pytest suite
docs/decisions.md   dated design-decision log
docs/literature.md  prior work and the gaps this project targets
data/               git-ignored; raw downloads are never edited in place
```

## Conventions

See [CLAUDE.md](CLAUDE.md) for the engineering rules that bind this repo —
notably float casting before band arithmetic, the Sentinel-2 January 2022
processing-baseline offset, data-source logging, sanity checks, and explicit
assumption flagging.
