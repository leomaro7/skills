# Remediation reference

Detailed guidance for handling findings after the human review. Read this when
deciding *how* to fix each category, especially for real secrets.

## Table of contents
- [Decision matrix per category](#decision-matrix-per-category)
- [Real secrets: rotation is mandatory](#real-secrets-rotation-is-mandatory)
- [If the secret is already committed locally](#if-the-secret-is-already-committed-locally)
- [Replacement conventions](#replacement-conventions)
- [Tuning false positives](#tuning-false-positives)
- [Installing gitleaks (optional)](#installing-gitleaks-optional)

## Decision matrix per category

| Category | Default action after approval |
|---|---|
| `SECRET` (real credential) | Remove value, replace with env-var reference or placeholder, **and rotate the credential**. See below. |
| `SECRET` (false positive, e.g. sample value) | Mark as accepted, no change. Consider tightening the value or adding a placeholder form. |
| `PII` (email/phone/IP/card) | Replace with a generic placeholder (`user@example.com`, `000-0000-0000`, `203.0.113.10`, `4111...`). For test fixtures, prefer reserved/documentation ranges. |
| `NAME` (glossary or LLM-suggested) | Replace with the glossary `REPLACEMENT`, or a neutral generic chosen with the human. Add newly confirmed names to `.scrub-glossary`. |

## Real secrets: rotation is mandatory

Text-replacing a leaked credential does **not** make it safe — anyone who saw it
(including earlier local commits, terminal history, backups) can still use it.

When a real secret is confirmed, tell the human explicitly:

1. **Rotate/revoke** the credential at its source (cloud console, token settings).
2. Replace the value in the file with an environment-variable reference
   (`API_KEY=${API_KEY}`) or a documented placeholder.
3. Move the real value to a secret store / `.env` file that is git-ignored.
4. Verify `.gitignore` covers the secret-bearing file.

Do not proceed to commit until the human confirms rotation is done or
consciously deferred.

## If the secret is already committed locally

The scanner runs **before** `git add`, so the goal is to never let the secret
enter a commit. But if earlier local commits (not yet pushed) already contain
it, text replacement leaves it in history. Options, in order of preference:

- If commits are **not pushed**: rewrite local history (`git rebase`, or
  `git reset --soft` back to before the leak and recommit cleanly).
- Regardless: **rotate the secret** — history rewriting alone is not enough.
- If already pushed: rotate immediately; treat as a disclosed secret.

History rewriting is destructive — always confirm with the human and never
force-push without explicit approval.

## Replacement conventions

Prefer well-known reserved/documentation values so fixtures stay realistic but
safe:

- Email: `user@example.com` (RFC 2606 reserved domain)
- IPv4: `192.0.2.x`, `198.51.100.x`, `203.0.113.x` (RFC 5737 doc ranges)
- Phone (JP): `03-0000-0000`; (US/intl) `+1-555-0100`
- Credit card: `4111 1111 1111 1111` is a known test number (acceptable in tests)
- Secrets in config: `${VAR_NAME}` env reference

## Tuning false positives

The scanner errs toward over-reporting so the human review can reject noise.

- **Placeholder values** (`xxxx`, `<token>`, `${VAR}`, `changeme`, `example`)
  are already filtered for the generic `key = value` rule.
- The **phone** and **IP** detectors are the noisiest. If a repo has many
  version numbers or IDs that look like phone numbers, expect false positives;
  reject them in review rather than weakening the pattern globally.
- To stop a recurring legitimate string from being flagged, the cleanest fix is
  to make the value an obvious placeholder, not to disable the rule.

## Installing gitleaks (optional)

The scanner works without gitleaks (regex fallback). Installing it improves
secret coverage. Cross-platform install:

- macOS: `brew install gitleaks`
- Windows: `winget install gitleaks` or `choco install gitleaks`
- Any OS: download a release binary from the gitleaks GitHub releases page and
  put it on `PATH`.

The scanner auto-detects gitleaks on `PATH`; no configuration needed.
