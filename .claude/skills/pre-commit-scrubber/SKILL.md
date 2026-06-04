---
name: pre-commit-scrubber
description: >-
  Scan pending changes for secrets/credentials, PII, and organization- or
  project-specific names BEFORE committing, then apply human-approved fixes and
  commit cleanly. Use whenever the user asks to commit, check in, or push code
  to GitHub/GitLab — especially for reusable artifacts shared across projects —
  or asks to "check for secrets/PII/leaks" or "scrub" files before committing.
  Runs before `git add` so secrets never enter git history. Cross-platform
  (macOS/Windows), human-in-the-loop required before any fix.
---

# Pre-commit Scrubber

Gate commits of shared artifacts so they never leak secrets, PII, or
org/project-specific names. The flow is **detect → human review → fix → add →
commit** (one commit), and it runs **before `git add`** so nothing sensitive
enters git history.

## When this runs

Trigger when the user is about to commit/push, or explicitly asks to scrub or
check for secrets/PII/leaks. Run the scan **before staging** the changes.

## Workflow

### 1. Detect (read-only)

Run the scanner against the repository. It works on macOS and Windows and uses
only the Python standard library. Use `python3` (fall back to `python` on
Windows if `python3` is unavailable):

```
python3 scripts/scan.py --repo <repo-path>
```

The scanner:
- inspects **uncommitted changes** (modified + untracked eligible files) vs
  `HEAD`, before staging;
- detects **SECRET** (gitleaks if installed, else built-in regex), **PII**
  (email/phone/IP/credit-card with Luhn check), and **NAME** (terms in
  `<repo>/.scrub-glossary`);
- **never edits files** — it only reports, so the human stays in control.

Add `--format json` when you need structured output to drive edits. Exit code is
`1` when there are findings, `0` when clean.

If `.scrub-glossary` does not exist, copy `assets/scrub-glossary.template` to the
repo root, help the user fill in their client/project/internal names, then
re-run. The glossary only catches **registered** terms; unregistered names are
covered by the manual NAME pass in step 1b.

### 1b. Manual NAME pass (mandatory — also covers files the scanner cleared)

The scanner's "clean"/zero-findings result is only reliable for **SECRET** and
**PII**, which are matched by deterministic regex. For **NAME** it sees *only*
terms registered in `.scrub-glossary`, so a file the scanner reported with **no
findings can still contain an unregistered org/project-specific name**. This is a
structural blind spot, not an edge case.

Therefore, **regardless of scanner output**, read through **every** changed file
yourself — including the ones the scanner cleared — and look for unregistered
names: client/customer names, internal project or product codenames, team or
system names, internal hostnames, repo names, ticket prefixes. Get the full list
of changed files from the scanner's `--format json` output (`scanned_files`) or
from `git status --porcelain`.

Treat anything you find as a candidate **NAME** finding, carry it into the human
review below alongside the scanner's findings, and add each confirmed name to
`.scrub-glossary` so future runs catch it automatically. Do **not** skip this
pass just because the scanner returned no findings — that is precisely the case
it cannot cover.

### 2. Human review (mandatory checkpoint)

Never auto-fix. Present findings grouped by file and category, and for each ask
the human to choose: **fix** (and with what replacement), **reject** (false
positive), or **defer**. Make the secret risk explicit:

> A real credential cannot be made safe by text replacement alone — it must be
> rotated/revoked at its source.

Surface false-positive-prone items (phone, IP) clearly so they can be rejected
quickly.

### 3. Apply approved fixes

Apply only what the human approved, using the `Edit` tool:
- **NAME**: replace with the glossary `REPLACEMENT`, or a neutral generic agreed
  with the human. Add newly confirmed names to `.scrub-glossary`.
- **PII**: replace with reserved/documentation placeholders.
- **SECRET**: replace the value with an env-var reference or placeholder, move
  the real value to a git-ignored `.env`/secret store, and **tell the user to
  rotate the credential**.

For replacement conventions, history-rewrite cautions, and the full secret
remediation procedure, read `references/remediation.md`.

### 4. Re-scan, then add and commit

Re-run `scripts/scan.py` to confirm approved findings are gone. When clean (or
only rejected false positives remain), stage and commit in one step:

```
git add <files>
git commit -m "<type>: <summary>"
```

Because fixes were made before staging, this produces a single clean commit.

**Commit message convention (Conventional Commits):** Start the subject with a
type, then a concise imperative summary: `<type>: <summary>`. Allowed types:
`feat` (new feature/artifact), `fix`, `docs`, `refactor`, `chore`, `test`,
`build`, `ci`, `perf`, `style`. Do **not** use `add:` — use `feat:`. Example:
`feat: add reusable error-handling helper`. Keep the summary short (~50 chars)
and in the imperative mood. Do not add a `Co-Authored-By` trailer here — the
environment appends one automatically when required; avoid duplicating it.

## Important constraints

- **Run before `git add`**, not before push — fixing after a local commit leaves
  secrets in history.
- **Human approval is required before any edit.** This skill detects
  automatically but never redacts automatically.
- **Real secrets require rotation**, not just replacement. Do not let the commit
  proceed until the user confirms rotation is done or consciously deferred.
- **Cross-platform**: invoke the scanner via Python (`python3`/`python`); do not
  rely on `grep`/`sed`/bash. gitleaks is optional and auto-detected.
