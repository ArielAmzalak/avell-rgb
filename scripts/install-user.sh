#!/bin/sh
set -e

cd "$(dirname "$0")/.."

echo "==> Garantindo ite8291r3-ctl (backend do teclado, PID 0x600B do Avell STORM 570 TI)"
ITE_SRC="$HOME/src/ite8291r3-ctl"
ITE_FILE="$ITE_SRC/ite8291r3_ctl/ite8291r3.py"
if [ ! -d "$ITE_SRC" ]; then
  git clone --depth 1 https://github.com/pobrn/ite8291r3-ctl "$ITE_SRC"
fi
# O teclado usa o product ID 0x600B; garante que esteja na lista de forma
# idempotente (protege caso o upstream volte a remover esse ID no futuro).
if ! grep -q "0x600B" "$ITE_FILE"; then
  sed -i 's/\(PRODUCT_IDS = \[[^]]*\)\]/\1, 0x600B]/' "$ITE_FILE"
fi
# Reinstala do clone local (imune a cache de wheel do pip e a quebra de venv
# por interpretador orfao apos upgrade do Python). pipx install --force falha
# quando o interpretador do venv sumiu, por isso removemos antes.
pipx uninstall ite8291r3-ctl >/dev/null 2>&1 || true
rm -rf "$HOME/.local/share/pipx/venvs/ite8291r3-ctl"
PIP_NO_CACHE_DIR=1 pipx install "$ITE_SRC"

echo "==> Instalando avell-rgb via pipx"
# --system-site-packages e essencial: a GUI usa gi/GTK4/Adw/AppIndicator do
# sistema. Remove antes para reparar venv com interpretador orfao (pos-upgrade).
pipx uninstall avell-rgb >/dev/null 2>&1 || true
rm -rf "$HOME/.local/share/pipx/venvs/avell-rgb"
pipx install --system-site-packages .

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

echo "==> Verificando permissões de escrita da light bar"
LB_SYS=/sys/class/leds/rgb:lightbar
if [ -w "$LB_SYS/brightness" ] && [ -w "$LB_SYS/multi_intensity" ]; then
  echo "✓ light bar gravável ($LB_SYS)"
else
  echo
  echo "############################################################"
  echo "#  ATENÇÃO: light bar SEM permissão de escrita             #"
  echo "#  ($LB_SYS/{brightness,multi_intensity})                  #"
  echo "#  O daemon vai rodar, mas a barra ficará morta até você   #"
  echo "#  instalar (uma única vez, como root) os dois arquivos    #"
  echo "#  versionados em data/. Rode:                             #"
  echo "############################################################"
  echo
  echo "  sudo install -Dm644 data/99-avell-lightbar.rules /etc/udev/rules.d/99-avell-lightbar.rules"
  echo "  sudo install -Dm644 data/lightbar.conf /etc/tmpfiles.d/lightbar.conf"
  echo "  sudo udevadm control --reload"
  echo "  sudo udevadm trigger --subsystem-match=leds"
  echo "  sudo systemd-tmpfiles --create /etc/tmpfiles.d/lightbar.conf"
  echo
  if sudo -n true 2>/dev/null && [ -t 0 ]; then
    printf "sudo sem senha disponível — executar os comandos acima agora? [s/N] "
    read -r LB_RESP || LB_RESP=""
    case "$LB_RESP" in
    [sSyY]*)
      sudo -n install -Dm644 data/99-avell-lightbar.rules /etc/udev/rules.d/99-avell-lightbar.rules \
        && sudo -n install -Dm644 data/lightbar.conf /etc/tmpfiles.d/lightbar.conf \
        && sudo -n udevadm control --reload \
        && sudo -n udevadm trigger --subsystem-match=leds \
        && sudo -n systemd-tmpfiles --create /etc/tmpfiles.d/lightbar.conf \
        && echo "✓ permissões da light bar instaladas" \
        || echo "✗ falha ao aplicar — rode os comandos acima manualmente"
      ;;
    esac
  fi
fi

echo
echo "==> Pronto. Abra 'Avell RGB' no menu de aplicações."
echo "==> Daemon status: $(systemctl --user is-active avell-rgb-daemon.service)"
