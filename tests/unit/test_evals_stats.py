"""Unit tests for mastery.evals.stats (pure arithmetic, offline, deterministic)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pytest

from mastery.evals.stats import (
    NOISE_VERDICT,
    Interval,
    LeakageError,
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

# ---------------------------------------------------------------------------
# Wilson interval
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("successes", "n", "low", "high"),
    [
        (9, 10, 0.596, 0.982),  # the classic "9/10 is not 90%" example
        (7, 10, 0.397, 0.892),
        (14, 16, 0.640, 0.965),
        (11, 12, 0.646, 0.985),
    ],
)
def test_wilson_known_values(successes: int, n: int, low: float, high: float) -> None:
    interval = wilson_interval(successes, n)
    assert interval.estimate == pytest.approx(successes / n)
    assert interval.low == pytest.approx(low, abs=5e-4)
    assert interval.high == pytest.approx(high, abs=5e-4)
    assert (interval.method, interval.n, interval.confidence) == ("wilson", n, 0.95)


def test_wilson_edges_are_exact() -> None:
    assert wilson_interval(0, 10).low == 0.0
    assert wilson_interval(10, 10).high == 1.0
    assert wilson_interval(0, 10).high < 0.5 < wilson_interval(10, 10).low


@pytest.mark.parametrize(("successes", "n"), [(0, 0), (1, 0), (-1, 10), (11, 10), (True, 10)])
def test_wilson_rejects_impossible_counts(successes: int, n: int) -> None:
    with pytest.raises(ValueError):
        wilson_interval(successes, n)


def test_wilson_rejects_bad_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        wilson_interval(5, 10, confidence=1.0)


def test_higher_confidence_gives_a_wider_interval() -> None:
    assert wilson_interval(9, 10, confidence=0.99).width > wilson_interval(9, 10).width


def test_interval_prints_for_humans() -> None:
    interval = wilson_interval(9, 10)
    assert str(interval) == "0.900 [0.596, 0.982] (wilson, n=10)"
    assert f"{interval:.1%}" == "90.0% [59.6%, 98.2%] (wilson, n=10)"
    assert interval.contains(0.9) and not interval.contains(0.5)


# ---------------------------------------------------------------------------
# Newcombe's paired interval
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("both", "b_only", "a_only", "neither", "low", "high"),
    [
        # Newcombe (1998), Statistics in Medicine 17:2635-2650, Table III, method 10.
        (36, 12, 2, 0, 0.0569, 0.3404),
        (20, 12, 2, 16, 0.0562, 0.3292),
        (35, 14, 0, 1, 0.1461, 0.4175),
        (0, 30, 0, 0, 0.8395, 1.0),
        (54, 0, 0, 0, -0.0664, 0.0664),
    ],
)
def test_newcombe_matches_published_table(
    both: int, b_only: int, a_only: int, neither: int, low: float, high: float
) -> None:
    interval = newcombe_paired_interval(both, b_only, a_only, neither)
    assert interval.estimate == pytest.approx((b_only - a_only) / (both + b_only + a_only + neither))
    assert interval.low == pytest.approx(low, abs=1e-4)
    assert interval.high == pytest.approx(high, abs=1e-4)


def test_newcombe_is_antisymmetric_and_rejects_bad_counts() -> None:
    forward = newcombe_paired_interval(20, 12, 2, 16)
    backward = newcombe_paired_interval(20, 2, 12, 16)
    assert backward.low == pytest.approx(-forward.high) and backward.high == pytest.approx(-forward.low)
    with pytest.raises(ValueError):
        newcombe_paired_interval(0, 0, 0, 0)
    with pytest.raises(ValueError):
        newcombe_paired_interval(1, -1, 0, 0)


# ---------------------------------------------------------------------------
# Exact tests
# ---------------------------------------------------------------------------


def test_mcnemar_exact_small_counts() -> None:
    assert mcnemar_exact(0, 6) == pytest.approx(0.03125)  # 2 * (1/2)**6
    assert mcnemar_exact(6, 0) == pytest.approx(0.03125)
    assert mcnemar_exact(3, 0) == pytest.approx(0.25)
    assert mcnemar_exact(1, 1) == 1.0
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(0, 5) == pytest.approx(0.0625)  # 5-0 is NOT significant at 0.05


def test_mcnemar_mid_p_is_less_conservative() -> None:
    assert mcnemar_exact(0, 6, mid_p=True) == pytest.approx(0.015625)
    assert mcnemar_exact(2, 8, mid_p=True) < mcnemar_exact(2, 8)
    with pytest.raises(ValueError):
        mcnemar_exact(-1, 2)


def test_sign_test_drops_ties() -> None:
    assert sign_test([1, 1, 1, 0, 0, 0]) == pytest.approx(sign_test([1, 1, 1])) == pytest.approx(0.25)
    assert sign_test([0.1 + 0.2 - 0.3, 0.0]) == 1.0  # float rounding counts as a tie
    assert sign_test([]) == 1.0
    assert sign_test([0.5] * 6) == pytest.approx(mcnemar_exact(0, 6))


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------


def test_bootstrap_is_deterministic_for_a_seed() -> None:
    rng = random.Random(7)
    values = [rng.random() for _ in range(40)]
    first = bootstrap_interval(values, seed=3)
    assert first == bootstrap_interval(values, seed=3)
    assert first != bootstrap_interval(values, seed=4)
    assert first.contains(first.estimate)
    assert first.estimate == pytest.approx(sum(values) / len(values))
    assert first.method == "bootstrap" and first.n == 40


def test_cluster_bootstrap_is_wider_on_correlated_data() -> None:
    # 10 postings x 5 fields; all fields of a posting are right or wrong together.
    outcomes = [1.0, 1.0, 0.0, 1.0, 0.0, 1.0, 1.0, 1.0, 0.0, 1.0]
    values = [outcome for outcome in outcomes for _ in range(5)]
    clusters = [posting for posting in range(10) for _ in range(5)]
    plain = bootstrap_interval(values)
    clustered = bootstrap_interval(values, clusters=clusters)
    assert clustered.width > plain.width
    assert clustered.method == "cluster bootstrap, 10 clusters"


def test_bootstrap_accepts_other_statistics() -> None:
    interval = bootstrap_interval([1, 2, 3, 4, 100], statistic=lambda xs: sorted(xs)[len(xs) // 2])
    assert interval.estimate == 3.0


@pytest.mark.parametrize(
    ("values", "kwargs"),
    [([], {}), ([1.0, math.nan], {}), ([1.0, 2.0], {"clusters": ["a"]}), ([1.0], {"n_resamples": 10})],
)
def test_bootstrap_rejects_bad_input(values: list[float], kwargs: dict) -> None:
    with pytest.raises(ValueError):
        bootstrap_interval(values, **kwargs)


# ---------------------------------------------------------------------------
# Paired comparison
# ---------------------------------------------------------------------------


def test_paired_compare_requires_matching_ids() -> None:
    with pytest.raises(ValueError, match=r"only in A: \['t3'\].*only in B: \['t9'\]"):
        paired_compare({"t1": True, "t3": True}, {"t1": True, "t9": False})
    with pytest.raises(ValueError):
        paired_compare({}, {})


def test_one_item_gap_on_twelve_is_noise() -> None:
    zero_shot = {f"T{i:02d}": i < 10 for i in range(12)}
    few_shot = {f"T{i:02d}": i < 11 for i in range(12)}
    result = paired_compare(zero_shot, few_shot, names=("zero-shot", "few-shot"))
    assert (result.n, result.a_wins, result.b_wins, result.ties) == (12, 0, 1, 11)
    assert result.test == "mcnemar exact" and result.p_value == 1.0
    assert not result.significant and result.winner is None
    assert result.verdict() == NOISE_VERDICT
    assert "few-shot vs zero-shot" in str(result) and NOISE_VERDICT in str(result)


def test_consistent_gap_is_detected() -> None:
    a = {i: i >= 6 for i in range(20)}  # A fails the first 6 items
    b = {i: True for i in range(20)}
    result = paired_compare(a, b, names=("old", "new"))
    assert result.p_value == pytest.approx(mcnemar_exact(0, 6))
    assert result.significant and result.verdict() == "new better"
    assert result.mean_diff.estimate == pytest.approx(0.3)
    assert result.mean_diff.method == "newcombe"


def test_borderline_case_is_flagged_not_hidden() -> None:
    # 5 fixes and 0 regressions: exact p = 0.0625, but the interval excludes 0.
    a = {i: i >= 5 for i in range(12)}
    b = {i: True for i in range(12)}
    result = paired_compare(a, b)
    assert result.verdict() == NOISE_VERDICT
    assert "borderline" in str(result)


def test_numeric_scores_use_sign_test_and_bootstrap() -> None:
    rng = random.Random(1)
    a = {i: rng.random() for i in range(30)}
    b = {i: a[i] + 0.05 for i in range(30)}
    result = paired_compare(a, b)
    assert result.test == "sign test" and result.mean_diff.method == "bootstrap"
    assert result.b_wins == 30 and result.verdict() == "B better"
    assert result.mean_diff.estimate == pytest.approx(0.05)


def test_lower_is_better_flips_the_winner() -> None:
    fast = {i: 1.0 for i in range(15)}
    slow = {i: 2.0 for i in range(15)}
    result = paired_compare(slow, fast, names=("slow", "fast"), higher_is_better=False)
    assert result.b_wins == 15 and result.a_wins == 0
    assert result.verdict() == "fast better"


def test_mixed_signals_are_reported() -> None:
    # B is slightly better on 10 items and much worse on 2: wins and mean disagree.
    a = {i: 0.0 for i in range(12)}
    b = {i: (0.01 if i < 10 else -1.0) for i in range(12)}
    result = paired_compare(a, b)
    assert result.significant and result.mixed
    assert result.verdict().startswith("mixed:") and result.winner is None


def test_clusters_switch_to_a_cluster_level_test() -> None:
    a = {(p, f): False for p in range(8) for f in range(4)}
    b = {(p, f): p < 7 for p in range(8) for f in range(4)}
    result = paired_compare(a, b, clusters={key: key[0] for key in a})
    assert result.test == "sign test on cluster means" and result.n_clusters == 8
    assert result.p_value == pytest.approx(mcnemar_exact(0, 7))
    with pytest.raises(ValueError, match="cluster id"):
        paired_compare(a, b, clusters={})


def test_paired_compare_rejects_nan() -> None:
    with pytest.raises(ValueError, match="NaN"):
        paired_compare({1: 0.5}, {1: math.nan})


# ---------------------------------------------------------------------------
# Repeated runs
# ---------------------------------------------------------------------------


def test_summarize_repeats_hand_made_case() -> None:
    runs = [
        {"x": True, "y": True, "z": False, "w": True},
        {"x": True, "y": False, "z": False, "w": False},
        {"x": True, "y": True, "z": False, "w": False},
    ]
    summary = summarize_repeats(runs)
    assert (summary.k, summary.n) == (3, 4)
    assert summary.run_means == pytest.approx((0.75, 0.25, 0.5))
    assert summary.flip_rate == pytest.approx(0.5)  # y and w changed
    assert summary.pass_at_k == pytest.approx(0.75)  # x, y, w passed at least once
    assert summary.pass_hat_k == pytest.approx(0.25)  # only x passed every time
    assert summary.flaky_ids == ["y", "w"]
    assert summary.pass_at(1) == pytest.approx(0.5) == summary.pass_hat(1)
    assert summary.pass_at(3) == pytest.approx(summary.pass_at_k)
    assert summary.mean.method == "cluster bootstrap, 4 clusters"
    assert "pass^3 0.250" in str(summary)


def test_single_run_uses_wilson_and_reports_no_flakiness() -> None:
    summary = summarize_repeats([{i: i < 9 for i in range(10)}])
    assert summary.mean == wilson_interval(9, 10)
    assert summary.run_sd is None and summary.flip_rate is None
    assert "repeat it" in str(summary)


def test_numeric_repeats_use_the_threshold() -> None:
    runs = [{"a": 0.9, "b": 0.4}, {"a": 0.7, "b": 0.6}]
    summary = summarize_repeats(runs, threshold=0.5)
    assert summary.passes == {"a": 2, "b": 1}
    assert summary.flaky_ids == ["b"]


def test_summarize_repeats_rejects_mismatched_runs() -> None:
    with pytest.raises(ValueError, match="different items"):
        summarize_repeats([{"a": True}, {"b": True}])
    with pytest.raises(ValueError):
        summarize_repeats([])
    with pytest.raises(ValueError):
        summarize_repeats([{}])


def test_pass_at_k_and_pass_hat_k_estimators() -> None:
    assert pass_at_k(5, 1, 1) == pytest.approx(0.2)
    assert pass_at_k(5, 0, 3) == 0.0
    assert pass_at_k(5, 3, 3) == 1.0  # only 2 failures: any 3 tries include a pass
    assert pass_at_k(10, 2, 3) == pytest.approx(1 - math.comb(8, 3) / math.comb(10, 3))
    assert pass_hat_k(5, 3, 3) == pytest.approx(0.1)  # C(3,3) / C(5,3)
    assert pass_hat_k(5, 5, 3) == 1.0
    with pytest.raises(ValueError):
        pass_at_k(3, 4, 1)
    with pytest.raises(ValueError):
        pass_hat_k(3, 1, 4)


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------


def test_min_detectable_difference_shrinks_with_square_root_of_n() -> None:
    small, large = min_detectable_difference(12), min_detectable_difference(48)
    assert large == pytest.approx(small / 2)
    expected = (1.959964 + 0.841621) * math.sqrt(2 * 0.8 * 0.2 / 12)
    assert small == pytest.approx(expected, rel=1e-5)
    assert min_detectable_difference(100, power=0.9) > min_detectable_difference(100)
    with pytest.raises(ValueError):
        min_detectable_difference(0)
    with pytest.raises(ValueError):
        min_detectable_difference(10, p=1.0)


# ---------------------------------------------------------------------------
# Dataset hygiene
# ---------------------------------------------------------------------------


def _ids(items: list[dict]) -> list[str]:
    return [item["id"] for item in items]


def test_split_is_stable_when_items_are_appended() -> None:
    first = [{"id": f"T{i:03d}"} for i in range(50)]
    grown = first + [{"id": f"T{i:03d}"} for i in range(50, 120)]
    dev_1, test_1 = split_dev_test(first)
    dev_2, test_2 = split_dev_test(grown)
    assert set(_ids(dev_1)) <= set(_ids(dev_2))
    assert set(_ids(test_1)) <= set(_ids(test_2))
    assert split_dev_test(first) == (dev_1, test_1)


def test_split_is_a_partition_near_the_fraction() -> None:
    items = [{"id": i} for i in range(1000)]
    dev, test = split_dev_test(items)
    assert sorted(_ids(dev) + _ids(test)) == list(range(1000))
    assert 0.62 < len(test) / 1000 < 0.72
    assert split_dev_test(items, salt="other") != (dev, test)


def test_split_accepts_callables_and_attributes() -> None:
    @dataclass
    class Item:
        ticket_id: str

    objects = [Item(f"T{i}") for i in range(20)]
    by_attribute = split_dev_test(objects, key="ticket_id")
    by_callable = split_dev_test(objects, key=lambda item: item.ticket_id)
    assert by_attribute == by_callable


def test_split_rejects_duplicates_and_bad_fraction() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        split_dev_test([{"id": 1}, {"id": 1}])
    with pytest.raises(ValueError):
        split_dev_test([{"id": 1}], test_fraction=1.0)


def test_assert_disjoint_catches_shared_ids_and_normalized_text() -> None:
    dev = [{"id": "a", "text": "Hello  World"}]
    with pytest.raises(LeakageError, match="shared text"):
        assert_disjoint(dev, [{"id": "b", "text": "hello world"}], text="text")
    with pytest.raises(LeakageError, match="shared id"):
        assert_disjoint(dev, [{"id": "a", "text": "something else"}])
    assert_disjoint(dev, [{"id": "b", "text": "Goodbye"}], text="text")  # clean: no error
    assert issubclass(LeakageError, ValueError)
    with pytest.raises(ValueError):
        assert_disjoint(dev, dev, key=None, text=None)


def test_find_leaks_finds_a_copied_example() -> None:
    test_items = {
        "T07": "My card was charged twice for the same order last week, please refund one.",
        "T08": "The export button does nothing when I click it.",
    }
    prompt = (
        "Classify the ticket. Example: 'my card was charged twice for the same order last week' -> billing."
    )
    leaks = find_leaks(prompt, test_items)
    assert [leak.item for leak in leaks] == ["T07"]
    assert leaks[0].longest == 11
    assert leaks[0].spans[0] == "my card was charged twice for the same order last week"
    assert "T07" in str(leaks[0])


def test_find_leaks_ignores_unrelated_and_short_overlaps() -> None:
    assert find_leaks("Answer politely and in English.", ["Answer the question about refunds."]) == []
    short = find_leaks("the export button", ["The export button does nothing"], n=3)
    assert short[0].item == 0 and short[0].longest == 3
    with pytest.raises(ValueError):
        find_leaks("x", ["x"], n=0)


def test_interval_is_a_plain_value_object() -> None:
    interval = Interval(0.5, 0.4, 0.6, method="test", n=3)
    assert interval.width == pytest.approx(0.2)
    assert str(interval) == "0.500 [0.400, 0.600] (test, n=3)"
