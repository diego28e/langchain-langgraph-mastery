"""mastery.finetune: dataset splits, numpy baselines, metrics, routing cost and the batched LLM router (offline)."""
import json

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from mastery.finetune import (QUEUES, LogReg, NaiveBayes, accuracy, assign_splits, best_threshold, by_split, calibration,
                              confusion, correct_map, expected_calibration_error, family_overlap, fewshot_prompt,
                              load_predictions, load_tickets, macro_f1, pick_examples, route_curve, route_with_llm,
                              save_predictions, to_chat_example, top_confusions, write_chat_jsonl)
from mastery.finetune.llm_router import Routed, RoutedBatch


@pytest.fixture(scope="module")
def split():
    return by_split(load_tickets())


def test_dataset_shape_and_no_family_leaks(split):
    assert {k: len(v) for k, v in split.items()} == {"train": 594, "dev": 72, "test": 234}
    assert not family_overlap(split["train"], split["test"]) and not family_overlap(split["train"], split["dev"])
    for part in split.values():
        assert {t["queue"] for t in part} == set(QUEUES)
    assert any(t["lang"] == "es" for t in split["test"]) and any(t["hard"] for t in split["test"])


def test_assign_splits_is_stable_and_by_family():
    rows = [{"id": f"{f}-{i}", "family": f"f{f}", "queue": "bug"} for f in range(10) for i in range(3)]
    a, b = assign_splits(rows), assign_splits(list(reversed(rows)))
    where = {r["id"]: r["split"] for r in a}
    assert all(where[r["id"]] == r["split"] for r in b)
    fam = {}
    for r in a:
        fam.setdefault(r["family"], set()).add(r["split"])
    assert all(len(s) == 1 for s in fam.values())
    assert sum(1 for s in fam.values() if s == {"test"}) == 2


@pytest.mark.parametrize("cls", [NaiveBayes, LogReg])
def test_baselines_learn_and_give_probabilities(cls, split):
    model = cls().fit([t["text"] for t in split["train"]], [t["queue"] for t in split["train"]])
    preds = model.predict([t["text"] for t in split["test"]])
    acc = sum(p == t["queue"] for (p, _), t in zip(preds, split["test"])) / len(preds)
    assert acc > 0.45                                             # well above chance (1/6)
    assert all(0 < c <= 1 for _, c in preds)
    assert model.predict_proba(["refund"]).sum() == pytest.approx(1, abs=1e-5)


def test_metrics():
    gold = {"a": "bug", "b": "bug", "c": "billing", "d": "outage"}
    pred = {"a": "bug", "b": "billing", "c": "billing"}
    assert correct_map(pred, gold) == {"a": 1, "b": 0, "c": 1, "d": 0}
    assert accuracy(pred, gold).estimate == 0.5
    assert macro_f1(pred, gold, ["bug", "billing", "outage"]) == pytest.approx((2 / 3 + 2 / 3 + 0) / 3)
    assert confusion(pred, gold, ["bug", "billing", "outage"])["outage"]["other"] == 1
    assert top_confusions(pred, gold)[0] in {("bug", "billing", 1), ("outage", "missing", 1)}
    assert expected_calibration_error([1.0, 1.0], [1, 1]) == 0
    assert calibration([0.1, 0.9], [0, 1], bins=2) == [{"bin": "0.0–0.5", "n": 1, "confidence": 0.1, "accuracy": 0.0},
                                                       {"bin": "0.5–1.0", "n": 1, "confidence": 0.9, "accuracy": 1.0}]


def test_route_curve_and_best_threshold():
    conf, local, big = [0.9, 0.8, 0.3, 0.2], [1, 1, 0, 0], [1, 1, 1, 1]
    pts = route_curve(conf, local, big, cost_wrong=1.0, cost_escalate=0.1, thresholds=[0.0, 0.5, 1.01])
    assert [(p.kept, p.accuracy) for p in pts] == [(4, 0.5), (2, 1.0), (0, 1.0)]
    assert best_threshold(pts).threshold == 0.5


def test_chat_export_and_predictions_round_trip(tmp_path, split):
    ex = to_chat_example(split["train"][0])
    assert [m["role"] for m in ex["messages"]] == ["system", "user", "assistant"]
    path = write_chat_jsonl(split["train"][:3], tmp_path / "train.jsonl")
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3
    p = save_predictions(tmp_path / "p.json", "fake", {"b": "bug", "a": "billing"}, recorded="2026-10-16", split="test")
    assert load_predictions(p)["labels"] == {"a": "billing", "b": "bug"} and json.loads(p.read_text())["split"] == "test"


def test_fewshot_prompt_has_queues_and_examples(split):
    ex = pick_examples(split["train"], per_queue=1)
    assert len(ex) == 6 and {e["queue"] for e in ex} == set(QUEUES)
    prompt = fewshot_prompt(ex)
    assert all(q in prompt for q in QUEUES) and ex[0]["text"] in prompt


def test_route_with_llm_batches_and_survives_a_bad_batch():
    tickets = [{"id": f"K{i}", "text": f"ticket {i}"} for i in range(5)]
    calls = []

    class Fake:
        def invoke(self, messages):
            calls.append(messages)
            if len(calls) in (2, 3):                     # second batch fails twice → marked "error"
                raise ValueError("bad json")
            ids = [line.split(":")[0] for line in messages[1][1].splitlines()]
            return RoutedBatch(labels=[Routed(id=i, queue="bug") for i in ids])

    run = route_with_llm(GenericFakeChatModel(messages=iter([])), tickets, batch_size=2,
                         structured=lambda model, schema: Fake())
    assert run.labels == {"K0": "bug", "K1": "bug", "K2": "error", "K3": "error", "K4": "bug"}
    assert run.failed_batches == 1 and len(calls) == 4


def test_colab_notebook_trains_with_the_library_prompt():
    from pathlib import Path

    import nbformat

    from mastery.finetune import SYSTEM_PROMPT
    nb = Path(__file__).resolve().parents[2] / "modules" / "14-local-models-and-fine-tuning" / "colab" / "colab-qlora-router.ipynb"
    source = "\n".join(c.source for c in nbformat.read(nb, as_version=4).cells if c.cell_type == "code")
    assert f"SYSTEM_PROMPT = {SYSTEM_PROMPT!r}" in source
    assert "LIVE = IN_COLAB and HAVE_GPU" in source
