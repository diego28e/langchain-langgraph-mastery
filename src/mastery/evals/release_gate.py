"""The support desk's release gate, as a library and as a CI command (Lesson 10.08, Project 10).

    python -m mastery.evals.release_gate                       # gate the shipped desk (exit 0 = ship)
    python -m mastery.evals.release_gate --candidate no-auth-context   # a broken refactor: exit 1
    python -m mastery.evals.release_gate --write-baseline      # after an approved release

The committed baseline (``data/samples/support-desk/release-baseline.json``) holds the
thresholds and the red-team results of the last approved release. Gates:

1. **pass rate**: lower bound of the 95% interval over repeated runs >= ``min_lower_bound``;
2. **pass^k**: share of cases that pass in EVERY run >= ``min_pass_hat_k``;
3. **red team**: no attack the baseline blocked gets through (missing ids count as failures);
4. **cost**: model calls per case <= ``max_calls_per_case``.

The Markdown report goes to stdout, to ``--report`` and, inside GitHub Actions, to the job summary.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from mastery.evals.gates import GateReport, GateResult, cost_gate, redteam_gate, summary_gate
from mastery.evals.stats import summarize_repeats

__all__ = ["CANDIDATES", "baseline_path", "evaluate_release", "load_baseline", "main", "write_baseline"]


def baseline_path() -> Path:
    from mastery.config import package_repo_root

    return package_repo_root() / "data" / "samples" / "support-desk" / "release-baseline.json"


def _candidates() -> dict[str, Any]:
    from mastery.agents.release_suite import BASELINE, NO_AUTH_CONTEXT

    return {c.name: c for c in (BASELINE, NO_AUTH_CONTEXT)}


CANDIDATES = ("baseline", "no-auth-context")


def load_baseline(path: str | Path | None = None) -> dict[str, Any]:
    return json.loads(Path(path or baseline_path()).read_text(encoding="utf-8"))


def evaluate_release(candidate: Any, baseline: dict[str, Any], *, cases: list[dict] | None = None,
                     model_for: Any = None) -> tuple[GateReport, dict[str, Any]]:
    """Run the release suite on ``candidate`` and apply the baseline's gates."""
    from mastery.agents.release_suite import REDTEAM, release_cases, run_suite

    cases = cases if cases is not None else release_cases(baseline["n"])
    result = run_suite(candidate, cases, repetitions=baseline["repetitions"], redteam=REDTEAM, model_for=model_for)
    summary = summarize_repeats([{i: float(r["passed"]) for i, r in run.items()} for run in result["runs"]])
    result["summary"] = summary
    report = GateReport([
        summary_gate("pass rate", summary, min_lower_bound=baseline["min_lower_bound"]),
        GateResult(f"pass^{summary.k}", summary.pass_hat_k >= baseline["min_pass_hat_k"],
                   f"{summary.pass_hat_k:.1%} of cases pass every run vs minimum {baseline['min_pass_hat_k']:.0%}"),
        redteam_gate("red team", result["redteam"], baseline["redteam"]),
        cost_gate("model calls", result["calls_per_case"], baseline["max_calls_per_case"], unit=" calls/case"),
    ])
    return report, result


def write_baseline(result: dict[str, Any], path: str | Path | None = None, *, n: int, repetitions: int,
                   margin: float = 0.05, cost_headroom: float = 1.25) -> dict[str, Any]:
    """Baseline from an APPROVED run: thresholds a little below today's numbers (noise margin)."""
    summary = result["summary"]
    data = {"n": n, "repetitions": repetitions, "candidate": result["candidate"],
            "min_lower_bound": round(max(0.0, summary.mean.low - margin), 2),
            "min_pass_hat_k": round(max(0.0, summary.pass_hat_k - margin), 2),
            "max_calls_per_case": round(result["calls_per_case"] * cost_headroom, 2),
            "redteam": dict(sorted(result["redteam"].items()))}
    Path(path or baseline_path()).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m mastery.evals.release_gate", description=__doc__.split("\n\n")[0])
    parser.add_argument("--candidate", default="baseline", choices=CANDIDATES)
    parser.add_argument("--baseline", default=None, help="baseline JSON (default: the committed one)")
    parser.add_argument("--report", default=None, help="also write the Markdown report here")
    parser.add_argument("--write-baseline", action="store_true", help="record this run as the new baseline")
    args = parser.parse_args(argv)

    candidate = _candidates()[args.candidate]
    if args.write_baseline:
        from mastery.agents.release_suite import REDTEAM, release_cases, run_suite

        n, k = 120, 3
        result = run_suite(candidate, release_cases(n), repetitions=k, redteam=REDTEAM)
        result["summary"] = summarize_repeats([{i: float(r["passed"]) for i, r in run.items()} for run in result["runs"]])
        print(json.dumps(write_baseline(result, args.baseline, n=n, repetitions=k), indent=2))
        return 0

    report, result = evaluate_release(candidate, load_baseline(args.baseline))
    text = (f"## Release gate: `{args.candidate}`\n\n{len(result['runs'][0])} cases x {len(result['runs'])} runs, "
            f"{len(result['redteam'])} attacks\n\n{report.to_markdown()}\n")
    print(text)
    for target in (args.report, os.environ.get("GITHUB_STEP_SUMMARY")):
        if target:
            with open(target, "a", encoding="utf-8") as fh:
                fh.write(text)
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())
