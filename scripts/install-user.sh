#!/bin/sh
set -e

cd "$(dirname "$0")/.."

echo "==> Instalando avell-rgb via pipx"
pipx install --force --system-site-packages .

echo "==> Instalando .desktop entry e ícone"
install -Dm644 data/io.github.avellrgb.Avell.desktop \
    "$HOME/.local/share/applications/io.github.avellrgb.Avell.desktop"
install -Dm644 data/io.github.avellrgb.Avell.svg \
    "$HOME/.local/share/icons/hicolor/scalable/apps/io.github.avellrgb.Avell.svg"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo "==> Instalando autostart entry"
mkdir -p "$HOME/.config/autostart"
cp data/avell-rgb-autostart.desktop "$HOME/.config/autostart/"
echo "✓ autostart entry installed"

echo "==> Instalando systemd user service"
install -Dm644 data/avell-rgb-daemon.service \
    "$HOME/.config/systemd/user/avell-rgb-daemon.service"
systemctl --user daemon-reload
systemctl --user enable --now avell-rgb-daemon.service

echo
echo "==> Pronto. Abra 'Avell RGB' no menu de aplicações."
echo "==> Daemon status: $(systemctl --user is-active avell-rgb-daemon.service)"
