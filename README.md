# BRIO-MNS

Core implementation of structured multi-neighborhood search for unit-demand vehicle routing with a composite distance and dispersion objective.

## Requirements

Python 3.10 or newer. Only the Python standard library is required.

## Usage

Obtain an XML100 benchmark instance from [CVRPLIB](https://vrp.galgos.inf.puc-rio.br/). The runner accepts EUC_2D `.vrp` files with 100 unit-demand customers and a capacity that divides 100, with at least two routes and at least two customers per route.

```bash
python run.py path/to/instance.vrp
python run.py path/to/instance.vrp --seed 7 --budget 2000
```

The output reports the composite objective, its components, evaluation count, search runtime, and customer routes. Route indices are 1–100 after sorting the original customer IDs; depot index is 0. Runtime excludes calibration and initialization.

This repository contains the core implementation and a single-instance runner. The complete benchmark protocols, raw experimental records, and statistical analyses are not included.
