# SPEC — Lichtfabriek: Pi Zero W animates 3 RGB cubes + LED sign, driven by MQTT patterns

Grill 2026-11-26, review 2026-11-26 (ghce gpt-6-luna + claude-sonnet-5.5, all amendments applied). Two services in one monorepo: `kubusd` (headless Pi daemon) + `console` (Flask web app). Git flow master/devel. GitHub: TBD url.

## §G

On a Pi Zero W v1.1, run a headless daemon (`kubusd`) that drives 3 PWM RGB strips (in 1 m³ / 1000 L cubes) + 5 on/off outputs (analog LED sign), animating patterns received over MQTT (payload-encrypted), with autonomous fallback when offline; a Flask web app (`console`) lets makerspace users create patterns and publish them immediately, while admins audit and can revoke any live pattern.

## §C

- hardware: Pi Zero W v1.1 (armv6, single-core, 512 MB RAM, 26 usable GPIO). 3 RGB strips = 9 PWM channels + 5 on/off sign outputs = 14 signals.
- PWM: pigpio daemon (pigpiod) runs on the Pi host; kubusd connects over its socket. Hardware PWM impossible for 9 channels (2 channels on BCM2835). software PWM rejected (jitter, CPU on single core).
- deployment Pi: systemd unit + install script pulled from a GitHub release. release tarball ships with a checksum (SHA256) verified by install.sh; previous release kept for rollback. Docker on the Pi: NO (armv6 pain, too heavy). kubusd headless, no GUI.
- deployment dev + console: Docker (docker compose). console is the only web app; it runs on Steven's server.
- versioning: `v26.11_38.0` = `v<year>.<month>_<minor>.<bugfix>` generated via `git describe`. one version line for both services. regex: `^v\d{2}\.\d{2}_\d+\.\d+$`. git describe appends `-<n>-g<sha>` between tags; release tarballs/images carry a baked `VERSION` file (no `.git` on target).
- repo: monorepo, two services (`pi/` + `console/`), git flow: feature → devel → master, `--no-ff`. releases tagged on master.
- animation model: built-in primitives + params over MQTT. Pi ships primitives (rainbow, pulse, fade, chase, holiday themes, sign sequences); messages name primitive + params (colors, speed, intensity). no raw frame data in v1.
- offline: persist last-good pattern in SQLite; on first boot run built-in default show; MQTT best-effort (subscribe when broker reachable, keep animating when not). survives reboot.
- sign: fixed always-on animation of the 5 outputs, 24/7, plus time-based scheduler (on/off times) AND manual MQTT on/off override. schedule configurable via .env AND via MQTT (runtime override wins). (scheduler restrict-user-publishing idea NOT in v1.)
- config Pi: `.env` = static config (MQTT broker URL + creds, shared payload key, GPIO pin map, host paths). SQLite = runtime state (last pattern, schedule overrides, audit). `.env.example` documents keys. no hand-edited JSON.
- MQTT broker: configurable via `.env`; v1 ships over a public broker. payload encryption only (shared secret key in .env), no TLS requirement in v1.
- payload crypto (review 2026-11-26): AEAD only — ChaCha20-Poly1305 via PyNaCl (preferred; check armv6 wheel availability at build, fallback AES-GCM via `cryptography` if it builds on armv6). random nonce per message, topic bound as associated data, `key_id` field for key rotation. replay protection: monotonic counter + timestamp window; kubusd persists last-accepted counter and rejects lower.
- revoke (review 2026-11-26): `pattern/set` uses retained messages + QoS1 + persistent session; "revoke" = publish default/previous pattern; persisted pattern gets a TTL so a revoked pattern cannot resurrect forever on an offline Pi.
- safety caps (review 2026-11-26): validated on console AND kubusd. strobe frequency < 3 Hz, global brightness cap, max message size, max `colors` list length (512 MB Pi). concurrent publishes = last-write-wins.
- privacy (review 2026-11-26): posting IP + username NEVER in the MQTT payload (public broker, GDPR); console keeps them in its DB only; kubusd logs pattern id + hash.
- SD-card safety (review 2026-11-26): audit table = ring buffer (capped rows); invalid-message logging rate-limited. SQLite WAL + `synchronous=FULL`; on open/integrity failure → rename db, recreate, run default show.
- kubusd health (review 2026-11-26): pin frame rate (≈30 fps), pigpio reconnect + health-check (pigpiod may restart), MQTT reconnect, render-loop watchdog, `Restart=always` + `WatchdogSec` in the unit.
- sign clock (review 2026-11-26): Pi Zero has no RTC → unsynced clock = sign defaults to a defined state; `TZ` set in `.env`; manual override has an expiry; sign/schedule messages accepted from console-admin only.
- language: Python 3 everywhere. Pi: paho-mqtt + pigpio client + sqlite3 (stdlib). console: Flask (accounts, session auth, admin page, SQLite, paho-mqtt publisher). single codebase, two entry points.
- verification: simulator mode in kubusd (renders strips/sign as ANSI/terminal, no pigpio needed) + unit tests + hardware smoke test script for the real Pi.
- publish workflow: any logged-in user can create AND activate patterns immediately; admin approval is post-hoc audit (see who published what, revoke/disable a live pattern). every pattern carries metadata: title, creator username, description, created timestamp, posting IP address (stored in console DB only).
- accounts: admin-created accounts (username + password) from the console admin page; no self-registration, no LDAP/OAuth. admin can audit, revoke live patterns, ban IPs.
- edge handling: kubusd validates every message (schema + payload auth + replay). invalid/forged → dropped + rate-limited log (pattern id/hash only), never interrupt running pattern, stay on last-good. console rate-limits publish endpoints; admin can ban IP.
- out of scope v1: TLS, LDAP/OAuth, raw frame data, GUI on Pi, time-based user publishing schedule, self-registration, mobile app.
- naming: system = Lichtfabriek; Pi daemon = kubusd; web app = console.
- ? which public broker exactly (e.g. HiveMQ public vs broker.emqx.io) — configurable, decide at install.
- ? exact GPIO pin map for 9 PWM + 5 sign outputs — comes from the physical wiring, set in `.env`.
- ? where the old Python 2.7 code lives — port behavior from it if Steven provides it (not found in /mnt/c/development).
- ? console hosting details (server IP/domain, GitHub URL) — TBD, config at install.
- ? which primitives ship in v1 — proposal: rainbow, pulse, fade, chase, holiday themes, sign sequences; expandable list.

## §I

- kubusd env (`.env` / `.env.example`): `MQTT_BROKER`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `PAYLOAD_KEY` (shared secret), `PIGPIOD_HOST`, `PIGPIOD_PORT`, GPIO pin map (9 PWM + 5 sign, e.g. `PIN_R1=…`), `SIGN_SCHEDULE` (json), `SQLITE_PATH`, log level.
- kubusd CLI: `kubusd run` (daemon, systemd), `kubusd sim` (simulator mode, ANSI output), `kubusd smoke` (hardware smoke test), `--config .env`.
- kubusd MQTT subscribe topics: `lichtfabriek/pattern/set` (set/activate pattern; retained + QoS1 + persistent session), `lichtfabriek/sign/set` (on/off override, admin only), `lichtfabriek/sign/schedule` (schedule update, admin only), `lichtfabriek/control` (generic). payload = JSON, encrypted with shared key (AEAD + nonce + counter + key_id).
- pattern payload shape: `{key_id, counter, ts, topic_aad, primitive, params:{colors, speed, intensity}, pattern_id, pattern_hash}`. NO `meta.ip`/username in payload (privacy, V19); console DB holds title/creator/description/created_ts/ip, Pi logs pattern_id + pattern_hash.
- kubusd SQLite tables: `patterns` (last-good + history), `sign_state` (schedule + override), `audit` (received messages, invalid attempts).
- kubusd systemd: unit file `deploy/kubusd.service`, install script `deploy/install.sh` (pulls release tarball from GitHub, installs deps, enables service). pigpiod as separate host service.
- console env: `MQTT_BROKER`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `PAYLOAD_KEY`, `KEY_ID`, `SECRET_KEY` (flask sessions), `SQLITE_PATH`, `ADMIN_PASSWORD` (forced change on first login), `TZ`.
- console web routes: login; patterns (create, activate, list, my patterns); admin (users, audit view, revoke/disable live pattern, ban IP, audit log); simulator preview (reuse kubusd sim rendering? or JS preview).
- docker: `compose.yaml` at repo root — console service (build from `console/`), dev-only kubusd simulator service. Pi deploy via systemd, not docker.
- versioning: `git describe` produces `v<year>.<month>_<minor>.<bugfix>`; release = tag on master; both services report the same version.

## §V

V1: kubusd runs 9 PWM channels + 5 sign outputs via pigpio socket, no root GPIO access in-process.
V2: MQTT message schema + AEAD auth + replay counter validated before apply; invalid/forged/stale → logged (rate-limited), never interrupts current pattern.
V3: offline/reboot: last-good pattern resumes from SQLite (WAL, synchronous=FULL); first boot → built-in default show; DB corruption → rename, recreate, default show.
V4: simulator mode runs the same animation engine without pigpio (headless, ANSI output) — unit-testable in CI.
V5: sign has fixed animation + schedule + manual override; MQTT override wins over schedule, both configurable, override has expiry; unsynced clock → defined default sign state.
V6: console records title, creator username, description, created_ts, posting IP in ITS OWN DB; MQTT payload carries pattern_id + pattern_hash only (never IP/username, V19).
V7: console: admin can revoke/disable any live pattern; ban IP stops publishing; rate limit on publish endpoints.
V8: version `v<year>.<month>_<minor>.<bugfix>` from git describe, regex `^v\d{2}\.\d{2}_\d+\.\d+$`; one version for both services; releases only on master via tag; VERSION baked into release artifacts.
V9: payload encryption = AEAD (ChaCha20-Poly1305 via PyNaCl, fallback AES-GCM), random nonce, topic as AAD, `key_id` in every message; key never in git, only `.env` (`.env.example` has placeholder); console key injected via `env_file`/secrets, never in compose.yaml.
V10: deploy via systemd + install script from GitHub release, SHA256-verified tarball, previous release kept for rollback; idempotent; works offline after install.
V11: no self-registration; accounts created by admin only.
V12: crypto AEAD-only + replay counter (V2/V9).
V13: replay protection: monotonic counter + timestamp window; kubusd persists last-accepted counter, rejects lower (V2).
V14: safety caps: strobe < 3 Hz, global brightness cap, max message size, max `colors` length, last-write-wins for concurrent publishes.
V15: `pattern/set` retained + QoS1 + persistent session; revoke = publish default/previous pattern; persisted pattern TTL (no resurrection offline).
V16: audit ring buffer (capped rows), rate-limited invalid logging; SQLite WAL + synchronous=FULL, corruption → rename+recreate+default show.
V17: kubusd health: pigpiod + MQTT reconnect/healthcheck, render-loop watchdog, `Restart=always` + `WatchdogSec` in unit.
V18: sign clock: unsynced clock → defined default state; `TZ` in .env; override expiry; sign/schedule messages console-admin only.
V19: privacy: posting IP + username never in MQTT payload; console DB only; kubusd logs pattern_id + pattern_hash.

## §T

id|status|task|cites
T1|.|repo scaffold: git flow master/devel, README, RELEASING.md, AGENTS.md, .gitignore, .env.example, compose.yaml|C
T2|.|kubusd config loader (.env) + pin map + SQLite init (WAL + FULL, ring-buffer audit)|V1,V3,V16,I.kubusd-env
T3|.|kubusd animation engine: primitives (rainbow, pulse, fade, chase, holiday, sign sequences) + render loop + safety caps|V1,V4,V14
T4|.|kubusd pigpio driver (9 PWM + 5 out) + simulator mode (ANSI) + health/reconnect|V1,V4,V17
T5|.|kubusd MQTT: subscribe, AEAD decrypt, replay counter, validate, apply pattern / sign set / schedule; audit log|V2,V12,V13,V16
T6|.|kubusd persistence: last-good pattern + TTL + schedule + override + corruption handling|V3,V5,V15
T7|.|kubusd systemd unit (Restart, WatchdogSec) + install.sh (SHA256 + rollback)|V8,V10,V17
T8|.|console: Flask app, session auth, admin accounts, forced first-login password change|V11
T9|.|console: patterns (create, activate, list), post-hoc audit view, revoke/disable, IP capture (DB only)|V6,V7,V19
T10|.|console: MQTT publish (AEAD + counter + retained + QoS1), rate limit, ban|V7,V9,V13,V14,V15
T11|.|console UI: login, patterns page, admin page, audit log; Docker build (secrets for key)|V7,V9,V19
T12|.|tests: kubusd unit (engine, crypto, replay, validation, persistence) in simulator mode; console unit; hardware smoke script|V1,V2,V4,V12,V13
T13|.|release v1: versioning wired to git describe, VERSION baked, devel → master, tag, docs|V8,C.versioning
T14|.|field deploy on real Pi + cubes: pin map, broker creds, TZ, schedule; smoke test on hardware|V1,V5,V10,V18

## §B

id|date|cause|fix
