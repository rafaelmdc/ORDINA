<!-- Keep the title in the repo's commit style: imperative, capitalized, no trailing period.
     e.g. "Add PhylogenyLayer via braidworks.fetch" -->

## Summary

<!-- What this PR does and why. Link the design doc / decision it implements
     (e.g. doc 10 Slice 1, decision B5) so reviewers can check intent, not just code. -->

## Scope

- **Module:** <!-- core / retes / mind / flux / web / docs / infra -->
- **Slice / phase:** <!-- e.g. Slice 1, or N/A for docs-only -->

## How it was verified

<!-- Commands run and what you observed. Not "tests pass" — say which and the result.
     For runtime changes, describe the end-to-end behaviour you drove. -->

## Checklist

- [ ] `uv run ruff check .` and `uv run ruff format --check .` clean
- [ ] `uv run mypy packages/core/ordina_core packages/retes/ordina_retes` clean
- [ ] `uv run pytest` green
- [ ] Boundary rule respected: `ordina-core` and `ordina-retes` import **no Django** (doc 10 A.1/A.9)
- [ ] Docs updated if a decision or contract changed (docs/ + the relevant change log)

## Related issues

<!-- Closes #… -->
