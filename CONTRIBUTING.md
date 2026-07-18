# Contributing to Aimentum

Thanks for taking the time to contribute.

## Getting set up

```bash
git clone https://github.com/AydinTHR/aimentum.git
cd aimentum
pre-commit run --all-files   # optional: run the formatters and linters locally
```

## Workflow

1. Create a short-lived branch off `main`, named for the change
   (for example `feat/booking-form` or `fix/empty-payload`).
2. Make focused, atomic commits. Keep each commit to one logical change.
3. Open a pull request. CI runs lint, type checks, and tests, and must pass.
4. Self-review your own diff before asking for a merge. Squash and merge when green.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org). The type prefix
drives the changelog and the version bump.

- `feat:` a new feature (minor version bump)
- `fix:` a bug fix (patch version bump)
- `docs:`, `refactor:`, `test:`, `chore:`, `ci:`, `perf:`, `build:` for the rest
- A `!` after the type, or a `BREAKING CHANGE:` footer, marks a breaking change (major bump)

Subjects are short and in the imperative mood, for example
`feat(auth): add token refresh`.

## Code style

Formatting and linting are handled by the tools configured in this repo, so you do not
need to format by hand. Run `pre-commit run --all-files` to check everything at once, or
let CI do it on your pull request.
