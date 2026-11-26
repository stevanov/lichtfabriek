#!/usr/bin/env bash
# Lichtfabriek kubusd installer for the Pi Zero W (armv6, systemd).
# Pulls a release tarball from GitHub, verifies SHA256 (V10), installs into a
# configurable prefix, fills the systemd unit template, enables the service.
#
# No absolute/host paths are hard-coded in this repo — the install prefix is
# resolved here, at install time (SPEC V20). Public repo: releases download
# without auth.
set -euo pipefail

# ---- configurable, no private defaults baked in ----
PREFIX="${KUBUSD_PREFIX:-/opt/lichtfabriek}"
RUN_USER="${KUBUSD_USER:-lichtfabriek}"
BASE="${KUBUSD_RELEASE_URL:-https://github.com/stevanov/lichtfabriek/releases/download}"
SYSTEMD_DIR="${KUBUSD_SYSTEMD_DIR:-/etc/systemd/system}"
VERSION="${KUBUSD_VERSION:?set KUBUSD_VERSION, e.g. v26.11_0.0-alpha1}"
TARBALL="lichtfabriek-${VERSION}.tar.gz"
SHAFILE="lichtfabriek-${VERSION}.sha256"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> downloading release ${VERSION} (public GitHub build)"
curl -fsSL -o "$TMP/$TARBALL" "$BASE/$VERSION/$TARBALL"
curl -fsSL -o "$TMP/$SHAFILE" "$BASE/$VERSION/$SHAFILE"

echo "==> verifying sha256 (V10)"
( cd "$TMP" && sha256sum -c "$SHAFILE" )

echo "==> installing to ${PREFIX}"
if id "$RUN_USER" &>/dev/null; then
  echo "user ${RUN_USER} exists"
else
  echo "creating user ${RUN_USER}"
  useradd --system --home-dir "$PREFIX" --shell /usr/sbin/nologin "$RUN_USER"
fi
install -d -o "$RUN_USER" -g "$RUN_USER" "$PREFIX"
rm -rf "$PREFIX.new"
mkdir -p "$PREFIX.new"
tar -xzf "$TMP/$TARBALL" -C "$PREFIX.new"
# keep one previous copy for rollback (RELEASING.md)
[ -d "$PREFIX.prev" ] && rm -rf "$PREFIX.prev"
[ -d "$PREFIX" ] && mv "$PREFIX" "$PREFIX.prev" || true
mv "$PREFIX.new" "$PREFIX"
chown -R "$RUN_USER:$RUN_USER" "$PREFIX"

echo "==> venv + deps"
python3 -m venv "$PREFIX/.venv"
"$PREFIX/.venv/bin/pip" install --no-cache-dir -r "$PREFIX/requirements.txt"

echo "==> env file"
ENV_FILE="$PREFIX/kubusd.env"
if [ ! -f "$ENV_FILE" ]; then
  cp "$PREFIX/kubusd/.env.example" "$ENV_FILE"
  chown "$RUN_USER:$RUN_USER" "$ENV_FILE"
  echo "!!! fill in ${ENV_FILE} (PAYLOAD_KEY must match the console)"
fi

echo "==> systemd unit"
sed -e "s|__KUBUSD_USER__|${RUN_USER}|g" \
    -e "s|__KUBUSD_INSTALL_DIR__|${PREFIX}|g" \
    -e "s|__KUBUSD_ENV_FILE__|${ENV_FILE}|g" \
    -e "s|__KUBUSD_PYTHON__|${PREFIX}/.venv/bin/python|g" \
    "$PREFIX/deploy/kubusd.service" > "${SYSTEMD_DIR}/kubusd.service"
systemctl daemon-reload
systemctl enable kubusd
systemctl restart kubusd
echo "==> kubusd ${VERSION} installed. status:"
systemctl status kubusd --no-pager || true
