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
- Permissões de escrita na light bar — veja a seção
  [Permissões da light bar](#permissões-da-light-bar) abaixo
- Python 3.11+, `python3-gi`, `gir1.2-adw-1`

## Permissões da light bar

Por padrão só root escreve em
`/sys/class/leds/rgb:lightbar/{brightness,multi_intensity}`. O repositório
versiona os dois arquivos que abrem essa permissão de forma persistente:

- [`data/99-avell-lightbar.rules`](data/99-avell-lightbar.rules) — regra udev
  (aplica `chmod` quando o LED aparece)
- [`data/lightbar.conf`](data/lightbar.conf) — entrada tmpfiles.d (reaplica a
  cada boot)

O `scripts/install-user.sh` verifica se a escrita está liberada e, se não
estiver, imprime os comandos `sudo` exatos para instalar os dois arquivos
(passo único por máquina).

## Licença

MIT.
