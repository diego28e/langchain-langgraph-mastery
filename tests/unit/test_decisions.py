"""mastery.decisions: modes, replay/record transports, answer rows, cost, doctor. All offline."""
import json
import warnings

import httpx2
import pytest

warnings.filterwarnings("ignore", message=".*TypeSafeClassifier.*beta")

from mastery.decisions import (ReplayMiss, ReplayStore, answer_rows, decision_classifier, decision_cost,  # noqa: E402
                               decisions_mode, provenance, request_key, with_rate_limit_retry)
from mastery.decisions.orbita import TICKETS, ticket_state, triage_questions, urgent_question  # noqa: E402
from mastery.doctor import check_decisions_env  # noqa: E402
from mastery.pricing import get_price  # noqa: E402


def test_mode_resolution(isolated_env):
    assert decisions_mode() == "replay"
    isolated_env.setenv("TYPESAFE_API_KEY", "ts_test")
    assert decisions_mode() == "live"
    assert decisions_mode("replay") == "replay"
    isolated_env.delenv("TYPESAFE_API_KEY")
    with pytest.raises(ValueError, match="needs TYPESAFE_API_KEY"):
        decisions_mode("live")
    with pytest.raises(ValueError, match="must be one of"):
        decisions_mode("cloud")


def test_request_key_ignores_model_and_order():
    a = {"model": "jev-1.13.0", "state": "x", "questions": {"q": {"type": "noul", "instructions": "?"}}}
    b = {"questions": {"q": {"instructions": "?", "type": "noul"}}, "state": "x", "model": "jev-latest"}
    assert request_key(a) == request_key(b)
    assert request_key(a) != request_key(dict(a, state="y"))


def test_shipped_recordings_replay_every_lesson_request(isolated_env):
    setup = decision_classifier()
    assert setup.mode == "replay" and len(setup.store) >= 7
    r = setup.classifier.invoke({"state": ticket_state(TICKETS[0]), "questions": urgent_question()})
    assert r.nouls["urgent"].noul > 0.9 and provenance(r) == "replay (synthetic)"
    results = setup.classifier.batch([{"state": ticket_state(t), "questions": triage_questions()} for t in TICKETS])
    for res in results:
        team = res.choices["team"]
        assert team.choice == max(team.probabilities, key=team.probabilities.get)
        assert abs(sum(team.probabilities.values()) - 1) < 1e-6
        assert 0 <= res.scores["urgency"].score <= 2 and set(res.nouls) == {"is_bug", "churn_risk"}
    assert [r.choices["team"].choice for r in results[:4]] == ["technical", "billing", "account_access", "feature_request"]


def test_replay_miss_is_a_clear_error(isolated_env):
    setup = decision_classifier()
    with pytest.raises(ReplayMiss, match="TYPESAFE_API_KEY"):
        setup.classifier.invoke({"state": "something new", "questions": urgent_question()})


def test_record_then_replay_roundtrip(tmp_path, isolated_env):
    from langchain_typesafe import TypeSafeClassifier
    from mastery.decisions import RecordingTransport

    def upstream(request):
        return httpx2.Response(200, json={"model": "jev-1.13.0", "request_id": "live-1",
                                          "answers": {"urgent": {"type": "noul", "noul": 0.25}},
                                          "usage": {"input_tokens": 50, "output_tokens": 4}})
    store = ReplayStore(tmp_path / "rec.json")
    live = TypeSafeClassifier(api_key="k", client=httpx2.Client(transport=RecordingTransport(httpx2.MockTransport(upstream), store)))
    live.invoke({"state": "hello", "questions": urgent_question()})
    store.save()
    saved = json.loads((tmp_path / "rec.json").read_text())
    (rec,) = saved["records"].values()
    assert rec["synthetic"] is False and "request_id" not in rec["response"]
    replay = decision_classifier(recordings=tmp_path / "rec.json").classifier
    r = replay.invoke({"state": "hello", "questions": urgent_question()})
    assert r.nouls["urgent"].noul == 0.25 and provenance(r) == "replay (recorded)"


def test_answer_rows_and_cost(isolated_env):
    r = decision_classifier().classifier.invoke({"state": ticket_state(TICKETS[4]), "questions": triage_questions()})
    rows = {row["question"]: row for row in answer_rows(r)}
    assert rows["team"]["type"] == "choice" and rows["urgency"]["type"] == "score"
    assert rows["is_bug"]["answer"] in ("yes", "no")
    cost = decision_cost(r)
    assert cost == pytest.approx(r.usage.input_tokens * 0.042 / 1e6)
    assert get_price("jev-1.13.0").output_per_m == 0.0


def test_rate_limit_retry_retries_only_429(isolated_env):
    from langchain_typesafe import TypeSafeClassifier
    from langchain_typesafe.client import TypeSafeAuthenticationError

    calls = {"n": 0}

    def flaky(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx2.Response(429, headers={"retry-after": "0"}, json={"error": "slow down"})
        return httpx2.Response(200, json={"model": "jev-1.13.0", "answers": {"urgent": {"type": "noul", "noul": 0.6}},
                                          "usage": {"input_tokens": 5}})
    clf = TypeSafeClassifier(api_key="k", client=httpx2.Client(transport=httpx2.MockTransport(flaky)))
    r = with_rate_limit_retry(clf).invoke({"state": "x", "questions": urgent_question()})
    assert r.nouls["urgent"].noul == 0.6 and calls["n"] == 2

    deny = TypeSafeClassifier(api_key="k", client=httpx2.Client(transport=httpx2.MockTransport(
        lambda req: httpx2.Response(401, json={"error": "bad key"}))))
    with pytest.raises(TypeSafeAuthenticationError):
        with_rate_limit_retry(deny).invoke({"state": "x", "questions": urgent_question()})


def test_check_decisions_env():
    assert check_decisions_env({}) == []
    assert "needs TYPESAFE_API_KEY" in check_decisions_env({"MASTERY_DECISIONS_MODE": "live"})[0]
    assert any("API root" in n for n in check_decisions_env({"TYPESAFE_BASE_URL": "https://openrouter.ai/api/v1"}))
    assert any("OpenRouter" in n for n in check_decisions_env({"TYPESAFE_API_KEY": "sk-or-v1-abc"}))
    assert check_decisions_env({"TYPESAFE_API_KEY": "sk-or-v1-abc", "TYPESAFE_BASE_URL": "https://openrouter.ai/api"}) == []


def test_async_replay_never_touches_the_network(isolated_env, monkeypatch):
    import asyncio

    def boom(*a, **k):
        raise AssertionError("network used in replay mode")
    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", boom)
    jev = decision_classifier().classifier
    out = asyncio.run(jev.abatch([{"state": ticket_state(t), "questions": triage_questions()} for t in TICKETS]))
    assert [provenance(r) for r in out] == ["replay (synthetic)"] * 6
    with pytest.raises(ReplayMiss):
        asyncio.run(jev.ainvoke({"state": "new text", "questions": urgent_question()}))


def test_lab_and_lesson_recordings_cover_every_request(isolated_env):
    from mastery.decisions.orbita import (chat_questions, chat_transcript, lab_tickets, queue_questions, single_questions)
    store = decision_classifier().store
    reqs = [{"state": t["text"], "questions": queue_questions()} for t in lab_tickets()]
    reqs += [{"state": ticket_state(TICKETS[0]), "questions": q} for q in single_questions()]
    reqs += [{"state": chat_transcript(), "questions": chat_questions()}]
    jev = decision_classifier().classifier
    assert len(jev.batch(reqs)) == len(reqs) and len(store) >= 246


def test_policy_band_and_scores():
    from mastery.decisions import BandCosts, apply_band, band_cost, brier_score, choose_band
    assert apply_band(0.9, 0.3, 0.7) == "yes" and apply_band(0.5, 0.3, 0.7) == "review" and apply_band(0.1, 0.3, 0.7) == "no"
    assert brier_score([1.0, 0.0], [1, 0]) == 0 and brier_score([0.5, 0.5], [1, 0]) == 0.25
    p, y = [0.95, 0.9, 0.55, 0.5, 0.1, 0.05], [1, 1, 1, 0, 0, 0]
    costs = BandCosts(false_yes=20, false_no=200, review=1)
    best = choose_band(p, y, costs)
    assert best.errors == 0 and best.cost <= band_cost(p, y, 0.5, 0.5, costs).cost


def test_llm_decider_keeps_the_response_shape():
    from langchain_core.messages import AIMessage
    from mastery.decisions import llm_decider
    from mastery.testing import ScriptedChatModel
    model = ScriptedChatModel(responses=[AIMessage("", tool_calls=[{"name": "DecisionAnswers", "id": "c1", "args": {
        "team": "billing", "urgency": 2, "is_bug": 0.2, "churn_risk": 0.7}}])])
    r = llm_decider(model, name="scripted").invoke({"state": ticket_state(TICKETS[1]), "questions": triage_questions()})
    assert provenance(r) == "llm fallback" and r.model == "llm:scripted"
    assert r.choices["team"].choice == "billing" and r.choices["team"].confidence == 0.0
    assert r.scores["urgency"].score == 2.0 and r.nouls["churn_risk"].noul == 0.7


def test_tool_gate_bands_and_fail_closed(isolated_env):
    from langchain_core.runnables import RunnableLambda
    from langchain_typesafe.experimental.middleware import AutoModeMiddleware

    from mastery.decisions.middleware import JevToolGate, with_classifier
    from mastery.decisions.ops import GUARDED, run_scenario

    jev = decision_classifier().classifier
    out = run_scenario("injection", [with_classifier(AutoModeMiddleware, jev, tools=GUARDED)])
    assert "station-backups" in out["buckets_left"] and not out["emails_sent"]

    for approve, restarted in ((True, ["ingest-worker"]), (False, [])):
        gate = JevToolGate(jev, tools=GUARDED, review_at=0.3, block_at=0.8)
        out = run_scenario("restart", [gate], approve=approve, thread=f"t-{approve}")
        assert out["restarted"] == restarted and len(gate.log) == 1
        assert gate.log[0]["action"] == "review → " + ("approved" if approve else "rejected")

    def down(_):
        raise RuntimeError("down")

    gate = JevToolGate(RunnableLambda(down), tools=GUARDED)
    out = run_scenario("restart", [gate], thread="t-down")
    assert out["restarted"] == [] and gate.log[0]["action"].startswith("blocked")


def test_router_and_batch_graph(isolated_env):
    from mastery.decisions.graph import build_batch_graph
    from mastery.decisions.ops import ROUTER_PROMPTS, run_router

    jev = decision_classifier().classifier
    assert run_router(ROUTER_PROMPTS["simple"], jev)["route"].choice == "small"
    assert run_router(ROUTER_PROMPTS["complex"], jev)["route"].choice == "large"
    rows = build_batch_graph(lambda t: {"id": t["id"], "queue": "x"}).invoke({"tickets": [{"id": i} for i in range(5)]})
    assert sorted(r["id"] for r in rows["results"]) == list(range(5))


def test_jev_evaluators_shape_and_shared_request(isolated_env):
    from mastery.decisions.evaluator import REPLY_CASES, bot_under_test, examples, jev_evaluators
    from mastery.evals.datasets import run_experiment

    assert len(REPLY_CASES) == 48 and len(examples("dev")) == len(examples("test")) == 24
    calls = []
    jev = decision_classifier().classifier
    counting = __import__("langchain_core.runnables", fromlist=["RunnableLambda"]).RunnableLambda(
        lambda x: calls.append(1) or jev.invoke(x))
    exp = run_experiment(bot_under_test, examples("dev"), jev_evaluators(counting))
    assert len(calls) == 24                       # two feedback keys, one request per reply
    row = exp.runs[0]["R1-off_topic"]["scores"]
    assert set(row) == {"fails", "invents_policy"} and row["fails"] > 0.9


def test_benchmark_percentiles_and_cost():
    from mastery.decisions.bench import benchmark, llm_cost_per_1k, monthly_cost, percentile

    assert percentile([10, 12, 11, 13, 250], 50) == 12 and percentile([10, 12, 11, 13, 250], 95) == 250
    ticks = iter(range(100))
    res = benchmark("x", lambda v: v, [1, 2, 3], warmup=0, cost_of=lambda _: 0.001, clock=lambda: next(ticks))
    assert res.n == 3 and res.p50_ms == 1000 and abs(res.usd_per_1k - 1.0) < 1e-9
    assert monthly_cost(1.0, 1000) == 30
    assert llm_cost_per_1k("groq:openai/gpt-oss-20b", 1000, 0) == pytest.approx(0.075)
    assert llm_cost_per_1k("nope:model", 1, 1) is None


def test_safety_cases_and_gate_band(isolated_env):
    from mastery.decisions.middleware import JevToolGate
    from mastery.decisions.policy import BandCosts, band_cost, choose_band
    from mastery.decisions.safety import CASES, case_state, cases

    assert len(CASES) == 32 and len(cases("dev")) == len(cases("test")) == 16
    s = case_state(next(c for c in CASES if c["tool_output"]))
    assert s["messages"][-1]["role"] == "tool" and set(s) == {"messages", "tool_call", "tool_description"}
    jev, q = decision_classifier().classifier, JevToolGate(None, tools=[])._questions()
    p = {c["id"]: jev.invoke({"state": case_state(c), "questions": q}).nouls["risky"].noul for c in CASES}
    costs = BandCosts(false_yes=5, false_no=100, review=1)
    band = choose_band([p[c["id"]] for c in cases("dev")], [c["unsafe"] for c in cases("dev")], costs)
    assert band.low < band.high
    test = band_cost([p[c["id"]] for c in cases("test")], [c["unsafe"] for c in cases("test")], band.low, band.high, costs)
    assert test.errors == 0
