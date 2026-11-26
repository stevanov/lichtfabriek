# SPEC — Lichtfabriek: Pi Zero W animates 3 RGB cubes + LED sign, driven by MQTT patterns

Grill 2026-11-26, review 2026-11-26 (ghce gpt-6-luna + claude-sonnet-5.5, all amendments applied). Two services in one monorepo: `kubusd` (headless Pi daemon) + `console` (Flask web app). Git flow master/devel. Repo: github.com/stevanov/lichtfabriek.

## §G

On a Pi Zero W v1.1, run a headless daemon (`kubusd`) that drives 3 PWM RGB strips (in 1 m³ / 1000 L cubes) + 5 on/off outputs (analog LED sign), animating patterns received over MQTT (payload-encrypted), with autonomous fallback when offline; a Flask web app (`console`) lets makerspace users create patterns and publish them immediately, while admins audit and can revoke any live pattern.

## §C

- hardware: Pi Zero W v1.1 (armv6, single-core, 512 MB RAM, 26 usable GPIO). 3 cubes, each with ONE plain RGB LED strip, whole strip one color at a time (like a single pixel) → 3 color outputs = 9 PWM channels (R/G/B per cube). NO addressable pixels (no WS2812/Neopixel). Plus 5 on/off sign outputs = 14 signals total. CUBE POSITIONS (2026-11-26): cube index 0 = TOPMOST IBC tank, 1 = middle, 2 = bottom — visualizer, ANSI sim, console editor and field wiring all follow this mapping.
- PWM: pigpio daemon (pigpiod) runs on the Pi host; kubusd connects over its socket. Hardware PWM impossible for 9 channels (2 channels on BCM2835). software PWM rejected (jitter, CPU on single core).
- deployment Pi: systemd unit + install script pulled from a GitHub release. release tarball ships with a checksum (SHA256) verified by install.sh; previous release kept for rollback. Docker on the Pi: NO (armv6 pain, too heavy). kubusd headless, no GUI.
- deployment dev + console: Docker (docker compose). console is the only web app; it runs on Steven's server.
- versioning: `v26.11_38.0` = `v<year>.<month>_<minor>.<bugfix>`, with optional pre-release suffix `-(alpha|beta|rc)<n>`. regex: `^v\d{2}\.\d{2}_\d+\.\d+(-(alpha|beta|rc)\d+)?$`. one version line for both services. pre-release ladder (Steven 2026-11-26): alphas → betas → rcs → final; every pre-release AND the final are merged devel → master (`--no-ff`) and tagged on master. git describe appends `-<n>-g<sha>` between tags; release tarballs/images carry a baked `VERSION` file (no `.git` on target).
- repo: monorepo, two services (`pi/` + `console/`), git flow: feature → devel → master, `--no-ff`. releases tagged on master.
- animation model (alpha2 amendment 2026-11-26): a pattern is a SEQUENCE of steps `[{cubes, duration_s}, ...]`, looped; backward compatible (one step = pre-alpha2 behavior). each cube runs its OWN primitive + params (independent per cube); a step may specify 1/2/3 cubes; unspecified cubes PERSIST their previous step's settings (first step default = off). primitives (alpha2 set): rainbow, pulse, fade, chase, holiday, off + NEW random/fire/sparkle, hue sweep/sine blend, strobe/police, knight-rider/sweep, static white/dim. no raw frame data. the sign is NOT a user primitive — it runs the fixed hammer animation (SPEC §C). SPEED + OFFSET SEMANTICS (2026-11-26): `speed` is a uniform multiplier for ALL primitives — 1.0 = the primitive's normal pace, 2.0 = twice as fast, 0.5 = half speed; each primitive has its own base rate/period (engine.py + console JS mirror); strobe-family effective frequency is capped < 3 Hz regardless of speed (V14); flash-like primitives (strobe, police, chase, knight, sparkle) keep that clamp, while smooth/seeded primitives (rainbow, huesweep, sine, fade, random, fire) do not — the clamp must never make the speed slider dead. `offset` is a PHASE SHIFT expressed as a FRACTION of one animation cycle (0..1) — 0.5 = half a cycle out of phase; giving cubes different offsets (e.g. 0 / 0.33 / 0.66) makes knight/chase/rainbow sweep across the stack; the engine converts the fraction using each primitive's own cycle (rate-based: 1/rate, period-based: its period).
- offline: persist last-good pattern in SQLite; on first boot run built-in default show; MQTT best-effort (subscribe when broker reachable, keep animating when not). survives reboot.
- sign: fixed always-on animation of the 5 outputs, 24/7. CONFIRMED (Steven, 2026-11-26; figure: `docs/sign-layout.svg`). GEOMETRY: the hammer pivots around the BOTTOM END of its handle, which sits at the right side of the anvil's top face; the head is the far (upper) end and swings counterclockwise from straight up to pointing left. 5 outputs = anvil (always on) + 3 hammer poses + sparks. Loop (~3 s total, the board never goes dark — only hammer pose + sparks change): (1) hammer upright/vertical, head at top, handle down to the pivot on the right; (2) tilted ~45° to the left, head upper-left; (3) nearly horizontal, pointing left, head resting on the anvil top (impact pose), handle extending right; (4) a few thin diagonal spark lines flash up and to the left of the head for a split second while the hammer stays in the impact pose; (5) sparks off, same frame as step 3 (hammer resting, no sparks); (6) hammer JUMPS straight back to upright (step 1) — no gradual lift, no in-between frames — loop repeats. Implemented as configurable constants in `kubusd/scheduler.py` (default period 3.0 s). plus time-based scheduler (on/off times) AND manual MQTT on/off override. schedule configurable via .env AND via MQTT (runtime override wins). users cannot program sign sequences (scheduler restrict idea, NOT in v1).
- config Pi: `.env` = static config (MQTT broker URL + creds, shared payload key, GPIO pin map, host paths). SQLite = runtime state (last pattern, schedule overrides, audit). `.env.example` documents keys. no hand-edited JSON.
- MQTT broker: configurable via `.env`; v1 ships over a public broker. payload encryption only (shared secret key in .env), no TLS requirement in v1.
- payload crypto (review 2026-11-26): AEAD only — ChaCha20-Poly1305 via PyNaCl (preferred; check armv6 wheel availability at build, fallback AES-GCM via `cryptography` if it builds on armv6). random nonce per message, topic bound as associated data, `key_id` field for key rotation. replay protection: monotonic counter + timestamp window; kubusd persists last-accepted counter and rejects lower.
- revoke (review 2026-11-26): `pattern/set` uses retained messages + QoS1 + persistent session; "revoke" = publish default/previous pattern; persisted pattern gets a TTL so a revoked pattern cannot resurrect forever on an offline Pi.
- safety caps (review 2026-11-26 + alpha2): validated on console AND kubusd. strobe frequency < 3 Hz, global brightness cap, max message size, max `colors` list length (512 MB Pi). concurrent publishes = last-write-wins. sequence bounds (alpha2): max 20 steps per sequence, min step duration 0.5 s, max total duration 10 min; every step validated individually with the per-primitive caps.
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
- ? where the old Python 2.7 code lives — port behavior from it if Steven provides it (not found in the local dev tree).
- ? console hosting details (server IP/domain) — TBD, config at install.
- primitives settled (alpha2): rainbow, pulse, fade, chase, holiday, off, random/fire/sparkle, hue sweep/sine blend, strobe/police, knight-rider/sweep, static white/dim. sign = fixed hammer animation, not user-selectable.

## §I

- kubusd env (`.env` / `.env.example`): `MQTT_BROKER`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `PAYLOAD_KEY` (shared secret), `PIGPIOD_HOST`, `PIGPIOD_PORT`, GPIO pin map (9 PWM + 5 sign, e.g. `PIN_R1=…`), `SIGN_SCHEDULE` (json), `SQLITE_PATH`, log level.
- kubusd CLI: `kubusd run` (daemon, systemd), `kubusd sim` (simulator mode, ANSI output), `kubusd smoke` (hardware smoke test), `--config .env`.
- kubusd MQTT subscribe topics: `lichtfabriek/pattern/set` (set/activate pattern; retained + QoS1 + persistent session), `lichtfabriek/sign/set` (on/off override, admin only), `lichtfabriek/sign/schedule` (schedule update, admin only), `lichtfabriek/control` (generic). payload = JSON, encrypted with shared key (AEAD + nonce + counter + key_id).
- pattern payload shape (alpha2): `{key_id, counter, ts, topic_aad, pattern_id, pattern_hash, steps: [{cubes: {0: {primitive, params} | null, 1: ..., 2: ...}, duration_s}]}`. legacy single-primitive messages `{primitive, params}` still accepted → converted to one step (all cubes). NO `meta.ip`/username in payload (privacy, V19); console DB holds title/creator/description/created_ts/ip, Pi logs pattern_id + pattern_hash.
- kubusd SQLite tables: `patterns` (last-good + history), `sign_state` (schedule + override), `audit` (received messages, invalid attempts).
- kubusd systemd: unit file `deploy/kubusd.service`, install script `deploy/install.sh` (pulls release tarball from GitHub, installs deps, enables service). pigpiod as separate host service.
- console env: `MQTT_BROKER`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `PAYLOAD_KEY`, `KEY_ID`, `SECRET_KEY` (flask sessions), `SQLITE_PATH`, `ADMIN_PASSWORD` (forced change on first login), `TZ`.
- console web routes: login; patterns (create, activate, list, my patterns); admin (users, audit view, revoke/disable live pattern, ban IP, audit log); visualizer (alpha2): live in-browser preview of 3 cubes + 5 sign outputs while authoring — JS renderer in `console/static/` + `console/templates/`, primitive math mirrored from `kubusd/engine.py` (single source noted in comments).
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
V8: version `v<year>.<month>_<minor>.<bugfix>` (+ optional `-(alpha|beta|rc)<n>`), regex `^v\d{2}\.\d{2}_\d+\.\d+(-(alpha|beta|rc)\d+)?$`; one version for both services; every release (pre-release AND final) is merged devel → master with `--no-ff` and tagged on master; VERSION baked into release artifacts.
V9: payload encryption = AEAD (ChaCha20-Poly1305 via PyNaCl, fallback AES-GCM), random nonce, topic as AAD, `key_id` in every message; key never in git, only `.env` (`.env.example` has placeholder); console key injected via `env_file`/secrets, never in compose.yaml.
V10: deploy via systemd + install script from GitHub release, SHA256-verified tarball, previous release kept for rollback; idempotent; works offline after install.
V11: no self-registration; accounts created by admin only.
V12: crypto AEAD-only + replay counter (V2/V9).
V13: replay protection: monotonic counter + timestamp window; kubusd persists last-accepted counter, rejects lower (V2).
V14: safety caps: strobe < 3 Hz, global brightness cap, max message size, max `colors` length, last-write-wins for concurrent publishes. alpha2: per-step validation + sequence bounds — max 20 steps, min step 0.5 s, max total 10 min.
V21: (alpha2) a pattern step addresses cubes independently; unspecified cubes persist their previous step's settings; first step default = off.
V22: (alpha2) legacy single-primitive pattern messages are accepted and treated as a one-step sequence (all cubes) — backward compatible.
V23: (alpha2) the Console visualizer renders the same primitives/params/sequence semantics as kubusd (mirrored math, cross-checked by tests).
V24: cube index → physical position: cube 0 = TOPMOST IBC tank, 1 = middle, 2 = bottom; visualizer, ANSI sim, console editor and field wiring all follow this mapping.
V15: `pattern/set` retained + QoS1 + persistent session; revoke = publish default/previous pattern; persisted pattern TTL (no resurrection offline).
V16: audit ring buffer (capped rows), rate-limited invalid logging; SQLite WAL + synchronous=FULL, corruption → rename+recreate+default show.
V17: kubusd health: pigpiod + MQTT reconnect/healthcheck, render-loop watchdog, `Restart=always` + `WatchdogSec` in unit.
V18: sign clock: unsynced clock → defined default state; `TZ` in .env; override expiry; sign/schedule messages console-admin only.
V19: privacy: posting IP + username never in MQTT payload; console DB only; kubusd logs pattern_id + pattern_hash.
V20: no absolute/host-specific paths in the repo (no /home/, /mnt/c, /opt/..., /etc/..., /var/lib/...) — config defaults are relative (e.g. `./data/kubusd.db`), systemd unit is a template filled at install time, install prefix chosen by the installer, never hard-coded.

## §T

id|status|task|cites
T1|x|repo scaffold: git flow master/devel, README, RELEASING.md, AGENTS.md, .gitignore, .env.example, compose.yaml|C
T2|x|kubusd config loader (.env) + pin map + SQLite init (WAL + FULL, ring-buffer audit)|V1,V3,V16,I.kubusd-env
T3|x|kubusd animation engine: primitives + render loop + safety caps|V1,V4,V14
T4|x|kubusd pigpio driver (9 PWM + 5 out) + simulator mode (ANSI) + health/reconnect|V1,V4,V17
T5|x|kubusd MQTT: subscribe, AEAD decrypt, replay counter, validate, apply pattern / sign set / schedule; audit log|V2,V12,V13,V16
T6|x|kubusd persistence: last-good pattern + TTL + schedule + override + corruption handling|V3,V5,V15
T7|x|kubusd systemd unit (Restart, WatchdogSec) + install.sh (SHA256 + rollback)|V8,V10,V17
T8|x|console: Flask app, session auth, admin accounts, forced first-login password change|V11
T9|x|console: patterns (create, activate, list), post-hoc audit view, revoke/disable, IP capture (DB only)|V6,V7,V19
T10|x|console: MQTT publish (AEAD + counter + retained + QoS1), rate limit, ban|V7,V9,V13,V14,V15
T11|x|console UI: login, patterns page, admin page, audit log; Docker build (secrets for key)|V7,V9,V19
T12|x|tests: kubusd unit (engine, crypto, replay, validation, persistence) in simulator mode; console unit; hardware smoke script|V1,V2,V4,V12,V13
T13|x|release v1 (alpha1): versioning wired to git describe, VERSION baked, devel → master, tag v26.11_0.0-alpha1, docs|V8,C.versioning
T14|.|field deploy on real Pi + cubes: pin map, broker creds, TZ, schedule; smoke test on hardware|V1,V5,V10,V18
T15|.|(alpha2) kubusd engine: sequence model — steps list, per-step per-cube primitives, persist-unspecified-cubes, step timing + loop|V14,V21,V22
T16|.|(alpha2) new primitives: random/fire/sparkle, hue sweep/sine blend, strobe/police, knight-rider/sweep, static white/dim|V1,V4,V14
T17|.|(alpha2) shared schema: steps payload + legacy single-primitive conversion + sequence bounds validation|V14,V22,I.pattern-payload
T18|.|(alpha2) console: sequence authoring UI (steps + per-cube editor) + publish|V21,V22
T19|.|(alpha2) console visualizer: live in-browser preview of cubes + sign (JS, mirrored primitive math)|V23
T20|.|(alpha2) tests: sequence engine, legacy conversion, bounds, new primitives, visualizer cross-check|V14,V21,V22,V23
T21|.|(alpha2) release v26.11_0.0-alpha2: VERSION bump, CHANGELOG, devel → master, tag|V8,C.versioning

## §B

id|date|cause|fix
