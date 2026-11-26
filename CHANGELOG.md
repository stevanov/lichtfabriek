# Changelog

All notable changes to Lichtfabriek. Format: reverse chronological.
Versions follow `RELEASING.md` (v26.11_0.0-alphaN → … → v26.11_0.0).

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
