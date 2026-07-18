# 5. Integrate Google Calendar rather than building calendar UI

- Status: accepted
- Date: 2026-07-18

## Context

Useful prioritization needs the real calendar: a day full of meetings should produce a
different plan than an empty one, and the day's top tasks are more likely to happen if
they hold real time slots. Building calendar UI (month grids, drag and drop, recurring
events, invites) is an enormous scope sink that has nothing to do with accountability,
and Google's own apps already do it better than a v1 ever could.

## Decision

We will integrate Google Calendar through its API and build no calendar UI. The agent
reads today's events across the owner's calendars to prioritize around them, and writes
the day's top tasks into a dedicated "Aimentum" calendar as time blocks, storing event
ids so task edits and re-plans update or delete their events. Overlap validation and
workday clamping happen in code, never in the prompt. The integration sits behind a
`CalendarService` Protocol (future swap target: CalDAV for Apple Calendar) with a
`GoogleCalendarService` implementation and a fake for tests. Auth is a one-time OAuth
authorization of the owner's own Google account via a local helper script, with the
refresh token in env; the OAuth consent screen must be in production status so refresh
tokens do not expire weekly. If Calendar is unreachable, morning planning still works
without events and says so in its rationale.

## Consequences

- Google's apps provide the full calendar experience for free; this app only reads and
  writes what it owns.
- Scope stays lean: no month, week, or day grids, no drag and drop, no recurring-event
  engine, ever, in v1.
- The one-time OAuth flow is a manual setup step for the owner, and losing the refresh
  token means re-running it.
- The Protocol boundary keeps a future Apple Calendar (CalDAV) swap to one class.
