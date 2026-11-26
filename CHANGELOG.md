# Changelog

All notable changes to Lichtfabriek. Format: reverse chronological.
Versions follow `RELEASING.md` (v26.11_0.0-alphaN → … → v26.11_0.0).

## v26.11_0.0-alpha1 — 2026-11-26

- Initial build of `kubusd` (Pi daemon) + `console` (Flask web app).
- Design: grill + ghce review 2026-11-26 (gpt-6-luna, claude-sonnet-5.5),
  V1–V20 in SPEC.md.
- Security (privacy review): reject placeholder `SECRET_KEY`/`ADMIN_PASSWORD`;
  guard open redirect on `?next=`.
- Migrated to GitHub (public), history rewritten: no private host refs,
  author = stevanov.
- Alpha/beta/rc pre-release ladder documented (RELEASING.md).
