# AGENTS.md

Guidance for AI agents (and humans) working in this repo. Keep it short; the
design lives in `SPEC.md`.

## Repo conventions

- **Two services, one monorepo**: `kubusd/` (Pi daemon, headless) and
  `console/` (Flask web app). Both are Python 3. Shared code in `shared/`.
- **Git flow**: `feature/*` → `devel` → `master` (releases only). Never push
  directly to `master`. Merges to `devel`/`master` use `--no-ff`.
- **Versioning**: one version line `v<year>.<month>_<minor>.<bugfix>` (regex
  `^v\d{2}\.\d{2}_\d+\.\d+$`). See `RELEASING.md`.
- **No hardware on dev**: test animation/mqtt via kubusd simulator
  (`python -m kubusd sim`), not pigpio. Hardware smoke = `python -m kubusd smoke`.
- **Env, never hard-coded config**: all config via `.env` (`.env.example` is
  the contract). Keys/secrets never committed.
- **The repo is public on GitHub** — `deploy/install.sh` pulls release
  tarballs from `github.com/stevanov/lichtfabriek` without auth. Never commit
  `.env` or PAYLOAD_KEY values; secrets stay out of the repo (V9).
- **V20: no absolute/host paths in the repo.** No `/home/`, `/mnt/c`,
  `/opt/...`, `/etc/...`, `/var/lib/...` in committed code or config. Defaults
  are relative (`./data/...`); the systemd unit is a template
  (`__KUBUSD_*__` placeholders) filled by `deploy/install.sh` at install time.

## Load-bearing invariants (from SPEC §V)

- V2/V13: MQTT messages are AEAD-authenticated + replay-counted before apply;
  invalid messages are dropped and rate-limited-logged, never interrupting the
  current pattern.
- V14: safety caps (strobe < 3 Hz, global brightness, message/colors size)
  enforced in console AND kubusd. Never remove a cap without a SPEC amendment.
- V19: IP + username never in the MQTT payload — console DB only.
- V9: AEAD crypto via PyNaCl (ChaCha20-Poly1305), fallback AES-GCM; `key_id`
  in every message; key only in `.env`/secrets, never in compose.yaml.

## When editing

- If a change touches SPEC §V or the payload schema → update SPEC.md too
  (via the spec skill) and say so in the MR.
- Keep patterns as built-in primitives + params; no raw frame data in v1.
- Tests: `pytest tests/`. Run before pushing to devel.
- Don't assume the Pi has internet, an RTC, or a working clock.

## Do NOT

- Don't add TLS requirements — v1 is payload-encryption-only (replay counter
  is the protection; see SPEC).
- Don't put broker credentials or PAYLOAD_KEY in code or compose.yaml.
- Don't self-register users — accounts are admin-created only.
