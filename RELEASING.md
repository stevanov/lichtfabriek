# RELEASING

How Lichtfabriek versions and releases. One version line for both services.

## Version format

`v<year>.<month>_<minor>.<bugfix>` — e.g. `v26.11_38.0`.

Regex: `^v\d{2}\.\d{2}_\d+\.\d+$`

- `<year>.<month>` — release month (e.g. `26.11` = Nov 2026)
- `<minor>` — feature/minor counter since month start
- `<bugfix>` — patch counter

Between tags `git describe` appends `-<n>-g<sha>`. Release artifacts (tarball,
image) carry a baked `VERSION` file; the target has no `.git`, so version comes
from the file, not from git describe.

## Git flow

```
feature/*  ──>  devel  ──no-ff──>  master  ──tag──>  release
```

- All work on `feature/*` branches off `devel`.
- Merge to `devel` with `--no-ff`.
- `master` holds only releases.
- Tag releases on `master`; never move or delete a tag.

## Release procedure (v1)

1. On `devel`: bump the version (`shared/version.py`, `VERSION` file), update
   `CHANGELOG.md`, commit.
2. Run tests: `.venv/bin/python -m pytest tests/` — all green.
3. Merge `devel` → `master` with `--no-ff`:
   ```bash
   git checkout master && git merge --no-ff devel
   ```
4. Tag: `git tag -a v26.11_38.0 -m "release v26.11_38.0"` then push tag.
5. Create the release on GitHub (tarball + `install.sh` + checksums).
6. Announce in the makerspace channel.

## Rollback

Keep the previous release tarball on GitHub. On the Pi:
`deploy/install.sh --version <previous-tag>` reinstalls the previous release.
The install script keeps one previous copy of the app dir for instant rollback.
