"""Measure the wall-clock cost of one local resource sample on the CI host."""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from faultline.sampler import collect_sample


def main() -> int:
    durations = []
    previous_cpu = None
    for _ in range(30):
        started = time.perf_counter()
        _sample, previous_cpu = collect_sample(previous_cpu)
        durations.append(time.perf_counter() - started)

    ordered = sorted(durations)
    median = statistics.median(ordered)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    print(
        "Sampler collection cost: "
        f"median={median * 1000:.2f} ms, "
        f"p95={p95 * 1000:.2f} ms, "
        f"interval-default=10 s"
    )
    # Use the median as the CI gate; the p95 is reported but can include shared-runner
    # scheduling pauses unrelated to the sampler's work.
    if median > 0.1:
        raise SystemExit("Median sampler collection exceeded the 100 ms budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
