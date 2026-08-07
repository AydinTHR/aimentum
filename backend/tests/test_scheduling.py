"""Block scheduling specification.

Claude proposes times; this module decides. Proposals are clamped into the
workday window, and anything that would land on a real event or an earlier
accepted block is dropped rather than moved.
"""

import datetime as dt

from app.core.timeutil import USER_TIMEZONE
from app.services.calendar import CalendarEvent
from app.services.scheduling import BlockProposal, schedule_blocks

DAY = dt.date(2026, 8, 10)
WORKDAY_START = dt.time(9, 0)
WORKDAY_END = dt.time(18, 0)


def at(hour: int, minute: int = 0) -> dt.datetime:
    return dt.datetime(DAY.year, DAY.month, DAY.day, hour, minute, tzinfo=USER_TIMEZONE)


def event(start_hour: float, end_hour: float, all_day: bool = False) -> CalendarEvent:
    return CalendarEvent(
        id="e",
        summary="Standup",
        start=at(int(start_hour), int((start_hour % 1) * 60)),
        end=at(int(end_hour), int((end_hour % 1) * 60)),
        all_day=all_day,
    )


def run(
    proposals: list[BlockProposal], events: list[CalendarEvent] | None = None
) -> list[tuple[int, str, int]]:
    blocks = schedule_blocks(proposals, events or [], DAY, WORKDAY_START, WORKDAY_END)
    return [(b.task_index, b.start.strftime("%H:%M"), b.minutes) for b in blocks]


class TestAcceptance:
    def test_a_clear_proposal_is_kept_as_is(self) -> None:
        assert run([BlockProposal(0, dt.time(10, 0), 60)]) == [(0, "10:00", 60)]

    def test_several_non_overlapping_blocks_all_survive(self) -> None:
        proposals = [
            BlockProposal(0, dt.time(9, 0), 60),
            BlockProposal(1, dt.time(10, 0), 30),
            BlockProposal(2, dt.time(14, 0), 90),
        ]
        assert run(proposals) == [(0, "09:00", 60), (1, "10:00", 30), (2, "14:00", 90)]

    def test_a_block_may_start_exactly_when_an_event_ends(self) -> None:
        assert run([BlockProposal(0, dt.time(10, 0), 60)], [event(9, 10)]) == [(0, "10:00", 60)]


class TestWorkdayClamping:
    def test_an_early_start_is_pulled_to_the_window(self) -> None:
        assert run([BlockProposal(0, dt.time(7, 0), 60)]) == [(0, "09:00", 60)]

    def test_an_overrun_is_trimmed_at_the_window_end(self) -> None:
        assert run([BlockProposal(0, dt.time(17, 30), 120)]) == [(0, "17:30", 30)]

    def test_a_block_starting_after_the_window_is_dropped(self) -> None:
        assert run([BlockProposal(0, dt.time(19, 0), 60)]) == []

    def test_a_block_trimmed_below_the_minimum_is_dropped(self) -> None:
        assert run([BlockProposal(0, dt.time(17, 55), 60)]) == []

    def test_an_inverted_workday_schedules_nothing(self) -> None:
        blocks = schedule_blocks(
            [BlockProposal(0, dt.time(10, 0), 60)], [], DAY, dt.time(18, 0), dt.time(9, 0)
        )
        assert blocks == []


class TestOverlapRejection:
    def test_a_block_over_a_meeting_is_dropped(self) -> None:
        assert run([BlockProposal(0, dt.time(10, 0), 60)], [event(10, 11)]) == []

    def test_a_block_partially_over_a_meeting_is_dropped(self) -> None:
        assert run([BlockProposal(0, dt.time(10, 30), 60)], [event(10, 11)]) == []

    def test_a_block_containing_a_meeting_is_dropped(self) -> None:
        assert run([BlockProposal(0, dt.time(9, 0), 180)], [event(10, 11)]) == []

    def test_the_higher_priority_task_keeps_the_slot(self) -> None:
        """Proposals arrive in priority order, so the first one wins."""
        proposals = [
            BlockProposal(0, dt.time(10, 0), 60),
            BlockProposal(1, dt.time(10, 30), 60),
        ]
        assert run(proposals) == [(0, "10:00", 60)]

    def test_a_later_task_can_still_take_a_free_slot(self) -> None:
        proposals = [
            BlockProposal(0, dt.time(10, 0), 60),
            BlockProposal(1, dt.time(10, 30), 60),
            BlockProposal(2, dt.time(13, 0), 45),
        ]
        assert run(proposals) == [(0, "10:00", 60), (2, "13:00", 45)]

    def test_all_day_events_do_not_reserve_time(self) -> None:
        """A birthday should not stop the day being planned."""
        birthday = CalendarEvent(
            id="b", summary="Birthday", start=at(0), end=at(23, 59), all_day=True
        )
        assert run([BlockProposal(0, dt.time(10, 0), 60)], [birthday]) == [(0, "10:00", 60)]


class TestDurationBounds:
    def test_a_tiny_duration_is_raised_to_the_minimum(self) -> None:
        assert run([BlockProposal(0, dt.time(10, 0), 5)]) == [(0, "10:00", 15)]

    def test_an_absurd_duration_is_capped(self) -> None:
        assert run([BlockProposal(0, dt.time(9, 0), 600)]) == [(0, "09:00", 240)]
