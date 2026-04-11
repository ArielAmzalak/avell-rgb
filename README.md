# Avell RGB

Utilitário GTK4/libadwaita pra controlar iluminação RGB do teclado e da light bar
inferior em notebooks Avell (chip ITE 8291 + EC ITE 8233), com presets, agenda
por horário e modo solar.

**Status:** em projeto. Veja
[`docs/superpowers/specs/2026-04-10-avell-rgb-gui-design.md`](docs/superpowers/specs/2026-04-10-avell-rgb-gui-design.md)
para o design spec completo.

## Pré-requisitos de sistema

- Linux com kernel >= 6.1
- `ite8291r3-ctl` no PATH (keyboard RGB)
- Módulo kernel `ite_8291_lb` carregado (light bar)
- `/sys/class/leds/rgb:lightbar/{brightness,multi_intensity}` com escrita
  permitida pro usuário
- Python 3.11+, `python3-gi`, `gir1.2-adw-1`

## Licença

MIT.
