# Security and publication policy

This repository contains public source, authored test fixtures and usage documentation. Screenshots, recordings, local designs, measured reports, raw traces, databases, environments and credentials are intentionally excluded. Original local development history is not part of this source publication.

Setup creates a fresh random secret in ignored `.env`. Never reuse an external account password. Authentication is intended for a localhost demo, not internet exposure. Dependencies are installed during setup; the core applications then run locally. Exports and evaluations are created only when you request them and remain on that machine.

Before committing or pushing, run:

```powershell
python scripts/check_publication.py --staged
python scripts/check_publication.py --history
git config core.hooksPath .githooks
```

The hooks reject private artifact paths, recognizable credential patterns, personal email addresses and workstation paths. The included CI repeats the history check when enabled; hosted execution is disabled for this source-only publication. These checks are a guard, not a guarantee that every possible sensitive value can be detected. Review staged content and commit metadata as well. Use your GitHub no-reply email for commits.

If a real credential has been published, revoke or rotate it immediately; removing its current file alone does not remove earlier Git history. Do not post credentials or private design files in issues or pull requests. Keep security reproductions free of sensitive data.
