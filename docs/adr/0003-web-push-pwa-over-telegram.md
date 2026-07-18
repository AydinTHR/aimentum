# 3. Web push in an installable PWA over a Telegram bot for v1

- Status: accepted
- Date: 2026-07-18

## Context

The agent must reach its owner on an iPhone at specific times. Candidate channels were
a Telegram bot (trivial delivery, but the experience lives inside Telegram), email (too
slow and too easy to ignore for time-of-day nudges), and Web Push to an installed PWA
(native-feeling notifications, no app store, but historically fragile on iOS). Modern
iOS supports Web Push for PWAs added to the home screen, which is exactly how this app
will be used.

## Decision

We will ship v1 as an installable PWA with Web Push: VAPID keys, `pywebpush` on the
server, and a service worker on the client. A native iOS client is deferred to v3, and
the backend stays a clean, client-agnostic JSON API so that client can be added with
zero backend changes. Because Web Push has no delivery receipts, reliability is proven
operationally: every send attempt is logged with its outcome in `push_log`, dead
subscriptions are pruned automatically on 404/410, a test-notification button exists in
Settings from day one, and deployment is not finished until a 48-hour soak shows every
scheduled push arriving on the phone on time.

## Consequences

- The whole experience lives in one app the owner installs once, with no third-party
  chat surface in the loop.
- iOS only allows push for installed PWAs, so the app must detect Safari outside
  standalone mode and walk the owner through Add to Home Screen.
- No delivery receipts means honest verification is a send log plus an on-device soak,
  and the README states that limitation plainly.
- Deferring native iOS keeps v1 small; the API contract is the insurance that v3 does
  not force a rewrite.
