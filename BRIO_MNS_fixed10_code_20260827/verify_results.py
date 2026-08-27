"""Recompute reported metrics from the bundled fixed-10 raw results.

The CSV columns are accessed by their stable positions so this verifier also
works on terminals that do not display the original Chinese headers correctly.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parent
FULL = "BRIO-MNS"

FIELD = {
    "dataset": 0,
    "capacity": 1,
    "algorithm": 6,
    "F": 7,
    "D": 8,
    "BD": 9,
    "BL": 10,
    "run": 19,
    "seed": 20,
}


def read_runs(paths: list[Path]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader)
            if len(header) <= max(FIELD.values()):
                raise ValueError(f"unexpected CSV schema: {path}")
            for raw in reader:
                if not raw:
                    continue
                rows.append(
                    {
                        "dataset": raw[FIELD["dataset"]],
                        "capacity": int(raw[FIELD["capacity"]]),
                        "algorithm": raw[FIELD["algorithm"]],
                        "F": float(raw[FIELD["F"]]),
                        "D": float(raw[FIELD["D"]]),
                        "BD": float(raw[FIELD["BD"]]),
                        "BL": float(raw[FIELD["BL"]]),
                        "run": int(raw[FIELD["run"]]),
                        "seed": int(raw[FIELD["seed"]]),
                    }
                )
    return rows


def average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and math.isclose(
            values[order[start]], values[order[end]], rel_tol=0.0, abs_tol=1e-15
        ):
            end += 1
        rank = ((start + 1) + end) / 2.0
        for index in order[start:end]:
            ranks[index] = rank
        start = end
    return ranks


def wilcoxon_exact(differences: list[float], alternative: str) -> float:
    nonzero = [value for value in differences if abs(value) > 1e-15]
    ranks = average_ranks([abs(value) for value in nonzero])
    observed = sum(rank for rank, value in zip(ranks, nonzero) if value > 0)
    totals = [
        sum(rank for bit, rank in zip(bits, ranks) if bit)
        for bits in itertools.product((0, 1), repeat=len(ranks))
    ]
    denominator = float(len(totals))
    lower = sum(total <= observed + 1e-12 for total in totals) / denominator
    upper = sum(total >= observed - 1e-12 for total in totals) / denominator
    if alternative == "greater":
        return upper
    if alternative == "two-sided":
        return min(1.0, 2.0 * min(lower, upper))
    raise ValueError(f"unknown alternative: {alternative}")


def mapping(rows: list[dict[str, object]]) -> dict[tuple[str, int, str], dict[str, object]]:
    result: dict[tuple[str, int, str], dict[str, object]] = {}
    for row in rows:
        key = (str(row["dataset"]), int(row["run"]), str(row["algorithm"]))
        if key in result:
            raise ValueError(f"duplicate run key: {key}")
        result[key] = row
    return result


def summarize_full(rows: list[dict[str, object]]) -> dict[str, object]:
    algorithms = {str(row["algorithm"]) for row in rows}
    if algorithms != {"GA", FULL}:
        raise ValueError(f"full verification algorithms mismatch: {sorted(algorithms)}")
    datasets = sorted({str(row["dataset"]) for row in rows})
    runs = sorted({int(row["run"]) for row in rows})
    if len(datasets) != 10 or runs != list(range(1, 11)):
        raise ValueError("full verification must contain 10 datasets x 10 runs")

    table = mapping(rows)
    improvements = []
    component_improvements: dict[str, list[float]] = defaultdict(list)
    mean_differences = []
    paired_wins = paired_losses = 0
    for dataset in datasets:
        ga_rows = [table[(dataset, run, "GA")] for run in runs]
        full_rows = [table[(dataset, run, FULL)] for run in runs]
        for left, right in zip(ga_rows, full_rows):
            if (left["run"], left["seed"]) != (right["run"], right["seed"]):
                raise ValueError(f"unpaired full-verification rows: {dataset}")
            if float(right["F"]) < float(left["F"]):
                paired_wins += 1
            elif float(right["F"]) > float(left["F"]):
                paired_losses += 1

        ga_f = mean(float(row["F"]) for row in ga_rows)
        full_f = mean(float(row["F"]) for row in full_rows)
        improvements.append((ga_f - full_f) / ga_f)
        mean_differences.append(ga_f - full_f)
        for metric in ("D", "BD", "BL"):
            ga_value = mean(float(row[metric]) for row in ga_rows)
            full_value = mean(float(row[metric]) for row in full_rows)
            component_improvements[metric].append((ga_value - full_value) / ga_value)

    return {
        "datasets": len(datasets),
        "runs_per_dataset": len(runs),
        "paired_comparisons": len(datasets) * len(runs),
        "mean_instance_relative_improvement": mean(improvements),
        "minimum_instance_relative_improvement": min(improvements),
        "maximum_instance_relative_improvement": max(improvements),
        "instance_wins": sum(value > 0 for value in improvements),
        "paired_wins": paired_wins,
        "paired_losses": paired_losses,
        "instance_level_exact_wilcoxon_p_two_sided": wilcoxon_exact(
            mean_differences, "two-sided"
        ),
        "mean_D_improvement": mean(component_improvements["D"]),
        "mean_BD_improvement": mean(component_improvements["BD"]),
        "mean_BL_improvement": mean(component_improvements["BL"]),
    }


def summarize_multibaseline(rows: list[dict[str, object]]) -> dict[str, object]:
    expected_algorithms = {"GA", "SA-F", "ACO-F", "TS-F", "DPSO-F", FULL}
    algorithms = sorted({str(row["algorithm"]) for row in rows})
    if set(algorithms) != expected_algorithms:
        raise ValueError(f"multibaseline algorithms mismatch: {algorithms}")
    datasets = sorted({str(row["dataset"]) for row in rows})
    runs = sorted({int(row["run"]) for row in rows})
    if len(datasets) != 10 or runs != [1, 2, 3]:
        raise ValueError("multibaseline must contain 10 datasets x 3 runs")

    table = mapping(rows)
    rank_values: dict[str, list[float]] = defaultdict(list)
    improvements: dict[str, list[float]] = defaultdict(list)
    full_wins = defaultdict(int)
    full_losses = defaultdict(int)
    instance_firsts = defaultdict(int)

    for dataset in datasets:
        means = {
            algorithm: mean(
                float(table[(dataset, run, algorithm)]["F"]) for run in runs
            )
            for algorithm in algorithms
        }
        ranks = average_ranks([means[algorithm] for algorithm in algorithms])
        for algorithm, rank in zip(algorithms, ranks):
            rank_values[algorithm].append(rank)
            if math.isclose(rank, 1.0, rel_tol=0.0, abs_tol=1e-12):
                instance_firsts[algorithm] += 1
            if algorithm == FULL:
                improvements[algorithm].append(0.0)
            else:
                improvements[algorithm].append(
                    (means[algorithm] - means[FULL]) / means[algorithm]
                )

        for run in runs:
            full_value = float(table[(dataset, run, FULL)]["F"])
            for algorithm in algorithms:
                if algorithm == FULL:
                    continue
                candidate = float(table[(dataset, run, algorithm)]["F"])
                if full_value < candidate:
                    full_wins[algorithm] += 1
                elif full_value > candidate:
                    full_losses[algorithm] += 1

    return {
        algorithm: {
            "mean_rank": mean(rank_values[algorithm]),
            "mean_full_improvement": mean(improvements[algorithm]),
            "full_wins": int(full_wins[algorithm]),
            "full_losses": int(full_losses[algorithm]),
            "instance_firsts": int(instance_firsts[algorithm]),
        }
        for algorithm in algorithms
    }


def holm_adjust(raw: dict[str, float]) -> dict[str, float]:
    ordered = sorted(raw, key=raw.__getitem__)
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for index, name in enumerate(ordered):
        running = max(running, min(1.0, (total - index) * raw[name]))
        adjusted[name] = running
    return adjusted


def summarize_ablation(rows: list[dict[str, object]]) -> dict[str, object]:
    variants = {"No-N6-16", "Distance-Proxy16", "Static-VNS16", "Matched-Random16"}
    algorithms = {str(row["algorithm"]) for row in rows}
    if algorithms != variants | {FULL}:
        raise ValueError(f"ablation algorithms mismatch: {sorted(algorithms)}")
    datasets = sorted({str(row["dataset"]) for row in rows})
    runs = sorted({int(row["run"]) for row in rows})
    if len(datasets) != 10 or runs != list(range(1, 11)):
        raise ValueError("ablation must contain 10 datasets x 10 runs")

    table = mapping(rows)
    result: dict[str, dict[str, object]] = {}
    raw_p: dict[str, float] = {}
    for variant in variants:
        instance_gaps = []
        full_wins = full_losses = 0
        for dataset in datasets:
            candidate_mean = mean(
                float(table[(dataset, run, variant)]["F"]) for run in runs
            )
            full_mean = mean(float(table[(dataset, run, FULL)]["F"]) for run in runs)
            instance_gaps.append((candidate_mean - full_mean) / full_mean)
            for run in runs:
                candidate = float(table[(dataset, run, variant)]["F"])
                full_value = float(table[(dataset, run, FULL)]["F"])
                if candidate > full_value:
                    full_wins += 1
                elif candidate < full_value:
                    full_losses += 1

        seed_blocks = [
            mean(
                (
                    float(table[(dataset, run, variant)]["F"])
                    - float(table[(dataset, run, FULL)]["F"])
                )
                / float(table[(dataset, run, FULL)]["F"])
                for dataset in datasets
            )
            for run in runs
        ]
        raw_p[variant] = wilcoxon_exact(seed_blocks, "greater")
        result[variant] = {
            "mean_instance_gap": mean(instance_gaps),
            "mean_seed_block_gap": mean(seed_blocks),
            "full_wins": full_wins,
            "full_losses": full_losses,
            "positive_seed_blocks": sum(value > 0 for value in seed_blocks),
            "wilcoxon_p_one_sided": raw_p[variant],
        }

    adjusted = holm_adjust(raw_p)
    for variant in variants:
        result[variant]["holm_p"] = adjusted[variant]
    return result


def compare(actual: object, expected: object, path: str = "root") -> list[str]:
    failures: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected object, got {type(actual).__name__}"]
        for key, value in expected.items():
            if key not in actual:
                failures.append(f"{path}.{key}: missing")
            else:
                failures.extend(compare(actual[key], value, f"{path}.{key}"))
        return failures
    if isinstance(expected, float):
        if not math.isclose(float(actual), expected, rel_tol=1e-11, abs_tol=1e-12):
            failures.append(f"{path}: actual={actual!r}, expected={expected!r}")
        return failures
    if actual != expected:
        failures.append(f"{path}: actual={actual!r}, expected={expected!r}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify raw results against paper values.")
    parser.add_argument(
        "--full",
        action="append",
        type=Path,
        help="full-verification all_runs.csv; may be specified more than once",
    )
    parser.add_argument("--multibaseline", type=Path)
    parser.add_argument("--ablation", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    full_paths = args.full or [
        ROOT / "reference_results" / "full_part_a" / "all_runs.csv",
        ROOT / "reference_results" / "full_part_b" / "all_runs.csv",
    ]
    multibaseline = args.multibaseline or (
        ROOT / "reference_results" / "multibaseline" / "all_runs.csv"
    )
    ablation = args.ablation or ROOT / "reference_results" / "ablation" / "all_runs.csv"

    actual = {
        "full_verification": summarize_full(read_runs(full_paths)),
        "multibaseline": summarize_multibaseline(read_runs([multibaseline])),
        "ablation": summarize_ablation(read_runs([ablation])),
    }
    expected = json.loads(
        (ROOT / "expected_metrics.json").read_text(encoding="utf-8")
    )
    failures = compare(actual, expected)

    report = {"status": "PASS" if not failures else "FAIL", "metrics": actual}
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    if failures:
        print("\nMISMATCHES:")
        for failure in failures:
            print("-", failure)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
