# BRIO-MNS fixed-instance experiment package

This package runs BRIO-MNS and its controlled comparisons on the ten XML100
instances stored in `fixed_datasets/`. The experiment entry point reads this
directory directly and checks that its contents match the expected instance
list before a run begins.

## Requirements

- CPython 3.9 or newer
- Windows, Linux, or macOS
- No third-party Python packages are required for the controlled experiments

## Fixed instances

```text
XML100_1115_01
XML100_1316_21
XML100_2111_20
XML100_2112_20
XML100_2115_17
XML100_2313_03
XML100_2315_06
XML100_2315_23
XML100_3315_02
XML100_3315_06
```

Each `.vrp` file is accompanied by the corresponding XML100 `.sol` file.

## Experiment protocols

| Protocol | Methods | Runs per instance | Population/shared pool | Full-scan budget | Run seeds |
|---|---|---:|---:|---:|---|
| `full` | GA, BRIO-MNS | 10 | 80 | 32,480 | 42026--42035 |
| `multibaseline` | GA, SA-F, ACO-F, TS-F, DPSO-F, BRIO-MNS | 3 | 40 | 8,240 | 52026--52028 |
| `ablation` | BRIO-MNS and four controlled variants | 10 | 40 | 8,240 | 72026--72035 |

For every instance, 500 calibration permutations are generated from base seed
314159 to determine the fixed scales. Evaluations of the shared initialization
pool are included in the budget. A cached chromosome does not consume another
full-scan evaluation.

## Commands

Run a short environment check:

```bash
python run_experiments.py --protocol all --smoke-test
```

Run one formal protocol:

```bash
python run_experiments.py --protocol full
python run_experiments.py --protocol multibaseline
python run_experiments.py --protocol ablation
```

Run all protocols:

```bash
python run_experiments.py --protocol all
```

Results are written below `outputs/`. Every run directory contains raw run
records, per-instance summaries, fixed scales, protocol metadata, and aggregate
diagnostics.

## Verify the bundled reference results

```bash
python verify_results.py
```

A successful check prints `"status": "PASS"`. The verifier recomputes the
full-budget paired comparison, controlled-baseline ranks, ablation seed-block
effects, exact Wilcoxon tests, and Holm-adjusted p-values from the bundled raw
CSV files.

## Main files

- `run_experiments.py`: fixed protocol definitions and command-line entry point
- `experiment_runner.py`: paired-run engine and output writer
- `experiment_v2.py`: BRIO-MNS, controlled baselines, and ablation variants
- `algorithms.py`: genetic search components
- `utils.py`: objective evaluation, normalization, and cache accounting
- `dataset_tools.py`: XML100 parser and EUC_2D distance construction
- `verify_results.py`: independent recomputation of reported metrics
- `reference_results/`: raw CSV records used by the verification script
