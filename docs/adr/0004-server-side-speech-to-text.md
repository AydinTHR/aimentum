# 4. Server-side Google Speech-to-Text over the browser Web Speech API

- Status: accepted
- Date: 2026-07-18

## Context

Morning planning is voice-first: the owner taps a mic, talks, and the words become the
day's plan. The browser's built-in Web Speech API looks like the easy path, but its
recognition support is unreliable in installed iOS PWAs, which is precisely where this
app lives. A voice feature that fails on the one device that matters is worse than no
voice feature. Separately, iOS Safari's MediaRecorder produces `audio/mp4` (AAC), a
container Google's Speech-to-Text does not reliably accept.

## Decision

We will capture audio in the browser with MediaRecorder and transcribe it server-side
with Google Cloud Speech-to-Text (v2, short-form recognition), staying within the free
monthly transcription minutes. The provider sits behind a `SpeechToText` Protocol so it
is swappable in one class, with a fake implementation for tests. Before transcription,
the backend transcodes any uploaded container to FLAC 16 kHz mono with ffmpeg.
Consequently the backend deploys to Render as a Docker image with ffmpeg installed.
Language codes come from env so additional languages can sit alongside English later.
Transcription is a separate step from planning: the transcript comes back to the UI for
a human confirm-or-edit before it becomes the day's plan.

## Consequences

- Voice input works in the installed iOS PWA, the environment that actually matters.
- The backend takes on an ffmpeg dependency and a Docker deploy, which is more setup
  than a plain buildpack but makes the transcode reliable and reproducible.
- Server-side STT costs nothing within Google's free tier but requires a Google Cloud
  project and a service account, a one-time manual setup.
- The Protocol boundary means a future provider swap (or an on-device model) touches
  one class and its tests, nothing else.
