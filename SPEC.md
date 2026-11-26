# SPEC — Lichtfabriek: Pi Zero W animates 3 RGB cubes + LED sign, driven by MQTT patterns

Grill 2026-11-26. Two services in one monorepo: `kubusd` (headless Pi daemon) + `console` (Flask web app). Git flow master/devel. GitHub: TBD url.

## §G

On a Pi Zero W v1.1, run a headless daemon (`kubusd`) that drives 3 PWM RGB strips (in 100 L cubes) + 5 on/off outputs (analog LED sign), animating patterns received over MQTT (payload-encrypted), with autonomous fallback when offline; a Flask web app (`console`) lets makerspace users create patterns, admins approve/manage them, and publishes approved patterns to MQTT.

## §C

- hardware: Pi Zero W v1.1 (armv6, single-core, 512 MB RAM, 26 usable GPIO). 3 RGB strips = 9 PWM channels + 5 on/off sign outputs = 14 signals.
- PWM: pigpio daemon (pigpiod) runs on the Pi host; kubusd connects over its socket. Hardware PWM impossible for 9 channels (2 channels on BCM2835). software PWM rejected (jitter, CPU on single core).
- deployment Pi: systemd unit + install script pulled from a GitHub release. Docker on the Pi: NO (armv6 pain, too heavy). kubusd headless, no GUI.
- deployment dev + console: Docker (docker compose). console is the only web app; it runs on Steven's server.
- versioning: `v26.11_38.0` = `v<year>.<month>_<minor>.<bugfix>` generated via `git describe`. one version line for both services. (format confirmed 2026-11-26: vYYYY.MM_MM.bugfix)
- repo: monorepo, two services (`pi/` + `console/`), git flow: feature → devel → master, `--no-ff`. releases tagged on master.
- animation model: built-in primitives + params over MQTT. Pi ships primitives (rainbow, pulse, fade, chase, holiday themes, sign sequences); messages name primitive + params (colors, speed, intensity). no raw frame data in v1.
- offline: persist last-good pattern in SQLite; on first boot run built-in default show; MQTT best-effort (subscribe when broker reachable, keep animating when not). survives reboot.
- sign: fixed always-on animation of the 5 outputs, 24/7, plus time-based scheduler (on/off times) AND manual MQTT on/off override. schedule configurable via .env AND via MQTT (runtime override wins). (scheduler restrict-user-publishing idea NOT in v1.)
- config Pi: `.env` = static config (MQTT broker URL + creds, shared payload key, GPIO pin map, host paths). SQLite = runtime state (last pattern, schedule overrides, audit). `.env.example` documents keys. no hand-edited JSON.
- MQTT broker: configurable via `.env`; v1 ships over a public broker. payload encryption only (shared secret key in .env, e.g. HMAC/AES), no TLS requirement in v1.
- language: Python 3 everywhere. Pi: paho-mqtt + pigpio client + sqlite3 (stdlib). console: Flask (accounts, session auth, admin page, SQLite, paho-mqtt publisher). single codebase, two entry points.
- verification: simulator mode in kubusd (renders strips/sign as ANSI/terminal, no pigpio needed) + unit tests + hardware smoke test script for the real Pi.
- publish workflow: any logged-in user can create AND activate patterns immediately; admin approval is post-hoc audit (see who published what, revoke/disable a live pattern). every pattern carries metadata: title, creator username, description, created timestamp, posting IP address (for rate limiting + banning).
- accounts: admin-created accounts (username + password) from the console admin page; no self-registration, no LDAP/OAuth. admin can approve/reject, revoke live patterns, ban IPs.
- edge handling: kubusd validates every message (schema + payload auth). invalid/forged → dropped + logged with sender metadata, never interrupt running pattern, stay on last-good. console rate-limits publish endpoints; admin can ban IP.
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
- kubusd MQTT subscribe topics: `lichtfabriek/pattern/set` (set/activate pattern), `lichtfabriek/sign/set` (on/off override), `lichtfabriek/sign/schedule` (schedule update), `lichtfabriek/control` (generic). payload = JSON, encrypted with shared key, includes pattern metadata when applicable.
- pattern payload shape: `{primitive, params:{colors, speed, intensity}, meta:{title, creator, description, created_ts, ip}}`.
- kubusd SQLite tables: `patterns` (last-good + history), `sign_state` (schedule + override), `audit` (received messages, invalid attempts).
- kubusd systemd: unit file `deploy/kubusd.service`, install script `deploy/install.sh` (pulls release tarball from GitHub, installs deps, enables service). pigpiod as separate host service.
- console env: `MQTT_BROKER`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`, `PAYLOAD_KEY`, `SECRET_KEY` (flask sessions), `SQLITE_PATH`, `ADMIN_PASSWORD`.
- console web routes: login; patterns (create, activate, list, my patterns); admin (users, approval queue, revoke/disable live pattern, ban IP, audit log); simulator preview (reuse kubusd sim rendering? or JS preview).
- docker: `compose.yaml` at repo root — console service (build from `console/`), dev-only kubusd simulator service. Pi deploy via systemd, not docker.
- versioning: `git describe` produces `v<year>.<month>_<minor>.<bugfix>`; release = tag on master; both services report the same version.

## §V

V1: kubusd runs 9 PWM channels + 5 sign outputs via pigpio socket, no root GPIO access in-process.
V2: MQTT message schema + payload auth validated before apply; invalid/forged → logged (with metadata), never interrupts current pattern.
V3: offline/reboot: last-good pattern resumes from SQLite; first boot → built-in default show.
V4: simulator mode runs the same animation engine without pigpio (headless, ANSI output) — unit-testable in CI.
V5: sign has fixed animation + schedule + manual override; MQTT override wins over schedule; both configurable.
V6: every published pattern records title, creator username, description, created_ts, posting IP.
V7: console: admin can revoke/disable any live pattern; ban IP stops publishing; rate limit on publish endpoints.
V8: version `v<year>.<month>_<minor>.<bugfix>` from git describe; one version for both services; releases only on master via tag.
V9: payload encryption with shared key at rest/transit; key never in git, only `.env` (`.env.example` has placeholder).
V10: deploy via systemd + install script from GitHub release; idempotent; works offline after install.
V11: no self-registration; accounts created by admin only.

## §T

id|status|task|cites
T1|.|repo scaffold: git flow master/devel, README, RELEASING.md, AGENTS.md, .gitignore, .env.example, compose.yaml|C
T2|.|kubusd config loader (.env) + pin map + SQLite init (patterns, sign_state, audit)|V1,V3,I.kubusd-env
T3|.|kubusd animation engine: primitives (rainbow, pulse, fade, chase, holiday, sign sequences) + render loop|V1,V4
T4|.|kubusd pigpio driver (9 PWM + 5 out) + simulator mode (ANSI)|V1,V4
T5|.|kubusd MQTT: subscribe, decrypt, validate, apply pattern / sign set / schedule; audit log|V2,V6
T6|.|kubusd persistence: last-good pattern + schedule + override in SQLite|V3,V5
T7|.|kubusd systemd unit + install.sh (GitHub release pull, idempotent)|V8,V10
T8|.|console: Flask app, session auth, admin-created accounts|V11
T9|.|console: patterns (create, activate, list), approval queue, revoke/disable, IP capture|V6,V7
T10|.|console: MQTT publish (encrypt + send pattern/sign/schedule), rate limit, ban|V7,V9
T11|.|console UI: login, patterns page, admin page, audit log; Docker build|V7,V9
T12|.|tests: kubusd unit (engine, validation, persistence) in simulator mode; console unit; hardware smoke script|V1,V4
T13|.|release v1: versioning wired to git describe, devel → master, tag, docs|V8,C.versioning
T14|.|field deploy on real Pi + cubes: pin map, broker creds, schedule; smoke test on hardware|V1,V5,V10

## §B

id|date|cause|fix
