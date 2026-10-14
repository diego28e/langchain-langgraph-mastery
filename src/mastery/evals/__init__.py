"""mastery.evals: measure LLM systems honestly (statistics, latency, run metadata).

Introduced in Module 01 (Lessons 01.03, 01.05, 01.06, 01.08 and Project 01),
reused by every module that reports a score, and extended in Module 10
(Testing, Evaluation and Observability).

Three submodules, all pure standard library:

- :mod:`mastery.evals.stats`: intervals (``wilson_interval``,
  ``bootstrap_interval``), paired tests (``paired_compare``, ``mcnemar_exact``,
  ``sign_test``), repeated runs (``summarize_repeats``, pass@k, pass^k),
  ``min_detectable_difference``, and dataset hygiene (``split_dev_test``,
  ``assert_disjoint``, ``find_leaks``).
- :mod:`mastery.evals.timing`: ``timed_invoke`` (rate-limiter waits excluded),
  ``stream_timings`` (first chunk vs first answer token), ``server_timing``
  and ``latency_summary`` (p50/p95).
- :mod:`mastery.evals.meta`: ``run_metadata`` (prompt version, content hashes,
  git SHA, package versions) for LangSmith metadata and report headers.

Example:
    >>> from mastery.evals import paired_compare, wilson_interval
    >>> print(wilson_interval(9, 10))
    0.900 [0.596, 0.982] (wilson, n=10)
    >>> zero_shot = {i: i < 9 for i in range(12)}
    >>> few_shot = {i: i < 10 for i in range(12)}
    >>> paired_compare(zero_shot, few_shot).verdict()
    'no detectable difference (treat as noise)'
"""

from __future__ import annotations

from mastery.evals.meta import (
    DEFAULT_PACKAGES,
    content_hash,
    file_hash,
    format_metadata,
    git_info,
    model_fingerprint,
    package_versions,
    run_metadata,
)
from mastery.evals.stats import (
    NOISE_VERDICT,
    Interval,
    Leak,
    LeakageError,
    PairedResult,
    RepeatSummary,
    assert_disjoint,
    bootstrap_interval,
    find_leaks,
    mcnemar_exact,
    min_detectable_difference,
    newcombe_paired_interval,
    paired_compare,
    pass_at_k,
    pass_hat_k,
    sign_test,
    split_dev_test,
    summarize_repeats,
    wilson_interval,
)
from mastery.evals.timing import (
    LatencySummary,
    LimiterInsideTimingWarning,
    ServerTiming,
    StreamTimings,
    Timed,
    astream_timings,
    atimed_invoke,
    attached_rate_limiters,
    latency_summary,
    nearest_rank,
    server_timing,
    stream_timings,
    timed_invoke,
)

__all__ = [
    "DEFAULT_PACKAGES",
    "NOISE_VERDICT",
    "Interval",
    "LatencySummary",
    "Leak",
    "LeakageError",
    "LimiterInsideTimingWarning",
    "PairedResult",
    "RepeatSummary",
    "ServerTiming",
    "StreamTimings",
    "Timed",
    "assert_disjoint",
    "astream_timings",
    "atimed_invoke",
    "attached_rate_limiters",
    "bootstrap_interval",
    "content_hash",
    "file_hash",
    "find_leaks",
    "format_metadata",
    "git_info",
    "latency_summary",
    "mcnemar_exact",
    "min_detectable_difference",
    "model_fingerprint",
    "nearest_rank",
    "newcombe_paired_interval",
    "package_versions",
    "paired_compare",
    "pass_at_k",
    "pass_hat_k",
    "run_metadata",
    "server_timing",
    "sign_test",
    "split_dev_test",
    "stream_timings",
    "summarize_repeats",
    "timed_invoke",
    "wilson_interval",
]
