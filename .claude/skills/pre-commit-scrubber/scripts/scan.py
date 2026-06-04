#!/usr/bin/env python3
"""Detect secrets, PII, and organization/project-specific names in pending changes.

Detection-only: this script NEVER edits files. It reports findings so a human can
review them before Claude applies fixes. Works on macOS and Windows (standard
library only; no bash/grep/sed dependency).

Usage:
    python scan.py [--repo PATH] [--glossary PATH] [--format text|json]
                   [--staged] [--no-untracked]

Exit codes:
    0  no findings
    1  findings present (review required)
    2  usage / environment error
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Files we never scan (binary / vendored / lockfiles tend to be noise).
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg",
    ".pdf", ".zip", ".gz", ".tar", ".7z", ".rar", ".jar", ".class",
    ".woff", ".woff2", ".ttf", ".eot", ".otf", ".mp3", ".mp4", ".mov",
    ".so", ".dylib", ".dll", ".exe", ".bin", ".wasm",
}
MAX_BYTES = 2_000_000  # skip files larger than ~2 MB

# Obvious placeholders that should NOT be flagged as real secrets.
PLACEHOLDER_RE = re.compile(
    r"^(?:x+|\*+|\.+|-+|none|null|nil|todo|changeme|example|sample|dummy|test|"
    r"your[_-]?\w+|<[^>]+>|\$\{[^}]+\}|\{\{[^}]+\}\}|%[a-z_]+%|env(?:iron)?\."
    r"\w+)$",
    re.IGNORECASE,
)

# --- Secret patterns (high confidence) ---------------------------------------
SECRET_PATTERNS = [
    ("private-key-block", re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")),
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    ("gitlab-pat", re.compile(r"\bglpat-[A-Za-z0-9\-_]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b")),
    ("stripe-secret-key", re.compile(r"\bsk_live_[0-9A-Za-z]{20,}\b")),
    ("openai-key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
]

# Generic "key = value" assignment of a credential. Value captured to filter placeholders.
ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|"
    r"client[_-]?secret|auth[_-]?token|private[_-]?key|credential)s?\b"
    r"\s*[:=]\s*[\"']?([^\s\"',;]{6,})[\"']?"
)

# --- PII patterns ------------------------------------------------------------
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
# Phone: international or JP-style separated digits (kept conservative).
PHONE_RE = re.compile(r"(?<!\d)(?:\+\d{1,3}[-\s]?)?(?:\(?0\d{1,4}\)?[-\s]?)\d{1,4}[-\s]?\d{3,4}(?!\d)")
CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")


def luhn_ok(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if not 13 <= len(digits) <= 16:
        return False
    checksum, parity = 0, len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def run_git(args: list[str], repo: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except FileNotFoundError:
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def has_head(repo: Path) -> bool:
    return run_git(["rev-parse", "--verify", "HEAD"], repo) is not None


def candidate_files(repo: Path, staged_only: bool, include_untracked: bool,
                    exclude: Path | None = None) -> list[Path]:
    names: set[str] = set()
    base = "--cached" if staged_only else "HEAD"
    if base == "HEAD" and not has_head(repo):
        base = "--cached"
    diff = run_git(["diff", "--name-only", "--diff-filter=ACMR", base], repo)
    if diff:
        names.update(line for line in diff.splitlines() if line.strip())
    if include_untracked and not staged_only:
        others = run_git(["ls-files", "--others", "--exclude-standard"], repo)
        if others:
            names.update(line for line in others.splitlines() if line.strip())
    files = []
    exclude_resolved = exclude.resolve() if exclude else None
    for name in sorted(names):
        p = repo / name
        if exclude_resolved and p.resolve() == exclude_resolved:
            continue  # never scan the glossary file itself
        if p.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            if not p.is_file() or p.stat().st_size > MAX_BYTES:
                continue
        except OSError:
            continue
        files.append(p)
    return files


def load_glossary(path: Path) -> list[tuple[re.Pattern, str, str]]:
    """Each non-comment line: `term` or `term => replacement`."""
    entries = []
    if not path.is_file():
        return entries
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=>" in line:
            term, repl = (s.strip() for s in line.split("=>", 1))
        else:
            term, repl = line, ""
        if not term:
            continue
        entries.append((re.compile(re.escape(term), re.IGNORECASE), term, repl))
    return entries


def gitleaks_findings(repo: Path, changed: set[str]) -> list[dict]:
    """Augment secret detection with gitleaks if it is installed."""
    if shutil.which("gitleaks") is None:
        return []
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "gl.json"
        try:
            subprocess.run(
                ["gitleaks", "detect", "--no-git", "--no-banner",
                 "--source", str(repo),
                 "--report-format", "json", "--report-path", str(report)],
                capture_output=True, text=True,
            )
        except FileNotFoundError:
            return []
        if not report.is_file():
            return []
        try:
            data = json.loads(report.read_text(encoding="utf-8", errors="replace") or "[]")
        except json.JSONDecodeError:
            return []
    out = []
    for item in data:
        rel = item.get("File", "")
        norm = rel.replace("\\", "/").lstrip("./")
        if changed and norm not in changed:
            continue
        out.append({
            "category": "SECRET", "kind": f"gitleaks:{item.get('RuleID', 'rule')}",
            "file": norm, "line": item.get("StartLine", 0),
            "match": (item.get("Secret") or item.get("Match") or "")[:80],
        })
    return out


def scan_line(rel: str, lineno: int, text: str, glossary) -> list[dict]:
    found = []
    for kind, pat in SECRET_PATTERNS:
        for m in pat.finditer(text):
            found.append({"category": "SECRET", "kind": kind, "file": rel,
                          "line": lineno, "match": m.group(0)[:80]})
    for m in ASSIGNMENT_RE.finditer(text):
        value = m.group(2)
        if PLACEHOLDER_RE.match(value):
            continue
        found.append({"category": "SECRET", "kind": f"assignment:{m.group(1).lower()}",
                      "file": rel, "line": lineno, "match": m.group(0)[:80]})
    for m in EMAIL_RE.finditer(text):
        found.append({"category": "PII", "kind": "email", "file": rel,
                      "line": lineno, "match": m.group(0)})
    for m in CREDIT_CARD_RE.finditer(text):
        if luhn_ok(m.group(0)):
            found.append({"category": "PII", "kind": "credit-card", "file": rel,
                          "line": lineno, "match": m.group(0)})
    for m in PHONE_RE.finditer(text):
        found.append({"category": "PII", "kind": "phone", "file": rel,
                      "line": lineno, "match": m.group(0)})
    for m in IPV4_RE.finditer(text):
        octs = m.group(0).split(".")
        if all(o.isdigit() and int(o) <= 255 for o in octs):
            found.append({"category": "PII", "kind": "ip-address", "file": rel,
                          "line": lineno, "match": m.group(0)})
    for pat, term, repl in glossary:
        if pat.search(text):
            found.append({"category": "NAME", "kind": f"glossary:{term}", "file": rel,
                          "line": lineno, "match": term, "replacement": repl})
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description="Detect secrets / PII / org-specific names in pending changes.")
    ap.add_argument("--repo", default=".", help="Repository path (default: current dir)")
    ap.add_argument("--glossary", default=None, help="Glossary file (default: <repo>/.scrub-glossary)")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    ap.add_argument("--staged", action="store_true", help="Scan staged changes only")
    ap.add_argument("--no-untracked", action="store_true", help="Skip untracked files")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if run_git(["rev-parse", "--is-inside-work-tree"], repo) is None:
        print("error: not a git repository (or git not installed)", file=sys.stderr)
        return 2

    glossary_path = Path(args.glossary) if args.glossary else repo / ".scrub-glossary"
    glossary = load_glossary(glossary_path)

    files = candidate_files(repo, args.staged, not args.no_untracked, exclude=glossary_path)
    changed = {p.relative_to(repo).as_posix() for p in files}

    findings: list[dict] = []
    for p in files:
        rel = p.relative_to(repo).as_posix()
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "\x00" in text[:4096]:  # binary guard
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            findings.extend(scan_line(rel, i, line, glossary))

    findings.extend(gitleaks_findings(repo, changed))
    findings.sort(key=lambda f: (f["file"], f["line"], f["category"]))

    if args.format == "json":
        print(json.dumps({"findings": findings, "scanned_files": sorted(changed),
                          "glossary": str(glossary_path), "gitleaks": shutil.which("gitleaks") is not None},
                         ensure_ascii=False, indent=2))
        return 1 if findings else 0

    # text report
    print(f"Scanned {len(files)} changed file(s). "
          f"gitleaks: {'available' if shutil.which('gitleaks') else 'NOT installed (regex fallback)'}. "
          f"glossary: {'loaded' if glossary else 'none'} ({glossary_path}).")
    if not findings:
        print("No findings. Safe to proceed.")
        return 0
    counts: dict[str, int] = {}
    for f in findings:
        counts[f["category"]] = counts.get(f["category"], 0) + 1
    print(f"\n{len(findings)} finding(s): " +
          ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for f in findings:
        repl = f.get("replacement")
        suffix = f"  -> suggest: {repl}" if repl else ""
        print(f"  [{f['category']:6}] {f['file']}:{f['line']}  "
              f"{f['kind']}  «{f['match']}»{suffix}")
    print("\nReview each finding with a human before applying fixes. "
          "Real secrets must be ROTATED/REVOKED, not just text-replaced.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
