# RELEASING

How Lichtfabriek versions and releases. One version line for both services.

## Version format

`v<year>.<month>_<minor>.<bugfix>` with an optional pre-release suffix.

Regex: `^v\d{2}\.\d{2}_\d+\.\d+(-(alpha|beta|rc)\d+)?$`

- `<year>.<month>` — release month (e.g. `26.11` = Nov 2026)
- `<minor>` — feature/minor counter since month start
- `<bugfix>` — patch counter
- pre-release suffix: `-alphaN` → `-betaN` → `-rcN` → final

## Pre-release ladder

For v26.11_0.0 (Steven 2026-11-26): iterate alphas, then betas, then release
candidates, then the final tag.

```
v26.11_0.0-alpha1  ->  ...  ->  v26.11_0.0-alphaN
   ->  v26.11_0.0-beta1  ->  ...  ->  v26.11_0.0-betaN
   ->  v26.11_0.0-rc1    ->  ...  ->  v26.11_0.0-rcN
   ->  v26.11_0.0  (final, tagged on master)
```

- Pre-release tags are created on `master` (merged from `devel` with `--no-ff`),
  so each alpha/beta/rc is a buildable, tagged state of the repo.
- Each pre-release runs the full test suite + simulator demo; anything broken
  is fixed before the next tag.
- `shared/version.next_version()` suggests the next suffix automatically
  (alphaN→alphaN+1); moving alpha→beta→rc is a human decision based on how
  stable the build feels.
- The final `v26.11_0.0` is the release tag on `master`; pre-releases are
  earlier tags on the same branch.

Between tags `git describe` appends `-<n>-g<sha>`. Release artifacts (tarball,
image) carry a baked `VERSION` file; the target has no `.git`, so version comes
from the file, not from git describe.

## Git flow

```
feature/*  ──>  devel  ──no-ff──>  master  ──tag──>  release
```

- All work on `feature/*` branches off `devel`.
- Merge to `devel` with `--no-ff`.
- `master` holds releases: every alpha/beta/rc AND the final release is tagged
  there (each is merged `devel` → `master` with `--no-ff`).
- Never move or delete a tag.

## Release procedure (per pre-release or final)

1. On `devel`: set the version (`VERSION` file — e.g. `v26.11_0.0-alpha1`),
   update `CHANGELOG.md`, commit.
2. Run tests: `.venv/bin/python -m pytest tests/` — all green.
3. Merge `devel` → `master` with `--no-ff`, then tag (pre-release OR final):
   ```bash
   git checkout master && git merge --no-ff devel
   git tag -a v26.11_0.0-alpha1 -m "alpha 1"   # or v26.11_0.0 for the final
   ```
4. Push master + the tag.
5. Create the release on GitHub (`https://github.com/stevanov/lichtfabriek`):
   attach the artifacts `install.sh` expects (exact names):
   `lichtfabriek-<tag>.tar.gz` + `lichtfabriek-<tag>.sha256` (a `sha256sum`
   over the tarball).
6. Announce in the makerspace channel.

## Rollback

Keep the previous release tarball on GitHub. On the Pi, re-run the installer
with the previous tag: `KUBUSD_VERSION=<previous-tag> ./deploy/install.sh`.
The install script keeps one previous copy of the app dir for instant rollback.
