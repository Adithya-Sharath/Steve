## What and why

<!-- One or two sentences. Link the issue if there is one. -->

## Checklist

- [ ] Tests added or updated (engine changes always need one)
- [ ] `ruff check engine api eval`, engine and API `pytest`, and (for web changes) `npm run lint`, `npx tsc --noEmit`, `npm run build` pass
- [ ] No new false "understood": rules only move results away from `understood` unless a test proves otherwise
- [ ] If the engine changed: `make eval` re-run, `python eval/update_readme.py` run, and a `DECISIONS.md` entry added
- [ ] No keys, `.env` files or personal data included
