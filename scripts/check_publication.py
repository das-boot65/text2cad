"""Reject private artifacts and recognizable credentials in the index or Git history."""
import argparse
import re
import subprocess
from pathlib import PurePosixPath

PRIVATE_PARTS = {
    ".venv", "venv", "node_modules", "dist", "data", "assets", "benchmark", "reports",
    "artifacts", "audit", "downloads", "test-results", "playwright-report", "__pycache__",
    ".pytest_cache", ".ruff_cache", ".mypy_cache", ".git", "redesign",
}
PRIVATE_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".log", ".pem", ".key", ".p12", ".pfx", ".pyc",
    ".zip", ".webm", ".mp4", ".png", ".jpg", ".jpeg", ".step", ".stl", ".pdf",
}
PUBLIC_DOCS = {
    "docs/ARCHITECTURE.md", "docs/API.md", "docs/PROTOCOL.md", "docs/USER_GUIDE.md",
    "docs/TEST_PLAN.md", "docs/TROUBLESHOOTING.md",
}
RULES = {
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "github-token": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})"),
    "cloud-access-key": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "service-token": re.compile(rb"(?:xox[baprs]-[A-Za-z0-9-]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{32,})"),
    "hardcoded-credential": re.compile(
        rb"(?im)(?:secret|password|api[_-]?key|access[_-]?token)\s*[=:]\s*[\"']([A-Za-z0-9+/_.=-]{24,})[\"']"
    ),
    "personal-email": re.compile(rb"[A-Za-z0-9._%+-]+@(?:gmail|outlook|hotmail|yahoo|protonmail|icloud)\.com\b", re.I),
    "personal-workspace-path": re.compile(rb"(?i)[A-Z]:[/\\](?:Users|portfolio|Softwares)[/\\]"),
}


def git(*arguments):
    return subprocess.check_output(["git", *arguments])


def blocked_path(name):
    path = PurePosixPath(name)
    parts = set(path.parts)
    filename = path.name.lower()
    if filename.startswith(".env") and filename != ".env.example":
        return True
    if filename in {".npmrc", ".pypirc", ".netrc", ".git-credentials", "id_rsa", "id_ed25519"}:
        return True
    if parts & PRIVATE_PARTS or path.suffix.lower() in PRIVATE_SUFFIXES:
        return True
    if name.startswith("docs/") and name not in PUBLIC_DOCS:
        return True
    return False


def scan_blob(name, contents):
    failures = []
    if blocked_path(name):
        failures.append((name, "private-file-policy"))
    for rule, expression in RULES.items():
        if expression.search(contents):
            failures.append((name, rule))
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true")
    mode.add_argument("--history", action="store_true")
    options = parser.parse_args()
    failures = []
    blobs = 0
    if options.staged:
        names = git("ls-files", "--cached", "-z").decode("utf-8").split("\0")
        for name in filter(None, names):
            failures.extend(scan_blob(name, git("show", ":" + name)))
            blobs += 1
    else:
        objects = git("rev-list", "--objects", "--all").decode("utf-8").splitlines()
        process = subprocess.Popen(["git", "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        try:
            for entry in objects:
                oid, _, name = entry.partition(" ")
                process.stdin.write((oid + "\n").encode())
                process.stdin.flush()
                header = process.stdout.readline().decode().split()
                contents = process.stdout.read(int(header[2]))
                process.stdout.read(1)
                if header[1] == "blob":
                    failures.extend(scan_blob(name, contents))
                    blobs += 1
                elif header[1] == "commit":
                    for field in re.findall(rb"(?m)^(?:author|committer) (.+)$", contents):
                        if RULES["personal-email"].search(field):
                            failures.append((oid[:12], "private-commit-email"))
            # Check paths in every tree, including objects reused under another name.
            for revision in git("rev-list", "--all").decode().splitlines():
                names = git("ls-tree", "-rz", "--name-only", revision).decode("utf-8").split("\0")
                failures.extend((name, "private-history-path") for name in filter(None, names) if blocked_path(name))
        finally:
            process.stdin.close()
            process.wait()
    if failures:
        for name, rule in sorted(set(failures)):
            print(f"BLOCKED {name}: {rule}")
        print("No credential contents are printed. Keep private files outside publication history.")
        return 1
    print(f"Publication policy passed: {blobs} blobs checked. Automated checks cannot guarantee absence of every secret.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
