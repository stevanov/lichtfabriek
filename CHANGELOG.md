# Changelog

All notable changes to Lichtfabriek. Format: reverse chronological.
Versions follow `RELEASING.md` (v26.11_0.0-alphaN → … → v26.11_0.0).

## Unreleased (alpha4 hardening + i18n)

- **Full-codebase review fixes** (gemini-4-argon delta review ×6, Kimi K3.1
  Pro blind review ×21 real, Claude Sonnet 5.5 full sweep — cross-checked):
  - Deployment: `Type=notify` watchdog fed from the render loop (a wedged
    loop restarts, a healthy one is never killed); install.sh preserves
    `kubusd.env` + SQLite data across upgrades (chmod 600) and refuses to
    start with a blank PAYLOAD_KEY; clean SIGTERM zeroes the LEDs.
  - Crash-proofing: per-primitive color arity (sine needs 2) + integer seed
    validation; render errors fall back to off instead of crash-looping on
    resume; persistence resolved by replay from off (matches the preview);
    alpha-DB migrations rebuild legacy tables into canonical steps.
  - Protocol: per-topic replay counters; retained/unsynced-clock messages
    skip the timestamp window; oversize rejected at the console; the
    never-implemented control topic removed; periodic TTL sweep.
  - Security: CSRF token on every POST; one rate-limit bucket covering
    login/activate/revoke; XFF last-hop only; forced password change is now
    a hard guard; `UnicodeDecodeError` → Reject; rate-limited audit writes.
  - Parity: seeded primitives share one LCG across Python + JS (preview now
    honors `seed`, holiday matches); primitive math extracted to
    `console/static/viz.js` (single source) with an exact node-parity test;
    pigpio auto-reconnect; strobe floor strictly < 3 Hz; paho pinned <2.
- **Dutch/English UI toggle** (alpha4 feature): lightweight dict catalog
  (`console/i18n.py`), EN default, cookie-persisted, console only.

## v26.11_0.0-alpha3 — 2026-11-26

- **Sign loop confirmed** (SPEC §C, `docs/sign-layout.svg`): hammer pivots at
  the bottom of its handle on the right of the anvil, swings CCW to the left,
  sparks flash up-left, then JUMPS back upright. Cycle ~3 s; the board never
  goes dark. Constants in `kubusd/scheduler.py`; the sign runs on its own
  clock in the visualizer.
- **Animator page** reworked to the physical layout: step editor left,
  physical rig right (hammer board on top, 3 true-cube IBC tanks stacked
  below). Cube 1 (index 0) = topmost tank (SPEC V24).
- **Step editor columns**: cube / primitive / color / brightness / speed /
  offset, with a per-cube **color picker** (single-color primitives only),
  **speed** (uniform multiplier, 1 = normal) and **offset** (phase shift as a
  fraction of one animation cycle — stagger cubes for a knight/chase sweep).
  Switching a primitive keeps the cube's speed/brightness/offset.
- **Sparkle is multi-color**: each flash picks a random palette color.
- **Primitive reference table** at the bottom of the page.
- **ANSI simulator** matches the same layout (sign LEDs top, cube stack right).
- **`.env.example`** added for kubusd + console (the contract referenced by
  install.sh/config/README/SPEC, V9/V20).
- **Console theme**: dark/light toggle + anvil favicon.
- **Gemini-4-argon review fixes** (6 findings): chase flash-rate cap + engine/
  preview parity + offset; no dead speed range (fire/random/fade unclamped);
  admin-password placeholder now rejected; offset full-cycle no-op; editor
  keep-row sliders disabled; SIM_COLS actually read.

## v26.11_0.0-alpha2 — 2026-11-26

- Patterns are now **sequences of steps** (looped), each with per-cube
  independent primitives (SPEC V21/V22). Cubes not set in a step persist their
  previous step's look.
- **5 new primitives**: random, fire, sparkle, huesweep, sine, strobe, police,
  knight, static (15 total).
- **Live visualizer** in the Console: 3 cubes + sign animate in the browser
  while authoring (mirrors kubusd engine, V23).
- Sequence safety bounds: max 20 steps, min step 0.5 s, max total 10 min (V14).
- Legacy single-primitive patterns still accepted (V22).

## v26.11_0.0-alpha1 — 2026-11-26

- Initial build of `kubusd` (Pi daemon) + `console` (Flask web app).
- Design: grill + ghce review 2026-11-26 (gpt-6-luna, claude-sonnet-5.5),
  V1–V20 in SPEC.md.
- Security (privacy review): reject placeholder `SECRET_KEY`/`ADMIN_PASSWORD`;
  guard open redirect on `?next=`.
- Migrated to GitHub (public), history rewritten: no private host refs,
  author = stevanov.
- Alpha/beta/rc pre-release ladder documented (RELEASING.md).
