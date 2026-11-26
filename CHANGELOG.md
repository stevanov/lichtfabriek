# Changelog

All notable changes to Lichtfabriek. Format: reverse chronological.
Versions follow `RELEASING.md` (v26.11_0.0-alphaN → … → v26.11_0.0).

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
