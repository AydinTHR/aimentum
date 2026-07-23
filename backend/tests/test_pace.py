"""Pace math specification.

Pace compares the fraction of the target reached against the fraction of the
period elapsed. The band is 10 percentage points on either side and the band
edges count as on track. Days elapse inclusively: on the first day of a 31 day
period, 1/31 has elapsed. A pace only exists where an honest one can: with a
positive target and a valid period.
"""

from datetime import date
from decimal import Decimal

from app.services.progress import Pace, compute_pace, month_bounds

JULY_START = date(2026, 7, 1)
JULY_END = date(2026, 7, 31)


def pace(
    target: float | None,
    current: float,
    start: date | None = JULY_START,
    end: date | None = JULY_END,
    today: date = date(2026, 7, 15),
) -> Pace | None:
    decimal_target = None if target is None else Decimal(str(target))
    return compute_pace(decimal_target, Decimal(str(current)), start, end, today)


class TestNoHonestPace:
    def test_no_target_means_no_pace(self) -> None:
        assert pace(None, 10) is None

    def test_zero_target_means_no_pace(self) -> None:
        assert pace(0, 10) is None

    def test_missing_period_means_no_pace(self) -> None:
        assert pace(40, 10, start=None, end=None) is None
        assert pace(40, 10, start=JULY_START, end=None) is None
        assert pace(40, 10, start=None, end=JULY_END) is None

    def test_inverted_period_means_no_pace(self) -> None:
        assert pace(40, 10, start=JULY_END, end=JULY_START) is None


class TestExpectedValue:
    def test_expected_scales_with_elapsed_days(self) -> None:
        result = pace(40, 23, today=date(2026, 7, 20))
        assert result is not None
        assert result.expected == round(40 * 20 / 31, 2)

    def test_first_day_of_month_counts_as_one_elapsed_day(self) -> None:
        result = pace(40, 0, today=JULY_START)
        assert result is not None
        assert result.expected == round(40 * 1 / 31, 2)

    def test_last_day_of_month_expects_the_full_target(self) -> None:
        result = pace(40, 40, today=JULY_END)
        assert result is not None
        assert result.expected == 40.0

    def test_single_day_period_expects_everything_on_that_day(self) -> None:
        day = date(2026, 7, 10)
        result = pace(5, 0, start=day, end=day, today=day)
        assert result is not None
        assert result.expected == 5.0


class TestPeriodBoundaries:
    def test_before_the_period_nothing_is_expected(self) -> None:
        result = pace(40, 0, today=date(2026, 6, 30))
        assert result is not None
        assert result.expected == 0.0
        assert result.status == "on_track"

    def test_before_the_period_progress_beyond_the_band_is_ahead(self) -> None:
        result = pace(40, 15, today=date(2026, 6, 30))
        assert result is not None
        assert result.status == "ahead"

    def test_after_the_period_the_full_target_is_expected(self) -> None:
        result = pace(40, 40, today=date(2026, 8, 5))
        assert result is not None
        assert result.expected == 40.0
        assert result.status == "on_track"

    def test_after_the_period_a_shortfall_is_behind(self) -> None:
        result = pace(40, 20, today=date(2026, 8, 5))
        assert result is not None
        assert result.status == "behind"


class TestTenPercentBand:
    """Halfway through a 10 day period with target 100, expected is exactly 50."""

    START = date(2026, 1, 1)
    END = date(2026, 1, 10)
    TODAY = date(2026, 1, 5)

    def band_pace(self, current: float) -> Pace:
        result = pace(100, current, start=self.START, end=self.END, today=self.TODAY)
        assert result is not None
        assert result.expected == 50.0
        return result

    def test_at_expected_is_on_track(self) -> None:
        assert self.band_pace(50).status == "on_track"

    def test_upper_band_edge_is_on_track(self) -> None:
        assert self.band_pace(60).status == "on_track"

    def test_just_above_the_band_is_ahead(self) -> None:
        assert self.band_pace(61).status == "ahead"

    def test_lower_band_edge_is_on_track(self) -> None:
        assert self.band_pace(40).status == "on_track"

    def test_just_below_the_band_is_behind(self) -> None:
        assert self.band_pace(39).status == "behind"

    def test_zero_progress_at_halfway_is_behind(self) -> None:
        assert self.band_pace(0).status == "behind"

    def test_double_expected_is_ahead(self) -> None:
        assert self.band_pace(100).status == "ahead"


class TestEarlyMonthIsNotPunished:
    def test_zero_progress_on_day_one_is_on_track(self) -> None:
        result = pace(40, 0, today=JULY_START)
        assert result is not None
        assert result.status == "on_track"

    def test_zero_progress_on_day_four_is_behind(self) -> None:
        # By July 4th, 4/31 (about 12.9 percent) has elapsed: outside the band.
        result = pace(40, 0, today=date(2026, 7, 4))
        assert result is not None
        assert result.status == "behind"


class TestMonthBounds:
    def test_mid_month(self) -> None:
        assert month_bounds(date(2026, 7, 23)) == (date(2026, 7, 1), date(2026, 7, 31))

    def test_february_leap_year(self) -> None:
        assert month_bounds(date(2024, 2, 10)) == (date(2024, 2, 1), date(2024, 2, 29))

    def test_february_regular_year(self) -> None:
        assert month_bounds(date(2026, 2, 1)) == (date(2026, 2, 1), date(2026, 2, 28))

    def test_december_wraps_the_year(self) -> None:
        assert month_bounds(date(2026, 12, 31)) == (date(2026, 12, 1), date(2026, 12, 31))
