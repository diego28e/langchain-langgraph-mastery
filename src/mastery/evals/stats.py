"""Small-sample statistics for comparing prompts, models and agents honestly.

Introduced in Module 01 (Lesson 01.03 and Project 01) and reused by every later
module that reports a score (memory, guardrails, RAG, multi-agent evaluations,
and the full treatment in Module 10).

Why this exists:
    Course experiments are small: 10 to 60 items, often run once. On 10 items,
    9/10 correct is compatible with a true accuracy anywhere from about 60% to
    98%, so "variant B scored 2 points higher" is usually noise. These helpers
    put an interval on every number and a test behind every "B is better".

What is here:
    - Intervals: :func:`wilson_interval` (a pass rate), :func:`bootstrap_interval`
      (any average, optionally resampling whole clusters such as one posting's
      fields or one item's repeated runs).
    - Paired tests: :func:`mcnemar_exact` (pass/fail), :func:`sign_test`
      (scores), and :func:`paired_compare`, which picks the right one and returns
      a :class:`PairedResult` with a plain-English :meth:`PairedResult.verdict`.
    - Repeats: :func:`summarize_repeats` (per-run means, flip rate, pass@k,
      pass^k), plus the unbiased :func:`pass_at_k` / :func:`pass_hat_k`.
    - Planning: :func:`min_detectable_difference` (how big a gap your dataset
      can see at all).
    - Dataset hygiene: :func:`split_dev_test` (stable hash split),
      :func:`assert_disjoint` and :func:`find_leaks` (test items copied into a
      dev set or into a prompt).

Everything is pure standard library (``math``, ``random``, ``statistics``,
``hashlib``), deterministic for a given ``seed``, and safe to call from
offline notebook cells.

Sources for the formulas:
    - Wilson score interval: Wilson (1927), JASA 22:209-212.
    - Paired difference interval (method 10): Newcombe (1998), "Improved
      confidence intervals for the difference between binomial proportions
      based on paired data", Statistics in Medicine 17:2635-2650.
    - Exact McNemar test: the two-sided exact binomial test on the discordant
      pairs (McNemar 1947); mid-p variant: Fagerland, Lydersen and Laake (2013),
      BMC Medical Research Methodology 13:91.
    - pass@k estimator: Chen et al. (2021), "Evaluating Large Language Models
      Trained on Code" (arXiv:2107.03374). pass^k: Yao et al. (2024),
      "tau-bench" (arXiv:2406.12045).
"""

from __future__ import annotations

import hashlib
import math
import random
import re
import statistics
import unicodedata
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "DEFAULT_CONFIDENCE",
    "DEFAULT_RESAMPLES",
    "DEFAULT_TEST_FRACTION",
    "NOISE_VERDICT",
    "Interval",
    "Leak",
    "LeakageError",
    "PairedResult",
    "RepeatSummary",
    "assert_disjoint",
    "bootstrap_interval",
    "find_leaks",
    "mcnemar_exact",
    "min_detectable_difference",
    "newcombe_paired_interval",
    "paired_compare",
    "pass_at_k",
    "pass_hat_k",
    "sign_test",
    "split_dev_test",
    "summarize_repeats",
    "wilson_interval",
]

# 95% intervals are the convention in most papers and dashboards.
DEFAULT_CONFIDENCE = 0.95
# 2,000 bootstrap resamples keep the interval ends stable to about +/-0.01 on
# course-sized data and take well under a second in pure Python.
DEFAULT_RESAMPLES = 2000
# Share of items that go to the held-out TEST split. The test set is the one
# you report (once), so it gets most of the items; the dev set is for iterating.
DEFAULT_TEST_FRACTION = 0.67
# Differences smaller than this are treated as ties (floating-point noise).
TIE_TOLERANCE = 1e-12
# The exact words PairedResult.verdict() uses when the test is not significant.
NOISE_VERDICT = "no detectable difference (treat as noise)"

Number = float | int | bool
ItemId = Hashable


# ---------------------------------------------------------------------------
# Intervals
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Interval:
    """A point estimate with a confidence interval.

    ``str(interval)`` reads ``0.900 [0.596, 0.982] (wilson, n=10)``, and
    format specs apply to all three numbers: ``f"{interval:.1%}"`` gives
    ``90.0% [59.6%, 98.2%] (wilson, n=10)``.

    Attributes:
        estimate: The observed value (for example the pass rate).
        low: Lower end of the interval.
        high: Upper end of the interval.
        confidence: Confidence level, e.g. ``0.95``.
        method: How the interval was computed (``"wilson"``, ``"bootstrap"``...).
        n: Number of observations behind the estimate.
    """

    estimate: float
    low: float
    high: float
    confidence: float = DEFAULT_CONFIDENCE
    method: str = ""
    n: int = 0

    @property
    def width(self) -> float:
        """Return ``high - low``: how uncertain the estimate still is."""
        return self.high - self.low

    def contains(self, value: float) -> bool:
        """Return True when ``value`` lies inside the interval (ends included)."""
        return self.low <= value <= self.high

    def __format__(self, spec: str) -> str:
        spec = spec or ".3f"
        numbers = f"{self.estimate:{spec}} [{self.low:{spec}}, {self.high:{spec}}]"
        return f"{numbers} ({self.method}, n={self.n})"

    def __str__(self) -> str:
        return format(self, "")


def _z(confidence: float) -> float:
    """Two-sided normal critical value (1.96 for 95%)."""
    if not 0 < confidence < 1:
        raise ValueError(f"confidence must be between 0 and 1, got {confidence!r}")
    return statistics.NormalDist().inv_cdf(1 - (1 - confidence) / 2)


def _wilson_bounds(successes: int, n: int, z: float) -> tuple[float, float]:
    """Wilson score bounds without validation (n > 0)."""
    p = successes / n
    z2 = z * z
    denominator = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denominator
    # The formula gives exactly 0 / 1 at the edges up to rounding; make it exact.
    low = 0.0 if successes == 0 else max(0.0, center - margin)
    high = 1.0 if successes == n else min(1.0, center + margin)
    return low, high


def wilson_interval(successes: int, n: int, confidence: float = DEFAULT_CONFIDENCE) -> Interval:
    """Confidence interval for a pass rate (``successes`` out of ``n``).

    The Wilson score interval stays inside [0, 1] and behaves well for small
    ``n`` and for rates near 0 or 1, where the textbook ``p +/- 1.96*se``
    interval breaks down (it gives [0.9, 0.9] for 9/9).

    Args:
        successes: Number of passing items.
        n: Number of items. Must be at least 1.
        confidence: Confidence level, default 0.95.

    Returns:
        An :class:`Interval` with ``method="wilson"``.

    Raises:
        ValueError: If ``n < 1``, ``successes`` is outside ``[0, n]``, or
            ``confidence`` is not between 0 and 1.

    Example:
        >>> print(wilson_interval(9, 10))
        0.900 [0.596, 0.982] (wilson, n=10)
    """
    if isinstance(n, bool) or int(n) != n or n < 1:
        raise ValueError(f"n must be a positive integer (an interval needs data), got {n!r}")
    if isinstance(successes, bool) or int(successes) != successes or not 0 <= successes <= n:
        raise ValueError(f"successes must be an integer between 0 and n={n}, got {successes!r}")
    successes, n = int(successes), int(n)
    low, high = _wilson_bounds(successes, n, _z(confidence))
    return Interval(successes / n, low, high, confidence, "wilson", n)


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolation quantile of already sorted values (0 <= q <= 1)."""
    position = q * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def _as_floats(values: Iterable[Number], what: str = "values") -> list[float]:
    floats = [float(v) for v in values]
    if not floats:
        raise ValueError(f"{what} is empty: an interval needs at least one observation")
    if any(math.isnan(v) for v in floats):
        raise ValueError(f"{what} contains NaN; drop or fix missing scores first")
    return floats


def bootstrap_interval(
    values: Iterable[Number],
    *,
    statistic: Callable[[Sequence[float]], float] = statistics.fmean,
    clusters: Sequence[Hashable] | None = None,
    confidence: float = DEFAULT_CONFIDENCE,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int | None = 0,
) -> Interval:
    """Percentile bootstrap interval for any statistic (default: the mean).

    The bootstrap redraws the dataset with replacement many times, recomputes
    the statistic each time, and reports the middle ``confidence`` share of
    those values. Use it for averages of scores (F1, field accuracy, judge
    scores) where no simple formula exists.

    **Cluster bootstrap.** When several values come from the same source
    (the six fields of one job posting, or three repeated runs of one item),
    they are not independent, and an ordinary bootstrap gives an interval
    that is too narrow. Pass ``clusters`` (one id per value) and whole
    clusters are redrawn instead of single values.

    Args:
        values: The observations (bools count as 0/1).
        statistic: Function of a list of floats; default ``statistics.fmean``.
        clusters: Optional cluster id for each value (same length as ``values``).
        confidence: Confidence level, default 0.95.
        n_resamples: Number of bootstrap resamples (at least 100).
        seed: Random seed. The same seed gives the same interval; ``None``
            draws a fresh one each call.

    Returns:
        An :class:`Interval` whose estimate is ``statistic(values)``.

    Raises:
        ValueError: If ``values`` is empty or has NaN, ``clusters`` has the
            wrong length, or ``n_resamples < 100``.

    Note:
        With very few items (or clusters) the percentile bootstrap is too
        optimistic, and when every value is identical it collapses to a single
        point. Treat it as a rough range below about 20 items.
    """
    data = _as_floats(values)
    if n_resamples < 100:
        raise ValueError(f"n_resamples must be at least 100, got {n_resamples}")
    _z(confidence)  # validates the level
    rng = random.Random(seed)
    estimate = float(statistic(data))

    if clusters is None:
        groups = [[v] for v in data]
        method = "bootstrap"
    else:
        if len(clusters) != len(data):
            raise ValueError(f"clusters has {len(clusters)} ids for {len(data)} values; give one id per value")
        by_cluster: dict[Hashable, list[float]] = {}
        for cluster_id, value in zip(clusters, data, strict=True):
            by_cluster.setdefault(cluster_id, []).append(value)
        groups = list(by_cluster.values())
        method = f"cluster bootstrap, {len(groups)} clusters"

    k = len(groups)
    replicates = []
    for _ in range(n_resamples):
        # Step 1: draw k clusters (or values) with replacement.
        picks = rng.choices(range(k), k=k)
        # Step 2: recompute the statistic on the flattened resample.
        sample = [value for index in picks for value in groups[index]]
        replicates.append(float(statistic(sample)))
    replicates.sort()
    tail = (1 - confidence) / 2
    low, high = _quantile(replicates, tail), _quantile(replicates, 1 - tail)
    return Interval(estimate, low, high, confidence, method, len(data))


def newcombe_paired_interval(
    both: int,
    b_only: int,
    a_only: int,
    neither: int,
    confidence: float = DEFAULT_CONFIDENCE,
) -> Interval:
    """Interval for the difference of two paired pass rates (B minus A).

    Each item was scored pass/fail by both A and B; the four counts are the
    cells of the 2x2 table. This is Newcombe's (1998) method 10: Wilson
    intervals for each pass rate, combined with a correction for the
    correlation between A and B on the same items. It stays inside [-1, 1]
    and does not collapse to a point when A and B agree on every item.

    Args:
        both: Items both A and B pass.
        b_only: Items only B passes.
        a_only: Items only A passes.
        neither: Items both fail.
        confidence: Confidence level, default 0.95.

    Returns:
        An :class:`Interval` for ``pass_rate(B) - pass_rate(A)``.

    Raises:
        ValueError: If a count is negative or all counts are zero.
    """
    counts = (both, b_only, a_only, neither)
    if any(c < 0 for c in counts):
        raise ValueError(f"counts must be non-negative, got {counts}")
    n = sum(counts)
    if n == 0:
        raise ValueError("no paired items: an interval needs at least one pair")
    z = _z(confidence)
    # In Newcombe's notation e=both, f=b_only, g=a_only, h=neither, and the
    # difference (f - g) / n is "first classification minus second", here B - A.
    e, f, g, h = counts
    p_b, p_a = (e + f) / n, (e + g) / n
    low_b, high_b = _wilson_bounds(e + f, n, z)
    low_a, high_a = _wilson_bounds(e + g, n, z)
    numerator = e * h - f * g
    denominator_sq = (e + f) * (g + h) * (e + g) * (f + h)
    if denominator_sq == 0:
        phi = 0.0  # The paper substitutes 0 when any margin is empty.
    else:
        if numerator > 0:
            numerator = max(numerator - n / 2, 0)  # method 10's continuity correction
        phi = numerator / math.sqrt(denominator_sq)
    diff = (f - g) / n
    d_low = p_b - low_b
    d_high = high_b - p_b
    a_low = p_a - low_a
    a_high = high_a - p_a
    delta = math.sqrt(max(d_low**2 - 2 * phi * d_low * a_high + a_high**2, 0.0))
    epsilon = math.sqrt(max(d_high**2 - 2 * phi * d_high * a_low + a_low**2, 0.0))
    return Interval(diff, max(-1.0, diff - delta), min(1.0, diff + epsilon), confidence, "newcombe", n)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _binomial_two_sided(k_small: int, n: int, *, mid_p: bool = False) -> float:
    """Two-sided exact binomial p-value at p=0.5 for the smaller count."""
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(k_small + 1))
    if mid_p:
        tail -= math.comb(n, k_small) / 2
    # Python divides big integers exactly before rounding, so this is precise.
    return min(1.0, 2 * tail / 2**n)


def mcnemar_exact(a_only: int, b_only: int, *, mid_p: bool = False) -> float:
    """Exact McNemar test for paired pass/fail results.

    Only the items where A and B disagree carry information. Under "no
    difference" each disagreement is a coin flip, so the p-value is the
    two-sided binomial probability of a split at least this lopsided.

    Args:
        a_only: Items only A passes.
        b_only: Items only B passes.
        mid_p: Use the mid-p variant, which is less conservative and is
            recommended by Fagerland et al. (2013). Default False (exact).

    Returns:
        The two-sided p-value (1.0 when there are no disagreements).

    Raises:
        ValueError: If a count is negative.

    Example:
        >>> mcnemar_exact(0, 6)   # B fixed 6 items, broke none
        0.03125
    """
    if a_only < 0 or b_only < 0:
        raise ValueError(f"counts must be non-negative, got a_only={a_only}, b_only={b_only}")
    return _binomial_two_sided(min(a_only, b_only), a_only + b_only, mid_p=mid_p)


def sign_test(differences: Iterable[Number], *, tol: float = TIE_TOLERANCE) -> float:
    """Two-sided sign test on paired differences (ties are dropped).

    It only asks "does B beat A on more items than chance would give?",
    ignoring by how much. That makes it robust to a few extreme scores and
    valid for any score scale.

    Args:
        differences: ``score_b - score_a`` per item.
        tol: Differences with ``abs(d) <= tol`` count as ties.

    Returns:
        The two-sided p-value (1.0 when every difference is a tie).
    """
    diffs = [float(d) for d in differences]
    positive = sum(1 for d in diffs if d > tol)
    negative = sum(1 for d in diffs if d < -tol)
    return _binomial_two_sided(min(positive, negative), positive + negative)


@dataclass(frozen=True)
class PairedResult:
    """Outcome of :func:`paired_compare`: who wins, by how much, and is it real.

    Attributes:
        n: Number of paired items.
        a_wins: Items where A did better (higher score, or lower when
            ``higher_is_better`` is False).
        b_wins: Items where B did better.
        ties: Items with the same score.
        mean_diff: Interval for ``mean(B) - mean(A)`` (raw scores, so for
            latency a negative difference means B is faster).
        p_value: Two-sided p-value of ``test``.
        test: The test used, e.g. ``"mcnemar exact"``.
        alpha: Significance level used by :attr:`significant`.
        names: Display names for A and B.
        higher_is_better: False for metrics such as latency or cost.
        n_clusters: Number of clusters when a cluster-level test was used.
    """

    n: int
    a_wins: int
    b_wins: int
    ties: int
    mean_diff: Interval
    p_value: float
    test: str
    alpha: float = 0.05
    names: tuple[str, str] = ("A", "B")
    higher_is_better: bool = True
    n_clusters: int | None = None

    @property
    def significant(self) -> bool:
        """True when ``p_value < alpha``."""
        return self.p_value < self.alpha

    def _direction(self) -> tuple[int, int]:
        """(+1 = B better, -1 = A better, 0 = even) by the mean and by win counts."""
        good = self.mean_diff.estimate if self.higher_is_better else -self.mean_diff.estimate
        by_mean = (good > TIE_TOLERANCE) - (good < -TIE_TOLERANCE)
        by_wins = (self.b_wins > self.a_wins) - (self.b_wins < self.a_wins)
        return by_mean, by_wins

    @property
    def mixed(self) -> bool:
        """True when win counts and the mean difference point different ways."""
        by_mean, by_wins = self._direction()
        return bool(by_mean and by_wins and by_mean != by_wins)

    @property
    def winner(self) -> str | None:
        """Name of the better variant, or None when not significant or mixed."""
        if not self.significant or self.mixed:
            return None
        by_mean, by_wins = self._direction()
        direction = by_mean or by_wins
        if direction == 0:
            return None
        return self.names[1] if direction > 0 else self.names[0]

    def verdict(self) -> str:
        """One-line decision in plain English.

        Returns:
            ``"<name> better"`` when the test is significant, otherwise
            ``"no detectable difference (treat as noise)"``. When one variant
            wins more items but the other has the better mean, the verdict
            starts with ``"mixed:"``: look at the per-item differences first.
        """
        if not self.significant:
            return NOISE_VERDICT
        if self.mixed:
            more_wins = self.names[1] if self.b_wins > self.a_wins else self.names[0]
            return f"mixed: {more_wins} wins more items but has the worse mean; inspect the items"
        winner = self.winner
        return f"{winner} better" if winner else NOISE_VERDICT

    def __str__(self) -> str:
        a, b = self.names
        clusters = f", {self.n_clusters} clusters" if self.n_clusters else ""
        lines = [
            f"{b} vs {a} on {self.n} paired items{clusters}: "
            f"{b} wins {self.b_wins}, {a} wins {self.a_wins}, ties {self.ties}",
            f"difference ({b} - {a}): {self.mean_diff}",
            f"{self.test}: p = {self.p_value:.3g} (alpha = {self.alpha}) -> {self.verdict()}",
        ]
        if not self.significant and not self.mean_diff.contains(0):
            lines.append("borderline: the interval excludes 0 but the test does not; add items before deciding")
        elif self.significant and self.mean_diff.contains(0):
            lines.append("note: the wins are consistent, but the size of the average gain is uncertain (interval includes 0)")
        return "\n".join(lines)


def _check_ids(a: Mapping[ItemId, Any], b: Mapping[ItemId, Any]) -> list[ItemId]:
    only_a = [k for k in a if k not in b]
    only_b = [k for k in b if k not in a]
    if only_a or only_b:
        raise ValueError(
            "paired comparison needs the same item ids on both sides; "
            f"only in A: {only_a[:10]}, only in B: {only_b[:10]}"
        )
    if not a:
        raise ValueError("no items to compare")
    return list(a)


def paired_compare(
    a: Mapping[ItemId, Number],
    b: Mapping[ItemId, Number],
    *,
    names: tuple[str, str] = ("A", "B"),
    alpha: float = 0.05,
    higher_is_better: bool = True,
    clusters: Mapping[ItemId, Hashable] | None = None,
    confidence: float = DEFAULT_CONFIDENCE,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int | None = 0,
    tol: float = TIE_TOLERANCE,
) -> PairedResult:
    """Compare two variants scored on the SAME items.

    Pairing is what makes small comparisons possible: both variants see the
    same easy and hard items, so only the items where they disagree matter.

    Which test runs:
        - All values bool, no clusters: exact McNemar test, with Newcombe's
          interval for the difference in pass rates.
        - Numeric scores, no clusters: sign test, with a paired bootstrap
          interval for the mean difference.
        - ``clusters`` given (e.g. item id -> posting id, when one posting
          contributes several fields): sign test on the per-cluster mean
          differences and a cluster bootstrap interval, because items in one
          cluster are not independent.

    The verdict comes from the test; the interval says how large the
    difference might be. When the two disagree near the threshold,
    ``print(result)`` says so instead of hiding it.

    Args:
        a: Item id -> score (bool pass/fail or a number) for variant A.
        b: Item id -> score for variant B. Must have exactly the ids of ``a``.
        names: Display names for A and B, e.g. ``("zero-shot", "few-shot")``.
        alpha: Significance level, default 0.05.
        higher_is_better: Set False for latency, cost or error counts.
        clusters: Optional item id -> cluster id.
        confidence: Confidence level of the interval.
        n_resamples: Bootstrap resamples (numeric scores or clusters).
        seed: Random seed for the bootstrap.
        tol: Score differences within ``tol`` count as ties.

    Returns:
        A :class:`PairedResult`; ``print(result)`` shows the full report and
        ``result.verdict()`` the decision.

    Raises:
        ValueError: If the ids differ (the message lists them), there are no
            items, or ``clusters`` misses an id.
    """
    ids = _check_ids(a, b)
    diffs = [float(b[i]) - float(a[i]) for i in ids]
    if any(math.isnan(d) for d in diffs):
        raise ValueError("scores contain NaN; drop or fix missing scores first")
    higher = sum(1 for d in diffs if d > tol)  # items where B's score is higher
    lower = sum(1 for d in diffs if d < -tol)
    b_wins, a_wins = (higher, lower) if higher_is_better else (lower, higher)
    ties = len(diffs) - a_wins - b_wins
    all_bool = all(isinstance(a[i], bool) and isinstance(b[i], bool) for i in ids)

    if clusters is not None:
        missing = [i for i in ids if i not in clusters]
        if missing:
            raise ValueError(f"clusters has no cluster id for items {missing[:10]}")
        cluster_ids = [clusters[i] for i in ids]
        per_cluster: dict[Hashable, list[float]] = {}
        for cluster_id, d in zip(cluster_ids, diffs, strict=True):
            per_cluster.setdefault(cluster_id, []).append(d)
        cluster_means = [statistics.fmean(ds) for ds in per_cluster.values()]
        p_value = sign_test(cluster_means, tol=tol)
        interval = bootstrap_interval(
            diffs, clusters=cluster_ids, confidence=confidence, n_resamples=n_resamples, seed=seed
        )
        test, n_clusters = "sign test on cluster means", len(per_cluster)
    elif all_bool:
        both = sum(1 for i in ids if a[i] and b[i])
        neither = sum(1 for i in ids if not a[i] and not b[i])
        # higher = items only B passes, lower = items only A passes.
        p_value = mcnemar_exact(lower, higher)
        interval = newcombe_paired_interval(both, higher, lower, neither, confidence)
        test, n_clusters = "mcnemar exact", None
    else:
        p_value = sign_test(diffs, tol=tol)
        interval = bootstrap_interval(diffs, confidence=confidence, n_resamples=n_resamples, seed=seed)
        test, n_clusters = "sign test", None

    return PairedResult(
        n=len(ids),
        a_wins=a_wins,
        b_wins=b_wins,
        ties=ties,
        mean_diff=interval,
        p_value=p_value,
        test=test,
        alpha=alpha,
        names=(str(names[0]), str(names[1])),
        higher_is_better=higher_is_better,
        n_clusters=n_clusters,
    )


# ---------------------------------------------------------------------------
# Repeated runs
# ---------------------------------------------------------------------------


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k: chance that at least one of ``k`` tries passes.

    Estimated from ``n`` tries of which ``c`` passed (Chen et al., 2021):
    ``1 - C(n - c, k) / C(n, k)``.

    Args:
        n: Tries made for this item.
        c: Tries that passed.
        k: Tries you would allow in production (``k <= n``).

    Returns:
        A probability between 0 and 1.

    Raises:
        ValueError: If the counts are inconsistent.
    """
    _check_counts(n, c, k)
    if n - c < k:
        return 1.0
    return 1.0 - math.comb(n - c, k) / math.comb(n, k)


def pass_hat_k(n: int, c: int, k: int) -> float:
    """Unbiased pass^k: chance that ALL of ``k`` tries pass (reliability).

    Estimated from ``n`` tries of which ``c`` passed (tau-bench, Yao et al.,
    2024): ``C(c, k) / C(n, k)``. An agent that passes 80% of single tries can
    have a much lower pass^3, which is what a user who asks three times sees.

    Args:
        n: Tries made for this item.
        c: Tries that passed.
        k: Number of consecutive tries that must all pass (``k <= n``).

    Returns:
        A probability between 0 and 1.

    Raises:
        ValueError: If the counts are inconsistent.
    """
    _check_counts(n, c, k)
    return math.comb(c, k) / math.comb(n, k)


def _check_counts(n: int, c: int, k: int) -> None:
    if not (n >= 1 and 0 <= c <= n and 1 <= k <= n):
        raise ValueError(f"need n >= 1, 0 <= c <= n and 1 <= k <= n; got n={n}, c={c}, k={k}")


@dataclass(frozen=True)
class RepeatSummary:
    """How stable a variant is across ``k`` repeated runs on the same items.

    Attributes:
        k: Number of runs.
        n: Number of items per run.
        run_means: Mean score of each run, in run order.
        mean: Overall mean with an interval (Wilson for a single pass/fail
            run, otherwise a cluster bootstrap that keeps each item's runs
            together).
        run_sd: Standard deviation of the run means (None when ``k == 1``).
        flip_rate: Share of items that passed in some runs and failed in
            others (None when ``k == 1``).
        pass_at_k: Share of items that passed in at least one run.
        pass_hat_k: Share of items that passed in every run (pass^k).
        threshold: Score counted as a pass for numeric scores.
        passes: Item id -> number of runs it passed.
    """

    k: int
    n: int
    run_means: tuple[float, ...]
    mean: Interval
    run_sd: float | None
    flip_rate: float | None
    pass_at_k: float
    pass_hat_k: float
    threshold: float
    passes: Mapping[ItemId, int] = field(repr=False)

    @property
    def flaky_ids(self) -> list[ItemId]:
        """Ids of the items whose pass/fail outcome changed between runs."""
        return [item for item, c in self.passes.items() if 0 < c < self.k]

    def pass_at(self, j: int) -> float:
        """Mean unbiased pass@j over items, for any ``1 <= j <= k``."""
        return statistics.fmean(pass_at_k(self.k, c, j) for c in self.passes.values())

    def pass_hat(self, j: int) -> float:
        """Mean unbiased pass^j over items, for any ``1 <= j <= k``."""
        return statistics.fmean(pass_hat_k(self.k, c, j) for c in self.passes.values())

    def __str__(self) -> str:
        runs = " / ".join(f"{m:.3f}" for m in self.run_means)
        lines = [f"mean {self.mean}", f"{self.k} run(s) of {self.n} items: {runs}"]
        if self.k > 1:
            lines.append(
                f"run sd {self.run_sd:.3f} | flip rate {self.flip_rate:.3f} | "
                f"pass@{self.k} {self.pass_at_k:.3f} | pass^{self.k} {self.pass_hat_k:.3f}"
            )
        else:
            lines.append("one run only: repeat it (k >= 2) to see how often answers flip")
        return "\n".join(lines)


def summarize_repeats(
    runs: Sequence[Mapping[ItemId, Number]],
    *,
    threshold: float = 1.0,
    confidence: float = DEFAULT_CONFIDENCE,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int | None = 0,
) -> RepeatSummary:
    """Summarize ``k`` runs of the same variant on the same items.

    LLM outputs change between runs, even at temperature 0. Running the eval
    ``k`` times shows how much of a score is the variant and how much is luck.

    Args:
        runs: One mapping per run: item id -> score (bool or number). Every
            run must cover the same ids.
        threshold: A numeric score ``>= threshold`` counts as a pass (bools
            are passes when True). Default 1.0 (a perfect score).
        confidence: Confidence level of the mean's interval.
        n_resamples: Bootstrap resamples for the interval.
        seed: Random seed for the bootstrap.

    Returns:
        A :class:`RepeatSummary`.

    Raises:
        ValueError: If ``runs`` is empty or the runs cover different ids.
    """
    if not runs:
        raise ValueError("runs is empty: pass at least one run (a mapping of item id -> score)")
    ids = list(runs[0])
    if not ids:
        raise ValueError("the runs contain no items")
    for index, run in enumerate(runs[1:], start=2):
        if set(run) != set(ids):
            only_first = [i for i in ids if i not in run][:10]
            only_this = [i for i in run if i not in runs[0]][:10]
            raise ValueError(
                f"run {index} covers different items than run 1; "
                f"missing from run {index}: {only_first}, extra in run {index}: {only_this}"
            )
    k, n = len(runs), len(ids)

    def passed(value: Number) -> bool:
        return bool(value) if isinstance(value, bool) else float(value) >= threshold

    run_means = tuple(statistics.fmean(float(run[i]) for i in ids) for run in runs)
    passes = {i: sum(passed(run[i]) for run in runs) for i in ids}
    all_bool = all(isinstance(run[i], bool) for run in runs for i in ids)
    if k == 1 and all_bool:
        mean = wilson_interval(sum(passes.values()), n, confidence)
    else:
        values = [float(run[i]) for run in runs for i in ids]
        cluster_ids = [i for _ in runs for i in ids]
        mean = bootstrap_interval(
            values,
            clusters=cluster_ids if k > 1 else None,
            confidence=confidence,
            n_resamples=n_resamples,
            seed=seed,
        )
    return RepeatSummary(
        k=k,
        n=n,
        run_means=run_means,
        mean=mean,
        run_sd=statistics.stdev(run_means) if k > 1 else None,
        flip_rate=sum(1 for c in passes.values() if 0 < c < k) / n if k > 1 else None,
        pass_at_k=sum(1 for c in passes.values() if c > 0) / n,
        pass_hat_k=sum(1 for c in passes.values() if c == k) / n,
        threshold=threshold,
        passes=passes,
    )


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


def min_detectable_difference(n: int, p: float = 0.8, alpha: float = 0.05, power: float = 0.8) -> float:
    """Smallest accuracy gap a dataset of ``n`` items can reliably detect.

    A teaching aid, not a power analysis for a paper: it uses the normal
    approximation for two independent pass rates near ``p``,
    ``(z_(1-alpha/2) + z_power) * sqrt(2 p (1 - p) / n)``. A paired design
    (same items for both variants) usually does better when the variants
    agree on most items, but the order of magnitude is the lesson: with 12
    items only huge gaps are visible.

    Args:
        n: Items per variant.
        p: Expected pass rate of the baseline, strictly between 0 and 1.
        alpha: Significance level (two-sided).
        power: Chance of detecting a real gap of this size.

    Returns:
        The gap in pass rate (0.25 means 25 percentage points). It can exceed
        what is possible (for example ``1 - p``): that means "this dataset
        cannot detect any realistic improvement".

    Raises:
        ValueError: If an argument is out of range.
    """
    if n < 1:
        raise ValueError(f"n must be at least 1, got {n}")
    for name, value in (("p", p), ("alpha", alpha), ("power", power)):
        if not 0 < value < 1:
            raise ValueError(f"{name} must be strictly between 0 and 1, got {value}")
    normal = statistics.NormalDist()
    z_total = normal.inv_cdf(1 - alpha / 2) + normal.inv_cdf(power)
    return z_total * math.sqrt(2 * p * (1 - p) / n)


# ---------------------------------------------------------------------------
# Dataset hygiene
# ---------------------------------------------------------------------------


def _key_func(key: str | Callable[[Any], Any]) -> Callable[[Any], Any]:
    """Turn a field name into a getter (dict key or attribute); pass callables through."""
    if callable(key):
        return key
    return lambda item: item[key] if isinstance(item, Mapping) else getattr(item, key)


def _bucket(value: Any, salt: str) -> float:
    """Map a key to [0, 1) with SHA-256: same key, same bucket, on every machine."""
    digest = hashlib.sha256(f"{salt}:{value}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def split_dev_test(
    items: Iterable[Any],
    *,
    key: str | Callable[[Any], Any] = "id",
    test_fraction: float = DEFAULT_TEST_FRACTION,
    salt: str = "mastery",
) -> tuple[list[Any], list[Any]]:
    """Split items into a dev set (iterate here) and a test set (report once).

    Each item's side depends only on a hash of its key, not on its position
    or on the other items. So appending new items never moves old ones, and
    everyone who runs the notebook gets the same split.

    Args:
        items: The dataset (dicts, tuples, objects...).
        key: Field name (for dicts) or function returning a stable, unique id.
        test_fraction: Expected share of items in the test set.
        salt: Change it to draw a different (still stable) split.

    Returns:
        ``(dev, test)`` lists, each in the input order.

    Raises:
        ValueError: If ``test_fraction`` is not between 0 and 1 or two items
            share a key.

    Note:
        The fraction is reached on average, not exactly: on 12 items a 0.67
        split can give 6 or 10 test items. Print the sizes and change ``salt``
        once (before looking at any results) if a side is too small.
    """
    if not 0 < test_fraction < 1:
        raise ValueError(f"test_fraction must be strictly between 0 and 1, got {test_fraction}")
    get_key = _key_func(key)
    dev: list[Any] = []
    test: list[Any] = []
    seen: set[Any] = set()
    duplicates: list[Any] = []
    for item in items:
        item_key = get_key(item)
        if item_key in seen:
            duplicates.append(item_key)
        seen.add(item_key)
        (test if _bucket(item_key, salt) < test_fraction else dev).append(item)
    if duplicates:
        raise ValueError(f"duplicate keys (fix the dataset ids first): {duplicates[:10]}")
    return dev, test


class LeakageError(ValueError):
    """Raised when test items leak into the dev set (same id or same text)."""


def _normalize_text(text: str) -> str:
    """Casefold, unify Unicode forms, keep only word characters."""
    text = unicodedata.normalize("NFKC", str(text)).casefold()
    return " ".join(re.findall(r"\w+", text))


def _words(text: str) -> list[str]:
    return _normalize_text(text).split()


def assert_disjoint(
    dev: Iterable[Any],
    test: Iterable[Any],
    *,
    key: str | Callable[[Any], Any] | None = "id",
    text: str | Callable[[Any], Any] | None = None,
) -> None:
    """Fail loudly if any test item also appears in the dev set.

    Checks shared ids and, when ``text`` is given, shared text after
    normalization (case, spacing and punctuation are ignored, so
    ``"Hello,  World"`` matches ``"hello world"``).

    Args:
        dev: Dev items.
        test: Test items.
        key: Field name or function for the id; None skips the id check.
        text: Field name or function for the text; None skips the text check.

    Raises:
        LeakageError: Listing the overlapping ids and texts.
        ValueError: If both ``key`` and ``text`` are None.
    """
    if key is None and text is None:
        raise ValueError("give key, text, or both: there is nothing to compare")
    dev_items, test_items = list(dev), list(test)
    problems = []
    if key is not None:
        get_key = _key_func(key)
        dev_keys = {get_key(item) for item in dev_items}
        shared = [get_key(item) for item in test_items if get_key(item) in dev_keys]
        if shared:
            problems.append(f"{len(shared)} shared id(s): {shared[:10]}")
    if text is not None:
        get_text = _key_func(text)
        dev_texts = {_normalize_text(get_text(item)) for item in dev_items}
        shared_texts = [get_text(item) for item in test_items if _normalize_text(get_text(item)) in dev_texts]
        if shared_texts:
            preview = [str(t)[:60] for t in shared_texts[:5]]
            problems.append(f"{len(shared_texts)} shared text(s): {preview}")
    if problems:
        raise LeakageError("test items leak into dev: " + "; ".join(problems))


@dataclass(frozen=True)
class Leak:
    """Text shared between a prompt and one test item.

    Attributes:
        item: Id (or index) of the test item.
        spans: The shared passages, as normalized words, longest first.
        longest: Length of the longest shared passage, in words.
    """

    item: Any
    spans: tuple[str, ...]
    longest: int

    def __str__(self) -> str:
        return f"{self.item}: {self.longest} shared words, e.g. {self.spans[0]!r}"


def find_leaks(
    prompt_text: str,
    test_texts: Mapping[Any, str] | Sequence[str],
    *,
    n: int = 6,
) -> list[Leak]:
    """Find passages of ``n`` or more words that a prompt copies from test items.

    Few-shot examples taken from the test set make a prompt look better than
    it is. This finds copied passages (word n-grams, ignoring case and
    punctuation) and returns the maximal shared spans per test item.

    Args:
        prompt_text: The full prompt (system message plus examples).
        test_texts: Test item id -> text, or a list of texts (ids = indexes).
        n: Minimum passage length in words. Lower it (e.g. 3) for short items.

    Returns:
        One :class:`Leak` per test item that shares a passage, worst first.
        An empty list means no copied passage was found.

    Raises:
        ValueError: If ``n < 1``.

    Note:
        This catches copying, not paraphrases or single-word hints (a label
        name, a rare skill). Also check that your examples' answers are not
        the test answers.
    """
    if n < 1:
        raise ValueError(f"n must be at least 1, got {n}")
    prompt_words = _words(prompt_text)
    prompt_grams = {tuple(prompt_words[i : i + n]) for i in range(len(prompt_words) - n + 1)}
    items = test_texts.items() if isinstance(test_texts, Mapping) else enumerate(test_texts)
    leaks = []
    for item_id, item_text in items:
        words = _words(item_text)
        covered = [False] * len(words)
        for i in range(len(words) - n + 1):
            if tuple(words[i : i + n]) in prompt_grams:
                for j in range(i, i + n):
                    covered[j] = True
        spans: list[list[str]] = []
        current: list[str] = []
        for word, is_covered in zip(words, covered, strict=True):
            if is_covered:
                current.append(word)
            elif current:
                spans.append(current)
                current = []
        if current:
            spans.append(current)
        if spans:
            spans.sort(key=len, reverse=True)
            leaks.append(Leak(item_id, tuple(" ".join(s) for s in spans), len(spans[0])))
    leaks.sort(key=lambda leak: leak.longest, reverse=True)
    return leaks
