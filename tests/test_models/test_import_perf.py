"""インポート時間テスト（slow）。

通常の ``uv run pytest`` では実行されない（``-m 'not slow'``）。
明示的に ``uv run pytest -m slow`` で実行する。
"""
from __future__ import annotations

import os
import statistics
import subprocess
import sys
from pathlib import Path

import pytest


def _measure_import_and_calibration(root: Path) -> tuple[float, float]:
    """サブプロセスで import 時間とCPU基準時間を測定する。

    Args:
        root: プロジェクトルート。

    Returns:
        (calibration_seconds, import_seconds) のタプル。
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    cmd = [
        sys.executable,
        "-c",
        (
            "import time\n"
            "start = time.perf_counter()\n"
            "total = 0\n"
            "for i in range(5_000_000):\n"
            "    total += i\n"
            "calibration = time.perf_counter() - start\n"
            "start = time.perf_counter()\n"
            "import edinet.models.edinet_code\n"
            "elapsed = time.perf_counter() - start\n"
            "print(f'{calibration:.6f} {elapsed:.6f}')\n"
        ),
    ]
    result = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
    )
    calibration_s, import_s = result.stdout.strip().split()
    return float(calibration_s), float(import_s)


@pytest.mark.slow
def test_import_time_acceptable() -> None:
    """edinet_code の import が環境相対で退化していないことを確認する。

    calibration（CPU ループ）との比率のみで判定し、
    絶対時間では判定しない（WSL・CI 等の環境差を吸収するため）。
    """
    root = Path(__file__).resolve().parents[2]
    runs = int(os.getenv("EDINET_IMPORT_PERF_RUNS", "3"))
    ratio_budget = float(os.getenv("EDINET_IMPORT_PERF_RATIO_BUDGET", "5.0"))

    measurements = [_measure_import_and_calibration(root) for _ in range(runs)]
    median_calibration_s = statistics.median(calibration for calibration, _ in measurements)
    median_import_s = statistics.median(elapsed for _, elapsed in measurements)
    ratio = median_import_s / median_calibration_s

    assert ratio <= ratio_budget, (
        f"edinet_code import/calibration ratio {ratio:.3f} "
        f"(budget={ratio_budget:.3f}, "
        f"import={median_import_s:.3f}s, "
        f"calibration={median_calibration_s:.3f}s, runs={runs})"
    )
