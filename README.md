# Lichtfabriek

Lichtfabriek laat de 3 RGB-kubussen (1 m³ / 1000 liter) en het analoge LED-bord van
Stadsfabriek Alkmaar branden. Twee diensten in één monorepo:

| Dienst | Waar | Wat |
|---|---|---|
| **kubusd** | Raspberry Pi Zero W v1.1 (armv6, headless) | Daemon die de 9 PWM-kanalen (3 strips × RGB) + 5 aan/uit-uitgangen van het bord aanstuurt via pigpio. Ontvangt patronen over MQTT, animeert autonoom offline. |
| **console** | jouw server (Docker) | Flask-webapp: gebruikers maken patronen en publiceren ze direct; admins zien wie wat publiceerde en kunnen live patronen intrekken of IP's blokkeren. |

Patronen = ingebouwde primitives + parameters (regenboog, pulse, fade, chase,
feestthema's, bord-sequenties). Via MQTT naar kubusd gestuurd, payload
versleuteld (AEAD + replay-teller), broker is configureerbaar (v1 = publieke
broker).

## Structuur

```
kubusd/     de Pi-daemon (headless)
console/    de Flask-webapp
shared/     crypto + message schema (door beide gebruikt)
deploy/     systemd unit + install.sh voor de Pi
tests/      unit tests
SPEC.md     het ontwerp (grill + review 2026-11-26)
```

## Vereisten

- Python ≥ 3.11 (Pi: Raspberry Pi OS, `pip install paho-mqtt pynacl pigpio`)
- pigpio daemon draait op de Pi host (`sudo systemctl enable --now pigpiod`)
- Docker + compose (alleen voor dev + console)
- GitHub release om de Pi te installeren (`deploy/install.sh`)

## Snel starten (dev, simulator)

kubusd heeft een simulatiemodus: geen hardware, ANSI-render van strips + bord.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cp kubusd/.env.example .env          # vul MQTT_BROKER + PAYLOAD_KEY in
.venv/bin/python -m kubusd sim       # of: kubusd run (echte pigpio)
```

Console lokaal:

```bash
cp console/.env.example console/.env
.venv/bin/python -m console          # http://localhost:5001
```

Of met Docker: `docker compose up --build`.

## Installeren op de Pi

```bash
curl -fsSL https://github.com/stevanov/lichtfabriek/releases/download/<tag>/install.sh | bash
```

Zie `deploy/install.sh` en `deploy/kubusd.service`. Versies: `RELEASING.md`.
Werken met anderen: `AGENTS.md`.
