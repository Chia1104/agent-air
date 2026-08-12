#!/usr/bin/env python3
"""Fail when tracked candidate files appear to contain credentials."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".json", ".jsonc", ".yaml", ".yml", ".toml", ".md", ".txt", ".env",
    ".sh", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".xml", ".ini",
}
SKIP_PARTS = {".git", "private", "node_modules", "__pycache__"}
PLACEHOLDER = re.compile(r"\$\{(?:env:)?[A-Za-z_][A-Za-z0-9_]*\}")
PATTERNS = {
    "GitHub token": re.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9_]{20,}"),
    "OpenAI-style key": re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    "AWS access key": re.compile(r"(?<![A-Za-z0-9])AKIA[0-9A-Z]{16}"),
    "JWT": re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "Bearer credential": re.compile(r"Bearer\s+(?!\$\{)[A-Za-z0-9._~+/=-]{18,}", re.IGNORECASE),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "assigned secret": re.compile(
        r"(?im)^\s*[\"']?(?:api[_-]?key|access[_-]?token|client[_-]?secret|password|passwd|token)[\"']?\s*[:=]\s*[\"']?(?!\$\{)([^\s\"',#}]{12,})"
    ),
}


def candidate_files() -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=True,
    )
    files = []
    for line in proc.stdout.splitlines():
        path = REPO / line
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and not any(part in SKIP_PARTS for part in path.relative_to(REPO).parts):
            files.append(path)
    return files


def main() -> int:
    findings = []
    for path in candidate_files():
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for label, pattern in PATTERNS.items():
            # Skills often contain executable examples such as `token = value`
            # or deterministic public hook IDs. Generic assignments are only
            # actionable in settings and env files; prefix-shaped credentials
            # and private keys are still checked everywhere.
            if label == "assigned secret" and path.relative_to(REPO).parts[0] != "configs" and path.name not in {".env", ".env.example"}:
                continue
            for match in pattern.finditer(text):
                excerpt = match.group(0)
                lower = excerpt.lower()
                if PLACEHOLDER.search(excerpt) or "redacted" in lower:
                    continue
                # Documentation commonly uses obvious runs of x characters.
                payload = re.sub(r"^bearer\s+", "", excerpt, flags=re.IGNORECASE)
                payload = re.sub(r"^(?:gh[pousr]_|sk-)", "", payload, flags=re.IGNORECASE)
                payload = re.sub(r"[^A-Za-z0-9]", "", payload)
                if payload and len(set(payload.lower())) <= 2 and "x" in payload.lower():
                    continue
                line = text.count("\n", 0, match.start()) + 1
                findings.append((path.relative_to(REPO), line, label))
    if findings:
        print("Potential secrets found:", file=sys.stderr)
        for path, line, label in findings:
            print(f"  {path}:{line}: {label}", file=sys.stderr)
        print("Move real values under private/ or replace them with ${ENV_VAR} references.", file=sys.stderr)
        return 1
    print(f"Secret scan passed ({len(candidate_files())} candidate files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
