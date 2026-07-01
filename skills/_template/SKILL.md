---
name: skill-name
description: Replace this. State what the skill does and WHEN Claude should use it,
  including the phrases a user would type ("release vX.Y.Z", "submit this to Slurm").
  This text is the only thing Claude reads before deciding to load the skill — make
  it specific and trigger-oriented, not a vague summary.
---

# skill-name — short human title

One-paragraph overview: what problem this automates and the outcome the user gets.

## Preconditions

List what must be true before starting. Prefer checks that fail loudly:

- Tool X installed and on `PATH` (`x --version` returns 0)
- Auth/session live (say exactly how the user renews it if not)
- Correct working directory / branch / cluster

## Workflow

Numbered, copy-pasteable steps. Mark anything destructive.

### 1. Do the first thing

```bash
# concrete command with <PLACEHOLDERS> for anything environment-specific
echo "replace me"
```

### 2. Do the next thing

Explain any decision points and what to do for each branch.

### 3. Verify

State the observable check that proves success (an exit code, an HTTP 200, a version
string in output). Never claim done without it.

## Common failure modes

- **Symptom** → cause → fix.
- **Symptom** → cause → fix.

## Notes

Anything else: cost, runtime, links to `references/` or `helpers/` in this repo.
Remember this repo is PUBLIC — use placeholders, never real account IDs / secrets / PII.
