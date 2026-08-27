"""Run BRIO-MNS experiments on the bundled ten-instance XML100 suite."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "experiment_runner.py"
DATASETS = ROOT / "fixed_datasets"
ENGINE_OUTPUT = ROOT / "experiment_runs"
OUTPUTS = ROOT / "outputs"

FULL_METHOD = "BRIO-MNS"

PROTOCOLS = {
    "full": {
        "runs": 10,
        "population": 80,
        "ga-generations": 200,
        "ga-phase-generations": 20,
        "budget": 32480,
        "seed": 42025,
        "only": f"GA,{FULL_METHOD}",
    },
    "multibaseline": {
        "runs": 3,
        "population": 40,
        "ga-generations": 100,
        "ga-phase-generations": 10,
        "budget": 8240,
        "seed": 52025,
        "only": f"GA,SA-F,ACO-F,TS-F,DPSO-F,{FULL_METHOD}",
    },
    "ablation": {
        "runs": 10,
        "population": 40,
        "ga-generations": 100,
        "ga-phase-generations": 10,
        "budget": 8240,
        "seed": 72025,
        "only": (
            "Static-VNS16,No-N6-16,Matched-Random16,"
            f"Distance-Proxy16,{FULL_METHOD}"
        ),
    },
}


def validate_fixed_suite() -> None:
    expected = {
        "XML100_1115_01",
        "XML100_1316_21",
        "XML100_2111_20",
        "XML100_2112_20",
        "XML100_2115_17",
        "XML100_2313_03",
        "XML100_2315_06",
        "XML100_2315_23",
        "XML100_3315_02",
        "XML100_3315_06",
    }
    actual = {path.stem for path in DATASETS.glob("*.vrp")}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise RuntimeError(
            f"fixed dataset suite mismatch; missing={missing}, extra={extra}"
        )


def build_command(protocol: str, smoke_test: bool) -> list[str]:
    config = dict(PROTOCOLS[protocol])
    if smoke_test:
        # This small run checks imports, parsing, budgeting, and output generation.
        config.update(
            {
                "runs": 1,
                "population": 20,
                "ga-generations": 2,
                "ga-phase-generations": 1,
                "budget": 400,
            }
        )

    command = [
        sys.executable,
        str(ENGINE),
        "--suite",
        str(DATASETS),
        "--calibration-seed",
        "314159",
        "--calibration-size",
        "500",
        "--dataset-seed-stride",
        "0",
    ]
    for name, value in config.items():
        command.extend((f"--{name}", str(value)))
    if smoke_test:
        command.extend(("--limit", "1"))
    return command


def newest_engine_output(before: set[Path]) -> Path:
    candidates = [
        path
        for path in ENGINE_OUTPUT.iterdir()
        if path.is_dir() and path not in before
    ]
    if not candidates:
        raise RuntimeError("experiment finished but no new output directory was found")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def move_output(source: Path, protocol: str, smoke_test: bool) -> Path:
    OUTPUTS.mkdir(exist_ok=True)
    prefix = "smoke_" if smoke_test else ""
    target = OUTPUTS / f"{prefix}{protocol}_{source.name}"
    suffix = 2
    while target.exists():
        target = OUTPUTS / f"{prefix}{protocol}_{source.name}_{suffix}"
        suffix += 1
    return Path(shutil.move(str(source), str(target)))


def run(protocol: str, smoke_test: bool, dry_run: bool) -> None:
    command = build_command(protocol, smoke_test)
    print(f"\n[{protocol}]", " ".join(command), flush=True)
    if dry_run:
        return

    ENGINE_OUTPUT.mkdir(exist_ok=True)
    before = {path for path in ENGINE_OUTPUT.iterdir() if path.is_dir()}
    subprocess.run(command, cwd=ROOT, check=True)
    generated = newest_engine_output(before)
    final_path = move_output(generated, protocol, smoke_test)
    print(f"[{protocol}] results: {final_path}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the paper's fixed-10-instance BRIO-MNS experiments."
    )
    parser.add_argument(
        "--protocol",
        choices=("full", "multibaseline", "ablation", "all"),
        default="all",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="run one tiny non-paper check instead of the reported budget",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the exact command without running it",
    )
    args = parser.parse_args()

    validate_fixed_suite()
    selected = tuple(PROTOCOLS) if args.protocol == "all" else (args.protocol,)
    for protocol in selected:
        run(protocol, args.smoke_test, args.dry_run)


if __name__ == "__main__":
    main()
