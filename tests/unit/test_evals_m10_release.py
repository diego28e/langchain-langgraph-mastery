"""Module 10 part 2: monitoring, prompt registry, the release suite and the release gate (offline)."""

from __future__ import annotations

import json
from functools import partial

import pytest

from mastery.agents.release_suite import (BASELINE, NO_AUTH_CONTEXT, REDTEAM, Candidate, release_cases, reword,
                                          run_suite, side_effects_only, tool_call)
from mastery.agents.support import TRIAGE_PROMPT, build_handoffs_desk
from mastery.evals import PromotionBlocked, PromptRegistry, ReviewQueue, feedback_payload, judge_budget, rate_alert
from mastery.evals import sample_size, should_sample
from mastery.evals.release_gate import baseline_path, evaluate_release, load_baseline, main


def test_sampling_and_budget():
    assert sample_size(0.05, p=0.3) == 323
    assert sample_size(0.03, p=0.5) == 1068
    with pytest.raises(ValueError):
        sample_size(0)
    picks = [should_sample(f"t{i}", 0.2) for i in range(2000)]
    assert picks == [should_sample(f"t{i}", 0.2) for i in range(2000)]
    assert 0.15 < sum(picks) / len(picks) < 0.25
    assert judge_budget(10_000, 0.05, judges=2)["calls"] == 1000


def test_feedback_alert_and_queue():
    payload = feedback_payload("r1", "user_thumbs", False, source="user")
    assert payload["score"] == 0.0 and payload["source_info"]["source"] == "user"
    fired, interval = rate_alert([True] * 30 + [False] * 70, 0.10)
    assert fired and interval.low > 0.10
    assert not rate_alert([True] * 12 + [False] * 88, 0.10)[0]
    queue = ReviewQueue("q")
    queue.add({"id": "a", "input": "hi", "want": ["faq"]}, "random")
    queue.add({"id": "a", "input": "hi", "want": ["faq"]}, "thumbs_down")
    assert len(queue.items) == 1 and queue.items["a"]["reason"] == "random"
    assert queue.to_examples() == []
    queue.label("a", "generic_fallback")
    assert queue.to_examples()[0]["category"] == "generic_fallback"
    with pytest.raises(KeyError):
        queue.label("zz", "pass")


def test_prompt_registry_promotion(tmp_path):
    reg = PromptRegistry()
    c1 = reg.push("p", "one")
    c2 = reg.push("p", "two")
    assert reg.push("p", "one") == c1 and len(reg.history("p")) == 2
    reg.tag("p", c1, "prod")
    assert reg.pull("p", "prod") == "one" and reg.pull("p") == "two" and reg.pull("p", c2) == "two"
    with pytest.raises(PromotionBlocked):
        reg.promote("p", c2, "prod", False)
    assert reg.resolve("p", "prod") == c1
    reg.promote("p", c2, "prod", True)
    again = PromptRegistry.load(reg.save(tmp_path / "r.json"))
    assert again.resolve("p", "prod") == c2
    with pytest.raises(KeyError):
        reg.pull("p", "nope")


def test_reword_is_deterministic_and_identity_at_zero():
    text = "I'm C-1003, please refund INV-3001 ($19)."
    assert reword(text, 0) == text
    assert reword(text, 2) == reword(text, 2)
    assert {reword(text, s) for s in range(1, 8)} != {text}


def test_redteam_blocked_only_with_identity():
    base = run_suite(BASELINE, [], redteam=REDTEAM)["redteam"]
    broken = run_suite(NO_AUTH_CONTEXT, [], redteam=REDTEAM)["redteam"]
    assert all(base.values())
    assert {k for k, v in broken.items() if not v} == {"RT01", "RT02", "RT03", "RT07"}


def test_release_cases_frozen_and_scored():
    cases = release_cases(120)
    assert len(cases) == 105 and cases[0]["id"].startswith("R")
    assert all(c["kind"] != "adversarial" for c in cases)
    result = run_suite(BASELINE, cases[:20], repetitions=2)
    assert len(result["runs"]) == 2 and set(result["runs"][0]) == {c["id"] for c in cases[:20]}
    assert result["calls_per_case"] > 0


def test_side_effects_only_filters_transfers():
    msgs = [{"role": "user", "content": "x"},
            {"role": "assistant", "content": "", "tool_calls": [tool_call("transfer_to_billing")]},
            {"role": "assistant", "content": "", "tool_calls": [tool_call("issue_refund", invoice_id="INV-3001")]},
            {"role": "assistant", "content": "done"}]
    kept = side_effects_only(msgs)
    assert [m["role"] for m in kept] == ["user", "assistant", "assistant"]
    assert kept[1]["tool_calls"][0]["function"]["name"] == "issue_refund"


def test_committed_baseline_is_well_formed():
    data = json.loads(baseline_path().read_text(encoding="utf-8"))
    assert data["candidate"] == "baseline" and data["repetitions"] >= 3
    assert set(data["redteam"]) == {a["id"] for a in REDTEAM} and all(data["redteam"].values())
    assert 0 < data["min_lower_bound"] < 1 and data["max_calls_per_case"] > 0


def test_gate_blocks_broken_candidates():
    baseline = load_baseline()
    small = {**baseline, "repetitions": 1}
    cases = release_cases(40)
    ok, _ = evaluate_release(BASELINE, {**small, "min_lower_bound": 0.0, "min_pass_hat_k": 0.0}, cases=cases)
    assert ok.passed
    broken, _ = evaluate_release(NO_AUTH_CONTEXT, {**small, "min_lower_bound": 0.0, "min_pass_hat_k": 0.0}, cases=cases)
    assert not broken.passed and [r.name for r in broken if not r.passed] == ["red team"]
    friendly = Candidate("friendly", build=partial(build_handoffs_desk, triage_prompt="You are a friendly front desk."))
    bad, _ = evaluate_release(friendly, small, cases=cases)
    assert {r.name for r in bad if not r.passed} >= {"pass rate"}
    assert TRIAGE_PROMPT  # the default prompt is unchanged


def test_cli_exit_codes(tmp_path, capsys):
    report = tmp_path / "gate.md"
    assert main(["--report", str(report)]) == 0
    assert "all gates passed" in report.read_text(encoding="utf-8")
    assert main(["--candidate", "no-auth-context"]) == 1
    assert "blocked by: red team" in capsys.readouterr().out
