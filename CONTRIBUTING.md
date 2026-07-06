# Contributing to ORDINA

ORDINA is a **docs-first research project** with a small, growing code workspace. Read the
blueprint in [`docs/`](docs/) before proposing code — the vision, network model, layer catalog,
and roadmap live there, and most "why is it done this way" questions are answered by a numbered
doc or a resolved decision in [`docs/08_decisions.md`](docs/08_decisions.md).

## Local development

The code is a [`uv`](https://docs.astral.sh/uv/) workspace under [`packages/`](packages/)
(see [`packages/README.md`](packages/README.md)). Requires Python ≥ 3.12.

```bash
uv sync                      # install workspace + dev tools
uv run pytest                # tests
uv run ruff check .          # lint
uv run ruff format .         # format (use --check in CI)
uv run mypy packages/core/ordina_core packages/retes/ordina_retes   # types
```

These four gates — **ruff lint, ruff format, mypy, pytest** — are exactly what CI runs
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)). Run them before pushing.

### The one architectural rule

`ordina-core` and `ordina-retes` import **no Django and no web framework** (doc 10 A.1/A.9).
Business rules live once, in framework-free packages, so the CLI, the offline pipeline, the
workers, and the web API all share the same objects. Only `ordina-mind` / `ordina-flux` may
import Django. A test enforces the core boundary; don't work around it.

## Branching

- `main` is the default branch and should always be green. Don't commit to it directly; open a PR.
- Work on a **short-lived topic branch** named `<type>/<slug>`, kebab-case:
  - `type` ∈ `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`.
  - For roadmap work, scope by slice: `feat/slice-1-phylogeny`, `feat/slice-2-gate`.
  - Examples: `docs/layer-catalog-pruning`, `fix/universe-version-hash`, `ci/add-mypy`.
- One logical change per branch. Rebase on `main` to stay current; keep the branch focused.

## Commits

### When to commit — one logical change per commit

Aim for **relevant, self-contained commits**: not one giant "did a bunch of stuff" commit, and
not a dribble of "wip", "fix typo", "oops" commits. The unit is **one logical change** — the
smallest thing that stands on its own and leaves the tree working.

- **Commit when** a coherent step is done: a feature/fix/refactor complete, its tests updated,
  the gates green. That's the moment — not every file save, and not only at end of day.
- **One concern per commit.** Don't mix a refactor with a feature, or a formatting sweep with a
  logic change. If a diff needs the word "and" to describe it, it's probably two commits
  (e.g. the earlier split of "format test files" from "add GitHub ops").
- **Don't commit broken states** on a branch you'll PR. Each commit should build and pass the
  gates on its own where practical (so `git bisect` and review-by-commit stay useful).
- **Too big** (touches many unrelated areas, hard to review, one line summarises nothing) →
  split it. **Too small** (can't be described without referring to the next commit) → squash it.
- Use staging deliberately — `git add <paths>` (or `-p`) to commit exactly one concern even when
  the working tree has several in flight. Squash/fixup local WIP before opening the PR.

Rule of thumb: a reviewer should understand each commit from its message + diff alone, and
reverting one commit should undo exactly one intelligible change.

### Message style

Match the style already in the history — **descriptive, imperative-mood subjects**, not
Conventional Commits (no `feat:` / `fix:` prefixes).

- **Subject:** imperative, capitalized, no trailing period, ≤ 72 chars.
  Say *what changes*, and where useful *which doc/slice* it serves.
  - Good: `Add PhylogenyLayer via braidworks.fetch`, `Harden blueprint from adversarial review`.
  - Avoid: `updates`, `fix stuff`, `WIP`.
- **Body (when the change isn't self-evident):** a blank line, then *why* and any consequence a
  reviewer needs. Reference docs/decisions (`doc 10 Slice 1`, `decision B5`) and issues (`Closes #12`).
- Keep commits coherent — each should build and pass the gates on its own where practical.
- Co-authorship / attribution trailers (e.g. `Co-Authored-By:`) go at the end of the body.

## Pull requests

- Fill in the [PR template](.github/pull_request_template.md): summary, module + slice, how you
  verified it, and the checklist.
- CI must be green (the four gates above).
- Update the relevant doc **and its change log** whenever a decision or a contract changes —
  the docs are the source of truth for intent.

## Issues

Use the [issue forms](.github/ISSUE_TEMPLATE/): **Bug report** for code defects,
**Feature / research proposal** for capabilities or blueprint changes, and **New layer proposal**
for a new enrichment layer (it asks for the `LayerFactory` contract fields up front).
