"""Turning proposed time blocks into ones that actually fit the day.

Claude proposes a start time and a duration per task. It is not asked to
avoid collisions, because a model asked to do arithmetic over a list of
meetings will occasionally get it wrong and write a block on top of a real
one. So the proposal is treated as a preference and this module decides:
clamp into the workday window, then drop anything that would sit on top of
a real event or an earlier accepted block.

Dropping beats shifting. Moving a block to the next free gap looks helpful
but silently rewrites the plan the owner just described, and this module has
no idea whether 3pm mattered. A task without a block still appears on the
list; it just does not claim time.
"""

import datetime as dt
from dataclasses import dataclass

from app.core.timeutil import USER_TIMEZONE
from app.services.calendar import CalendarEvent

MIN_BLOCK_MINUTES = 15
MAX_BLOCK_MINUTES = 240


@dataclass(frozen=True)
class BlockProposal:
    task_index: int
    start: dt.time
    minutes: int


@dataclass(frozen=True)
class Block:
    task_index: int
    start: dt.datetime
    minutes: int

    @property
    def end(self) -> dt.datetime:
        return self.start + dt.timedelta(minutes=self.minutes)


def _overlaps(
    start: dt.datetime, end: dt.datetime, other_start: dt.datetime, other_end: dt.datetime
) -> bool:
    """Half-open comparison: a block may start exactly when another ends."""
    return start < other_end and other_start < end


def schedule_blocks(
    proposals: list[BlockProposal],
    events: list[CalendarEvent],
    day: dt.date,
    workday_start: dt.time,
    workday_end: dt.time,
) -> list[Block]:
    """Accept the proposals that fit, in the order they were proposed.

    Order is priority order, so when two blocks collide the higher priority
    task keeps its slot and the lower one loses its block.
    """
    window_start = dt.datetime.combine(day, workday_start, tzinfo=USER_TIMEZONE)
    window_end = dt.datetime.combine(day, workday_end, tzinfo=USER_TIMEZONE)
    if window_end <= window_start:
        return []

    busy = [(event.start, event.end) for event in events if event.blocks_time]
    accepted: list[Block] = []

    for proposal in proposals:
        minutes = max(MIN_BLOCK_MINUTES, min(proposal.minutes, MAX_BLOCK_MINUTES))
        start = dt.datetime.combine(day, proposal.start, tzinfo=USER_TIMEZONE)

        # Clamp into the workday: pull an early start forward, and trim an
        # overrun rather than letting the block spill past the window.
        start = max(start, window_start)
        end = min(start + dt.timedelta(minutes=minutes), window_end)
        minutes = int((end - start).total_seconds() // 60)
        if minutes < MIN_BLOCK_MINUTES:
            continue

        taken = busy + [(block.start, block.end) for block in accepted]
        if any(_overlaps(start, end, other_start, other_end) for other_start, other_end in taken):
            continue

        accepted.append(Block(task_index=proposal.task_index, start=start, minutes=minutes))

    return accepted
