# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0](https://github.com/AydinTHR/aimentum/compare/v0.1.0...v0.2.0) (2026-08-28)


### Added

* add fastapi skeleton with health route ([bd431d6](https://github.com/AydinTHR/aimentum/commit/bd431d625653da92da6540ca4b72e7c007a42881))
* **agent:** add anthropic client wrapper and versioned prompts ([c3ad20c](https://github.com/AydinTHR/aimentum/commit/c3ad20ce6a621d4599a44f49e2c2af9511bacced))
* **agent:** add morning planning, evening reflection, and weekly retro ([ed1cdf9](https://github.com/AydinTHR/aimentum/commit/ed1cdf9e8db5903fd997909b0d863efbca27f7a7))
* **agent:** add speech to text protocol with ffmpeg transcode ([24ed51f](https://github.com/AydinTHR/aimentum/commit/24ed51f383cd9ff0c6769dabab06abb7f01cdf0d))
* **api:** add cors and serve the vapid public key ([5ccba9f](https://github.com/AydinTHR/aimentum/commit/5ccba9fefe4c5248df2635ad39458dda9e903217))
* **api:** add goals, progress, today, tasks, and settings endpoints ([4f12820](https://github.com/AydinTHR/aimentum/commit/4f12820b4fc64fce98e96397210306aa7c34c828))
* **api:** add progress service with pace math ([36265c9](https://github.com/AydinTHR/aimentum/commit/36265c975b5e7e8c283f619060f9267a58c8aa8b))
* **api:** require the shared bearer token on every request ([2121a3c](https://github.com/AydinTHR/aimentum/commit/2121a3c3234a97c4eb7d09a18cb212191c762f11))
* **calendar:** add calendar service protocol and block scheduling ([dda7400](https://github.com/AydinTHR/aimentum/commit/dda74009f2baca5293987bf9d947a6cf9feb417f))
* **calendar:** add oauth helper scripts and calendar tests ([956a2ee](https://github.com/AydinTHR/aimentum/commit/956a2eecbe1c8ff6612329c38269d97e94398bf0))
* **calendar:** feed events into planning and write time blocks ([00dfc53](https://github.com/AydinTHR/aimentum/commit/00dfc535e1430af676d36197d2def485e6192626))
* **db:** add data model, engine plumbing, and alembic baseline ([fb28fd6](https://github.com/AydinTHR/aimentum/commit/fb28fd61bcb2d6578a57b9e1b548a7be7c45a9d1))
* **db:** keep push log history when subscriptions are pruned ([b633362](https://github.com/AydinTHR/aimentum/commit/b633362e16439ecd111174f015b23a54affe1628))
* **push:** add subscribe, unsubscribe, and test endpoints ([859af86](https://github.com/AydinTHR/aimentum/commit/859af86abd06fa6768ce9d8d62dd0428ae5f72e7))
* **push:** add web push sender with logging and pruning ([deecd8a](https://github.com/AydinTHR/aimentum/commit/deecd8a6ae5bb31f0ea0a76a477b12c900ae12a0))
* **pwa:** build the installable app ([97545bb](https://github.com/AydinTHR/aimentum/commit/97545bbf6c22b4d95611efe5e8bc415a508b614c))
* scaffold react frontend shell with vite and tailwind ([f0ef62f](https://github.com/AydinTHR/aimentum/commit/f0ef62f283ab62b20bc937ea9d92b161a80a6c0c))
* **tick:** add the four scheduled jobs with idempotent claiming ([4f3b7d9](https://github.com/AydinTHR/aimentum/commit/4f3b7d909abf6f125ff1a5140840ea9d19c7722d))


### Fixed

* **agent:** degrade instead of returning a raw 500 ([2d8dce0](https://github.com/AydinTHR/aimentum/commit/2d8dce09827d3a5a4b2ef79d8cfa81d28e3b81f9))
* **calendar:** make setup scripts runnable as documented ([73ee53b](https://github.com/AydinTHR/aimentum/commit/73ee53b4302842853fad25852311e4d33aa7fb50))
* **pwa:** render times in the owner's timezone, not the device's ([36e7d9f](https://github.com/AydinTHR/aimentum/commit/36e7d9f80097e82d2a3afca6343c6c5e5da1a039))

## [Unreleased]

### Added

- Initial project scaffold.
