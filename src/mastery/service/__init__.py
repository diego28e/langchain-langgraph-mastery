"""mastery.service: production building blocks for serving an agent (Module 12).

Part of the course increment for Module 12: SLOs and budgets (12.01), resilience (12.02), the
background run manager (12.03), and the FastAPI service (12.04, ``mastery.service.app``, needs the
``[service]`` extra, so it is not imported here). Later lessons add persistence, JWT auth and telemetry.
"""

from mastery.service.budgets import BudgetDecision, CostBudget, LatencyBudget, SpendLedger, estimate_request_cost
from mastery.service.resilience import flaky, transient_only
from mastery.service.runs import Event, OverBudget, Run, RunManager, ServiceBusy, ThreadBusy
from mastery.service.slo import (
    SLO,
    RunRecord,
    SLOResult,
    burn_rate,
    default_slos,
    error_budget_policy,
    evaluate_slo,
    percentile,
    synthetic_runs,
)

__all__ = [
    "SLO",
    "BudgetDecision",
    "CostBudget",
    "Event",
    "LatencyBudget",
    "OverBudget",
    "Run",
    "RunManager",
    "RunRecord",
    "SLOResult",
    "ServiceBusy",
    "SpendLedger",
    "ThreadBusy",
    "burn_rate",
    "default_slos",
    "error_budget_policy",
    "estimate_request_cost",
    "evaluate_slo",
    "flaky",
    "percentile",
    "synthetic_runs",
    "transient_only",
]
