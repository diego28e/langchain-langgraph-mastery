"""Lesson 15.06: Jev as a LangSmith evaluator (a typed grader for support replies).

``REPLY_CASES`` are 48 Orbita Cloud tickets with a reply from the "support bot under test" and a human
label (``fails``: True = the reply does not resolve the ticket). 8 tickets x 6 reply kinds, SYNTHETIC.
:func:`jev_evaluators` returns LangSmith/openevals-shaped evaluators
(``evaluator(inputs=..., outputs=..., reference_outputs=...) -> {"key", "score"}``) that run with
``langsmith.evaluate`` and with the offline twin ``mastery.evals.datasets.run_experiment``.
"""
from __future__ import annotations

import json
from typing import Any, Callable

POLICY = ("Orbita Cloud support policy: refunds within 14 days of a charge; password resets via Settings > Security; "
          "the status page is status.orbita.example; exports are limited to 1M rows; SSO is on the Enterprise plan only.")

_TOPICS = [
    ("I was charged twice for October. Can I get one refunded?",
     "I'm sorry about the double charge. I've confirmed the duplicate October charge and refunded it; it shows on your card within 5 business days.",
     "Refunded the duplicate October charge.",
     "Billing issues can happen for many reasons. Please check your account.",
     "I've refunded both October charges and added 3 free months as our standard apology.",
     "Our API supports webhooks for every event type."),
    ("I can't log in after resetting my password, it says 'invalid token'.",
     "The reset link expires after 15 minutes. Go to Settings > Security, request a new reset, and use the newest link; that clears 'invalid token'.",
     "Request a fresh reset in Settings > Security and use the newest link.",
     "Login problems are usually temporary. Try again later.",
     "Invalid token means your account was locked for fraud; we deleted it, please sign up again.",
     "Our Enterprise plan includes SSO."),
    ("Is the API down? Every call returns 503 since 10:05.",
     "Yes: we have an incident since 10:02 affecting the API in us-east. Follow status.orbita.example for updates; we'll post the fix there.",
     "Incident since 10:02, see status.orbita.example.",
     "Errors can have many causes. Check your code.",
     "There's no incident; 503 means your plan ran out of API credits.",
     "You can export data as CSV from the dashboard."),
    ("Export to CSV fails for my 3M-row table.",
     "Exports are limited to 1M rows. Filter by date to split the table into three exports, or use the bulk API for the full table.",
     "The limit is 1M rows: split by date or use the bulk API.",
     "Exports should work. Try a different browser.",
     "Exports have no row limit; this is a bug we fixed yesterday, so retry now.",
     "Refunds are available within 14 days of a charge."),
    ("Can we enable SSO on our Business plan?",
     "SSO is available on the Enterprise plan only. I can connect you with sales to upgrade, and SSO can be on the same day.",
     "SSO needs Enterprise; I can connect you with sales.",
     "We support many authentication methods.",
     "Sure, I've enabled SSO on your Business plan at no charge.",
     "The status page is status.orbita.example."),
    ("Your dashboard shows temperatures in Fahrenheit; we need Celsius.",
     "Open Settings > Units and choose Celsius; every chart and export switches immediately.",
     "Settings > Units > Celsius.",
     "We take feedback about units seriously.",
     "Celsius isn't supported, but we'll add it next week for you.",
     "Password resets are in Settings > Security."),
    ("I was charged after cancelling 20 days ago. Refund please.",
     "Our refund window is 14 days from the charge, and this charge is 6 days old, so it qualifies; I've refunded it.",
     "It's within the 14-day window: refunded.",
     "Thanks for reaching out about your billing.",
     "Charges after cancellation are never refundable.",
     "SSO is on the Enterprise plan."),
    ("Webhooks stopped arriving after we rotated our signing secret.",
     "After a secret rotation, update the secret in your verifier and click 'Resend failed' in Settings > Webhooks; deliveries resume within minutes.",
     "Update your verifier's secret, then 'Resend failed' in Settings > Webhooks.",
     "Webhooks are a powerful feature.",
     "Rotating the secret permanently disables webhooks on your account.",
     "Exports are limited to 1M rows."),
]
KINDS = ("resolves", "brief", "vague", "invents", "off_topic", "deflects")
FAILS = {"resolves": False, "brief": False, "vague": True, "invents": True, "off_topic": True, "deflects": True}
_DEFLECT = "Please contact support for help with this."


def _cases() -> list[dict[str, Any]]:
    out = []
    for i, (ticket, good, brief, vague, invents, off) in enumerate(_TOPICS, 1):
        replies = {"resolves": good, "brief": brief, "vague": vague, "invents": invents, "off_topic": off, "deflects": _DEFLECT}
        for kind in KINDS:
            out.append({"id": f"R{i}-{kind}", "ticket": ticket, "reply": replies[kind], "kind": kind, "fails": FAILS[kind],
                        "split": "dev" if i <= 4 else "test"})
    return out


REPLY_CASES = _cases()


def reply_state(ticket: str, reply: str) -> dict[str, str]:
    """What Jev grades: the ticket, the reply, and the policy the reply must stay within."""
    return {"policy": POLICY, "customer_ticket": ticket, "support_reply": reply}


def eval_questions() -> dict[str, Any]:
    from langchain_typesafe import Noul

    return {
        "fails": Noul(instructions="Does the support reply FAIL to resolve the customer's ticket? "
                  "A reply resolves it if it answers the actual question with a concrete next step; vague, off-topic, "
                  "deflecting or policy-contradicting replies fail."),
        "invents_policy": Noul(instructions="Does the reply state a fact, promise or policy that contradicts "
                           "or is not in the given policy?"),
    }


def examples(split: str | None = None) -> list[dict[str, Any]]:
    """``run_experiment`` / LangSmith dataset rows: inputs, reference outputs (the human label)."""
    return [{"id": c["id"], "inputs": {"id": c["id"], "ticket": c["ticket"]},
             "reference": {"fails": c["fails"], "kind": c["kind"]}}
            for c in REPLY_CASES if split in (None, c["split"])]


def bot_under_test(inputs: dict[str, Any]) -> dict[str, str]:
    """The 'application' being evaluated: here, the pre-written reply for that case."""
    return {"reply": next(c["reply"] for c in REPLY_CASES if c["id"] == inputs["id"])}


def jev_evaluators(classifier: Any) -> list[Callable[..., dict[str, Any]]]:
    """Two evaluators (``fails``, ``invents_policy``) sharing ONE Jev request per example."""
    cache: dict[str, Any] = {}

    def ask(inputs: dict[str, Any], outputs: dict[str, Any]) -> Any:
        key = json.dumps([inputs["ticket"], outputs["reply"]])
        if key not in cache:
            cache[key] = classifier.invoke({"state": reply_state(inputs["ticket"], outputs["reply"]),
                                            "questions": eval_questions()})
        return cache[key]

    def fails(inputs, outputs, reference_outputs=None):
        r = ask(inputs, outputs)
        return {"key": "fails", "score": round(r.nouls["fails"].noul, 3), "comment": f"jev {r.model}"}

    def invents_policy(inputs, outputs, reference_outputs=None):
        return {"key": "invents_policy", "score": round(ask(inputs, outputs).nouls["invents_policy"].noul, 3)}

    return [fails, invents_policy]
