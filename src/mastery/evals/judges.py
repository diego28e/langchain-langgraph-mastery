"""Evaluators and judges you can trust (Lesson 10.04).

- :func:`make_binary_judge`: one pass/fail judge per failure category, built on openevals'
  ``create_llm_as_judge`` (boolean score by default, ``few_shot_examples``, reasoning first).
- :class:`ScriptedJudgeModel`: an offline chat model that plugs into that same openevals
  code path, so lessons and CI run the real judge pipeline without a key.
- :func:`agreement`: TPR / TNR of a judge against YOUR labels, each with a Wilson interval.
- :func:`corrected_rate`: the Rogan-Gladen correction of a judge-measured failure rate,
  with a bootstrap interval that includes the uncertainty of TPR and TNR.
- :func:`reliability_table`, :func:`expected_calibration_error`: is "0.9 confident" right
  9 times in 10? :func:`choose_threshold` and :func:`decide` turn a score into
  fail / pass / human using the cost of each error and an abstain band.
- :func:`pairwise_with_swap`: pairwise comparison that runs both orders (position bias).

Convention: a judge answers "does this output show failure X?". ``True`` = failure found.
Positive class = failure, so TPR = share of real failures caught, TNR = share of real
passes left alone.

Example:
    >>> a = agreement([True, True, False, False], [True, False, False, False])
    >>> (a.tp, a.fp, a.tn, a.fn)
    (1, 1, 2, 0)
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda

from mastery.evals.stats import Interval, wilson_interval

__all__ = [
    "JUDGE_PROMPT",
    "JudgeAgreement",
    "ScriptedJudgeModel",
    "agreement",
    "choose_threshold",
    "corrected_rate",
    "decide",
    "expected_calibration_error",
    "make_binary_judge",
    "pairwise_with_swap",
    "reliability_table",
]

JUDGE_PROMPT = """You are checking ONE failure mode of a customer-support assistant.

Failure mode: {category}
Definition: {definition}
It is NOT this failure: {not_this}

Read the conversation and decide whether THIS failure happened. Ignore every other problem.
Think step by step first, then answer true (the failure happened) or false (it did not).

<conversation>
<input>{{inputs}}</input>
<output>{{outputs}}</output>
</conversation>"""


class ScriptedJudgeModel(BaseChatModel):
    """Offline judge model: ``decide(prompt_text) -> (score, reasoning)``.

    openevals calls ``with_structured_output(schema)``; this returns the scripted
    ``{"reasoning", "score"}`` dict, so ``create_llm_as_judge(judge=ScriptedJudgeModel(...))``
    runs unchanged. ``decide`` sees only the conversation part of the prompt (few-shot
    examples are cut off), like a model that reads the case in front of it.
    """

    decide: Callable[[str], tuple[Any, str]]
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted-judge"

    def _verdict(self, messages: Any) -> dict[str, Any]:
        text = "\n".join(str(m.get("content", "")) if isinstance(m, dict) else str(getattr(m, "content", m))
                         for m in (messages if isinstance(messages, list) else [messages]))
        case = text.split("<example>")[0]
        self.calls += 1
        score, reasoning = self.decide(case)
        return {"reasoning": reasoning, "score": score}

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        verdict = self._verdict(messages)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=str(verdict)))])

    def with_structured_output(self, schema: Any, **kwargs: Any) -> RunnableLambda:
        return RunnableLambda(self._verdict)


def make_binary_judge(category: str, definition: str, not_this: str, *, judge: Any,
                      few_shot_examples: Sequence[Mapping[str, Any]] = (), continuous: bool = False) -> Callable[..., dict]:
    """One judge for one failure category: ``judge_fn(inputs=..., outputs=...) -> {"key", "score", "comment"}``.

    ``judge`` is any LangChain chat model (``get_model("fast")``) or a :class:`ScriptedJudgeModel`.
    ``few_shot_examples``: ``{"inputs", "outputs", "score", "reasoning"}`` dicts from your DEV labels
    only (never from the examples you will measure the judge on).
    """
    from openevals.llm import create_llm_as_judge

    prompt = JUDGE_PROMPT.format(category=category, definition=definition, not_this=not_this)
    return create_llm_as_judge(prompt=prompt, judge=judge, feedback_key=f"fails_{category}",
                               few_shot_examples=list(few_shot_examples) or None, continuous=continuous)


@dataclass(frozen=True)
class JudgeAgreement:
    """How a judge's verdicts compare with your labels (True = failure)."""

    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def n(self) -> int:
        return self.tp + self.fp + self.tn + self.fn

    @property
    def tpr(self) -> Interval:
        """Share of real failures the judge catches (sensitivity / recall)."""
        return wilson_interval(self.tp, self.tp + self.fn)

    @property
    def tnr(self) -> Interval:
        """Share of real passes the judge leaves alone (specificity)."""
        return wilson_interval(self.tn, self.tn + self.fp)

    @property
    def accuracy(self) -> Interval:
        return wilson_interval(self.tp + self.tn, self.n)

    def __str__(self) -> str:
        return (f"TPR {self.tpr:.0%} · TNR {self.tnr:.0%} · accuracy {self.accuracy.estimate:.0%} "
                f"(tp={self.tp} fp={self.fp} tn={self.tn} fn={self.fn})")


def agreement(predictions: Sequence[bool], labels: Sequence[bool]) -> JudgeAgreement:
    """Compare judge verdicts with human labels, item by item (both: True = failure)."""
    if len(predictions) != len(labels):
        raise ValueError(f"{len(predictions)} predictions vs {len(labels)} labels")
    pairs = list(zip(map(bool, predictions), map(bool, labels)))
    return JudgeAgreement(tp=sum(p and t for p, t in pairs), fp=sum(p and not t for p, t in pairs),
                          tn=sum(not p and not t for p, t in pairs), fn=sum(not p and t for p, t in pairs))


def _rogan_gladen(observed: float, tpr: float, tnr: float) -> float:
    denominator = tpr + tnr - 1
    if denominator <= 0:
        return float("nan")
    return min(1.0, max(0.0, (observed + tnr - 1) / denominator))


def corrected_rate(flags: Sequence[bool], validation_predictions: Sequence[bool], validation_labels: Sequence[bool],
                   *, n_resamples: int = 2000, seed: int = 0, confidence: float = 0.95) -> Interval:
    """Failure rate measured by a judge, corrected for its errors (Rogan-Gladen).

    ``flags``: the judge's verdicts on the items you want the rate of (no labels needed).
    ``validation_*``: judge verdicts and your labels on a separate labelled set, from
    which TPR and TNR are estimated. The interval resamples both sets, so a judge checked
    on 20 labels gives a wide interval, as it should. Undefined (``nan``) when the judge is
    no better than chance (TPR + TNR <= 1).
    """
    flags = [bool(f) for f in flags]
    val = list(zip(map(bool, validation_predictions), map(bool, validation_labels)))
    if not flags or not val:
        raise ValueError("need judge flags and a labelled validation set")

    def estimate(fs: Sequence[bool], vs: Sequence[tuple[bool, bool]]) -> float:
        a = agreement([p for p, _ in vs], [t for _, t in vs])
        if a.tp + a.fn == 0 or a.tn + a.fp == 0:
            return float("nan")
        return _rogan_gladen(sum(fs) / len(fs), a.tpr.estimate, a.tnr.estimate)

    point = estimate(flags, val)
    rng = random.Random(seed)
    draws = sorted(x for x in (estimate([rng.choice(flags) for _ in flags], [rng.choice(val) for _ in val])
                               for _ in range(n_resamples)) if x == x)
    if not draws:
        return Interval(point, float("nan"), float("nan"), confidence, "rogan-gladen bootstrap", len(flags))
    lo = draws[int((1 - confidence) / 2 * (len(draws) - 1))]
    hi = draws[int((1 + confidence) / 2 * (len(draws) - 1))]
    return Interval(point, lo, hi, confidence, "rogan-gladen bootstrap", len(flags))


def reliability_table(confidences: Sequence[float], correct: Sequence[bool], *, bins: int = 5) -> list[dict[str, Any]]:
    """Bin predictions by stated confidence; compare with how often they were right."""
    rows = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        members = [(c, ok) for c, ok in zip(confidences, correct) if lo <= c < hi or (b == bins - 1 and c == 1.0)]
        if members:
            rows.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(members),
                         "confidence": sum(c for c, _ in members) / len(members),
                         "accuracy": wilson_interval(sum(ok for _, ok in members), len(members))})
    return rows


def expected_calibration_error(confidences: Sequence[float], correct: Sequence[bool], *, bins: int = 5) -> float:
    """Weighted mean |confidence - accuracy| over the bins of :func:`reliability_table` (0 = calibrated)."""
    rows = reliability_table(confidences, correct, bins=bins)
    total = sum(r["n"] for r in rows)
    return sum(r["n"] / total * abs(r["confidence"] - r["accuracy"].estimate) for r in rows) if total else 0.0


def decide(score: float, threshold: float, abstain: float = 0.0) -> str:
    """``"fail"`` above ``threshold + abstain``, ``"pass"`` below ``threshold - abstain``, else ``"human"``."""
    if score >= threshold + abstain:
        return "fail"
    if score < threshold - abstain:
        return "pass"
    return "human"


def choose_threshold(scores: Sequence[float], labels: Sequence[bool], *, cost_false_alarm: float = 1.0,
                     cost_miss: float = 5.0, cost_human: float | None = None, abstain: float = 0.0,
                     candidates: Sequence[float] | None = None) -> dict[str, Any]:
    """Pick the threshold with the lowest total cost on LABELLED data (``labels``: True = failure).

    A miss (failure scored as pass) usually costs more than a false alarm, so the best
    threshold is rarely 0.5. With ``cost_human`` and ``abstain`` > 0 the band around the
    threshold goes to a person at that cost.
    """
    candidates = list(candidates or [i / 20 for i in range(1, 20)])
    best = None
    for t in candidates:
        cost = 0.0
        outcomes = {"fail": 0, "pass": 0, "human": 0}
        for s, y in zip(scores, labels):
            verdict = decide(s, t, abstain)
            outcomes[verdict] += 1
            if verdict == "human":
                cost += cost_human or 0.0
            elif verdict == "fail" and not y:
                cost += cost_false_alarm
            elif verdict == "pass" and y:
                cost += cost_miss
        if best is None or cost < best["cost"]:
            best = {"threshold": t, "cost": cost, **outcomes}
    return best


def pairwise_with_swap(prefer: Callable[[str, str], str], first: str, second: str) -> str:
    """Ask ``prefer(a, b) -> "A" | "B"`` in both orders; return ``"first"``, ``"second"`` or ``"inconsistent"``.

    A judge that prefers whatever comes first (position bias) gives opposite answers when
    the order is swapped; counting those as "inconsistent" instead of a win keeps the bias
    out of your comparison. LangSmith's pairwise ``evaluate(..., randomize_order=True)``
    attacks the same bias by shuffling.
    """
    forward = prefer(first, second)
    backward = prefer(second, first)
    if forward == "A" and backward == "B":
        return "first"
    if forward == "B" and backward == "A":
        return "second"
    return "inconsistent"
