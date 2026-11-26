# Lichtfabriek

Lichtfabriek drives the 3 RGB cubes (1 m³ / 1000 liter each) and the analog
LED sign at Stadsfabriek makerspace in Alkmaar. Two services in one monorepo:

| Service | Where | What |
|---|---|---|
| **kubusd** | Raspberry Pi Zero W v1.1 (armv6, headless) | Daemon driving the 9 PWM channels (3 strips × RGB) + 5 on/off sign outputs via pigpio. Receives patterns over MQTT, animates autonomously when offline. |
| **console** | your server (Docker) | Flask web app: users create patterns and publish them immediately; admins see who published what and can revoke live patterns or block IPs. |

Patterns are built-in primitives + parameters (rainbow, pulse, fade, chase,
holiday themes, sign sequences). They are pushed to kubusd over MQTT with
AEAD-encrypted payloads; the broker is configurable (v1 uses a public broker).

## Layout

```
kubusd/     the Pi daemon (headless)
console/    the Flask web app
shared/     crypto + message schema (used by both)
deploy/     systemd unit + install.sh for the Pi
tests/      unit tests
SPEC.md     the design (grill + review 2026-11-26)
```

## Requirements

- Python >= 3.11 (Pi: Raspberry Pi OS, `pip install paho-mqtt pynacl pigpio`)
- pigpio daemon running on the Pi host (`sudo systemctl enable --now pigpiod`)
- Docker + compose (dev and console only)
- A GitHub release to install the Pi (`deploy/install.sh`)

## Quick start (dev, simulator)

kubusd has a simulator mode: no hardware, ANSI render of strips + sign.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp kubusd/.env.example .env          # fill in MQTT_BROKER + PAYLOAD_KEY
.venv/bin/python -m kubusd sim       # or: kubusd run (real pigpio)
```

Console locally:

```bash
cp console/.env.example console/.env
.venv/bin/python -m console          # http://localhost:5001
```

Or with Docker: `docker compose up --build`.

## Notes for contributors

Initial build (grill + spec + scaffold + both services, 2026-11-26) was written
by the **DeepSeek V4 Flash 0731** model, with the design reviewed by two other
models (gpt-6-luna, claude-sonnet-5.5). Not all code is original: verify any
`from shared` imports and the deploy scripts against the SPEC before trusting
them blindly. See `AGENTS.md` for how to work in this repo.

## Install on the Pi

The repo is **private**, so releases are downloaded with a GitHub token
(fine-grained, `read:repository` only — create one under
Settings → Applications in GitHub). Install `pigpio` first:

```bash
sudo apt install -y pigpio
```

Then fetch and run the installer with the token and a release tag. Because the
repo is private, you cannot pipe `curl | bash` without auth — instead clone the
repo once with the token, or download `install.sh` from the GitHub web UI:

```bash
# from a clone (token grants read):
git clone https://github.com/stevanov/lichtfabriek.git
cd lichtfabriek
KUBUSD_TOKEN=<token> KUBUSD_VERSION=<tag> ./deploy/install.sh
```

Release tags look like `v26.11_38.0` (see `RELEASING.md`). The installer pulls
the release tarball + checksum from GitHub, verifies the SHA256 (V10), installs
into `KUBUSD_PREFIX`, and creates/updates the `kubusd` systemd unit. Fill in
the generated env file (`PAYLOAD_KEY` must match the console).
