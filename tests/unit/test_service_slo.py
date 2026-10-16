from __future__ import annotations

import pytest

from mastery.service import (
    SLO,
    CostBudget,
    LatencyBudget,
    RunRecord,
    SpendLedger,
    burn_rate,
    default_slos,
    error_budget_policy,
    evaluate_slo,
    flaky,
    percentile,
    synthetic_runs,
    transient_only,
)


def run(i, status="ok", ttft=0.5, duration=5.0, t=0.0):
    return RunRecord(f"r{i}", "u1", t, status, ttft, duration)


def test_percentile_nearest_rank():
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10
    assert percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50) == 5
    with pytest.raises(ValueError):
        percentile([], 50)


def test_slo_budget_and_policy():
    runs = [run(i) for i in range(99)] + [run(99, status="error")]
    availability = default_slos()[0]
    result = evaluate_slo(availability, runs)
    assert (result.good, result.eligible, result.budget_used) == (99, 100, 1)
    assert result.budget_remaining == pytest.approx(0.0) and result.met
    big = [run(i) for i in range(399)] + [run(399, status="error")]       # budget 4, used 1
    assert error_budget_policy(evaluate_slo(availability, big)).startswith("normal")
    half = [run(i) for i in range(199)] + [run(199, status="error")]      # budget 2, used 1
    assert error_budget_policy(evaluate_slo(availability, half)).startswith("caution")
    worse = evaluate_slo(availability, runs + [run(100, status="error")])
    assert worse.budget_remaining < 0 and error_budget_policy(worse).startswith("freeze")


def test_rejected_runs_are_not_eligible_for_latency():
    slo = SLO("ttft", "x", 0.9, default_slos()[1].good)
    result = evaluate_slo(slo, [run(1), run(2, status="rejected", ttft=None)])
    assert result.eligible == 1


def test_burn_rate_and_synthetic_incident():
    calm = synthetic_runs(400, seed=1)
    stormy = synthetic_runs(400, seed=1, incident=True)
    ttft = default_slos()[1]
    since = 0.9 * 7 * 24 * 3600
    assert burn_rate(ttft, stormy, since=since) > 5 * max(burn_rate(ttft, calm, since=since), 0.1)
    assert all(r.cost_usd > 0 for r in calm if r.status != "rejected")


def test_latency_budget_check():
    budget = LatencyBudget({"queue": 0.5, "model_ttft": 2.0})
    rows = budget.check({"queue": 1.2, "model_ttft": 1.0})
    assert budget.total == 2.5 and [r["ok"] for r in rows] == [False, True]


def test_spend_ledger_caps_in_order():
    ledger = SpendLedger(CostBudget(per_request=0.01, per_user_day=0.02, global_day=0.03))
    assert not ledger.check("d", "a", 0.02).allowed                       # per-request cap
    ledger.charge("d", "a", 0.015)
    assert ledger.check("d", "a", 0.008).reason == "user's daily budget used up"
    ledger.charge("d", "b", 0.01)
    assert ledger.check("d", "c", 0.006).reason.startswith("global")      # kill switch beats user budget
    assert ledger.check("e", "a", 0.005).allowed                          # a new day
    assert ledger.top_users("d")[0] == ("a", 0.015)


def test_flaky_and_transient_only():
    from langchain_core.exceptions import ModelAuthenticationError, ModelRateLimitError

    respond = flaky("hi", fail_rate=0.5, seed=3)
    outcomes = []
    for _ in range(40):
        try:
            outcomes.append(respond([]))
        except ModelRateLimitError:
            outcomes.append("x")
    assert 10 < outcomes.count("x") < 30 and "hi" in outcomes
    assert transient_only(ModelRateLimitError("x")) and not transient_only(ModelAuthenticationError("x"))
