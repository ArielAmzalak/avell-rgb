# Avell RGB v0.2 — Design Spec

## Overview

Redesign completo do avell-rgb: de app GTK com sidebar + daemon SIGHUP para arquitetura tray-centric com daemon D-Bus. Foco em zero-bug, responsividade instantânea e interface dark com cores dinâmicas.

**Hardware:** Avell 570 TI com teclado ITE 8291 (per-key RGB) e lightbar ITE 8233 via sysfs.

## Modos de operação

Quatro modos exclusivos, selecionáveis via tray ou janela:

| Modo | Comportamento |
|------|--------------|
| `fixed` | Cor fixa aplicada até o usuário mudar |
| `solar` | Interpola entre cor de dia e cor de noite baseado na elevação solar (astral). Recalcula a cada 60s |
| `effect` | Efeito do teclado (breathing, wave, random, etc.) com cor/velocidade configuráveis. Lightbar acompanha a cor do efeito em fixo |
| `off` | Teclado desligado, lightbar brightness 0 |

**Schedule eliminado.** Não existe mais faixas horárias. O modo solar cobre o caso de uso de transição dia/noite.

## Modelo de dados (Config v2)

```json
{
  "version": 2,
  "mode": "fixed",
  "color": "#00FFFF",
  "brightness": 30,
  "independent_colors": false,
  "keyboard_color": "#00FFFF",
  "keyboard_brightness": 30,
  "lightbar_color": "#00FFFF",
  "lightbar_brightness": 80,
  "effect": {
    "name": "breathing",
    "color": "#00FFFF",
    "speed": 5
  },
  "solar": {
    "latitude": -23.55,
    "longitude": -46.63,
    "day_color": "#8FF0A4",
    "night_color": "#FF7800",
    "day_brightness": 50,
    "night_brightness": 20
  },
  "presets": {
    "trabalho": { "color": "#00FFFF", "brightness": 30 },
    "noite": { "color": "#FF3300", "brightness": 10 }
  }
}
```

### Campos

- `version`: sempre 2. Config v1 é migrado automaticamente na leitura.
- `mode`: `"fixed"` | `"solar"` | `"effect"` | `"off"`
- `color`, `brightness`: cor e brilho unificados (teclado + lightbar). Brightness 0-50 vai direto pro teclado; pra lightbar, mapeado linearmente pra 0-100 (×2).
- `independent_colors`: quando `true`, usa `keyboard_color`/`keyboard_brightness` e `lightbar_color`/`lightbar_brightness` em vez de `color`/`brightness`.
- `effect`: configuração do efeito ativo. `name` é um dos `VALID_EFFECTS` existentes. Lightbar recebe a cor do efeito em modo fixo (sem efeito animado na lightbar, que não suporta).
- `solar`: configuração do modo solar. Mesma lógica do v0.1 (`astral` + interpolação por elevação) mas com tick de 60s em vez de 300s.
- `presets`: mapa nome → `{color, brightness}`. Presets são simplificados: uma cor e um brilho. Aplicar um preset seta `mode=fixed`, `color` e `brightness`.

### Removidos do v1

- `manual_state`, `manual_paused`: não existe mais estado temporário.
- `schedule`: eliminado.

### Migração v1 → v2

Ao ler config v1:
1. Pega o primeiro preset como `color`/`brightness` defaults
2. Converte `mode: "schedule"` → `mode: "fixed"`
3. Simplifica presets (extrai cor e brilho do `DeviceState`)
4. Descarta `manual_state`, `manual_paused`, `schedule`
5. Salva como v2

## Daemon

### Processo

Roda como systemd user service (`avell-rgb-daemon.service`). Mesmo `ExecStart` que v0.1 mas com loop reescrito.

### Interface D-Bus

Bus name: `io.github.avellrgb.Daemon`
Object path: `/io/github/avellrgb/Daemon`
Interface: `io.github.avellrgb.Daemon`

**Methods:**

| Method | Signature | Descrição |
|--------|-----------|-----------|
| `SetMode(mode)` | `s → ()` | Muda o modo e aplica imediatamente |
| `SetColor(hex, brightness)` | `si → ()` | Seta cor/brilho unificados, muda pra mode=fixed, aplica. Se `independent_colors=true`, seta ambos (teclado e lightbar) para a mesma cor e desativa `independent_colors` |
| `SetEffect(name, color, speed)` | `ssi → ()` | Seta efeito, muda pra mode=effect, aplica |
| `ApplyPreset(name)` | `s → ()` | Carrega preset, seta mode=fixed, aplica |
| `GetState()` | `() → (sssi)` | Retorna (mode, color, effect_name, brightness) |
| `ListPresets()` | `() → a(ssi)` | Retorna array de (name, color, brightness) |

**Signals:**

| Signal | Signature | Descrição |
|--------|-----------|-----------|
| `StateChanged(mode, color, brightness)` | `ssi` | Emitido após qualquer mudança de estado |

### Loop principal

```
async def run():
    dbus = export_dbus_interface(core)
    while True:
        state = core.compute_desired_state()
        core.apply(state)
        dbus.emit_state_changed(core.config)
        if core.config.mode == "solar":
            await wait_for_dbus_or_timeout(60)
        else:
            await wait_for_dbus_call()  # dorme até receber chamada
```

Cada method D-Bus seta um `asyncio.Event` que acorda o loop. O loop recalcula, aplica e volta a dormir.

### Persistência

O daemon é o **único escritor** do config.json. Após cada mudança via D-Bus:
1. Atualiza `self.config` em memória
2. Grava config.json atomicamente (write → fsync → rename)
3. Aplica no hardware
4. Emite `StateChanged`

### Backends

Mesmos do v0.1, sem alteração:
- `KeyboardBackend`: wrapper de `ite8291r3-ctl`
- `LightbarBackend`: sysfs `/sys/class/leds/rgb:lightbar/`

Adição: cada `apply()` captura exceções e loga erro em vez de crashar. Retry automático no próximo tick.

## Tray (AppIndicator)

### Processo

Mesmo processo da GUI app. A app inicia em modo tray (sem janela) via flag `--tray` ou por padrão quando lançada pelo autostart.

Entry point: `avell-rgb-gui` (mesmo binário).

```
if --tray or autostart:
    cria AppIndicator, não mostra janela
else:
    cria AppIndicator + mostra janela
```

### Dependência

`gir1.2-ayatanaappindicator3-0.1` (ou `gir1.2-appindicator3-0.1` no Ubuntu). AppIndicator3 via GObject introspection.

### Menu

```
┌─────────────────────────────┐
│  ● Fixo                    │  RadioMenuItem (modo atual)
│  ○ Solar                   │  RadioMenuItem
│  ○ Efeito  ►               │  RadioMenuItem + submenu
│  ○ Desligado               │  RadioMenuItem
│ ─────────────────────────── │
│  Presets  ►                 │  submenu com presets
│ ─────────────────────────── │
│  Configurações...           │  abre janela
│  Sair                       │  quit app (daemon continua)
└─────────────────────────────┘
```

**Submenu Efeito:** lista todos os `VALID_EFFECTS`. Cada efeito tem um submenu com a cor e velocidade atuais exibidas como labels informativos, mais um item "Personalizar..." que abre a janela na seção de efeito. Clicar no nome do efeito aplica direto com a cor/velocidade atuais do config via D-Bus `SetEffect()`. Limitação: AppIndicator não suporta widgets (sliders/pickers) em menus, então ajuste fino de cor e velocidade fica na janela.

**Submenu Presets:** lista presets do config com bullet indicando o ativo. Clicar aplica via D-Bus `ApplyPreset()`.

### Ícone dinâmico

Gera SVG temporário em `/tmp/avell-rgb-icon-XXXXXX.svg` com a cor atual preenchida. Atualiza via `AppIndicator.set_icon_full()` quando recebe `StateChanged` do D-Bus.

Template SVG: círculo colorido simples (16×16 ou 22×22).

### Comunicação com daemon

- Ações do menu → chamadas D-Bus ao daemon
- Daemon emite `StateChanged` → tray atualiza ícone e radio buttons
- Tray monitora `NameOwnerChanged` do bus name do daemon. Se daemon some, ícone fica cinza. Quando reaparece, reconecta.

## Janela de configuração

### Layout

Janela única GTK4/libadwaita, sem sidebar, sem navegação. `Adw.ApplicationWindow` com `Adw.Clamp(maximum_size=600)`.

Seções de cima pra baixo:

1. **Modo** — `Gtk.Box` horizontal com 4 `Gtk.ToggleButton` em grupo. Botão ativo recebe cor do LED via CSS dinâmico.

2. **Cor & Brilho** — `Adw.PreferencesGroup`:
   - `Gtk.ColorDialogButton` grande (48×48) com sombra glow na cor selecionada
   - `Gtk.Scale` de brilho (0-50) com label de valor
   - `Adw.SwitchRow` "Cores independentes" — quando ativo, expande dois pares de color+brightness (teclado e lightbar)

3. **Presets** — `Adw.PreferencesGroup`:
   - Lista de `Adw.ActionRow` com swatch de cor, nome, e botões editar/remover
   - Botão "+ Novo" no header do grupo
   - Clicar no preset aplica imediatamente (D-Bus `ApplyPreset`)

4. **Configuração Solar** — `Adw.PreferencesGroup`:
   - Visível/editável apenas quando modo = solar
   - Campos: latitude, longitude (Gtk.Entry)
   - Color pickers: cor de dia, cor de noite
   - Scales: brilho de dia, brilho de noite

5. **Configuração de Efeito** — `Adw.PreferencesGroup`:
   - Visível/editável apenas quando modo = effect
   - ComboRow pra selecionar efeito
   - Color picker pra cor do efeito
   - Scale pra velocidade (0-10)

6. **Preferências** — `Adw.PreferencesGroup`:
   - `Adw.SwitchRow` "Iniciar no login" (enable/disable systemd service)
   - `Adw.SwitchRow` "Mostrar na bandeja"

### Tema dark com cor dinâmica

A janela usa `Adw.ColorScheme.FORCE_DARK`. Acentos (botão ativo, sliders, switches) usam a cor atual dos LEDs via `Gtk.CssProvider` dinâmico que é atualizado quando `StateChanged` chega.

CSS dinâmico:
```css
.accent-dynamic {
  background-color: {current_color};
  color: {contrasting_text};
}
```

### Comunicação

- Todas as mudanças na janela → D-Bus pro daemon
- Janela escuta `StateChanged` → atualiza widgets se mudança veio de outra fonte (tray)
- **Fechar a janela não muda nenhum estado.** Janela é visualização + controle, não fonte de verdade.

## Autostart e ciclo de vida

### Instalação

Script `install-user.sh` atualizado:
1. `pipx install` (igual v0.1)
2. Copia `avell-rgb-daemon.service` → `~/.config/systemd/user/`
3. Copia `avell-rgb-autostart.desktop` → `~/.config/autostart/` (novo: inicia a GUI em modo tray no login)
4. `systemctl --user enable --now avell-rgb-daemon.service`

### Boot

1. systemd inicia `avell-rgb-daemon` → daemon aplica última config salva
2. Autostart do desktop inicia `avell-rgb-gui --tray` → tray icon aparece
3. Usuário interage via tray ou abre janela quando precisa

### Desligamento

- "Sair" no tray: mata o processo da GUI (tray + janela). Daemon continua rodando.
- Daemon para só via `systemctl --user stop` ou logout.

## Config migration v1 → v2

Função `migrate_v1_to_v2(config_dict) → config_dict`:

```python
def migrate_v1_to_v2(d):
    first_preset = next(iter(d.get("presets", {}).values()), None)
    color = "#FFFFFF"
    brightness = 30
    if first_preset:
        kb = first_preset.get("keyboard", {})
        color = kb.get("color", color)
        brightness = kb.get("brightness", brightness)
    presets = {}
    for name, state in d.get("presets", {}).items():
        kb = state.get("keyboard", {})
        presets[name] = {
            "color": kb.get("color", "#FFFFFF"),
            "brightness": kb.get("brightness", 30),
        }
    return {
        "version": 2,
        "mode": "fixed" if d.get("mode") == "schedule" else d.get("mode", "fixed"),
        "color": color,
        "brightness": brightness,
        "independent_colors": False,
        "keyboard_color": color,
        "keyboard_brightness": brightness,
        "lightbar_color": color,
        "lightbar_brightness": brightness * 2,
        "effect": {"name": "breathing", "color": color, "speed": 5},
        "solar": d.get("solar", {
            "latitude": -23.55, "longitude": -46.63,
            "day_color": "#8FF0A4", "night_color": "#FF7800",
            "day_brightness": 50, "night_brightness": 20,
        }),
        "presets": presets,
    }
```

## Dependências novas

- `gir1.2-ayatanaappindicator3-0.1` — AppIndicator3 (tray icon)
- `dbus-python` ou `dasbus` — D-Bus bindings (preferir `dasbus` por ser async-friendly e tipado)

Dependências existentes mantidas: `astral`, `gi` (GTK4, libadwaita).

## Estrutura de arquivos (projeção)

```
avell_rgb/
├── __init__.py
├── config.py          — load/save/migrate, XDG paths
├── state.py           — dataclasses Config v2, DeviceState simplificado
├── solar.py           — sem alteração
├── backends/
│   ├── keyboard.py    — sem alteração
│   └── lightbar.py    — sem alteração
├── daemon/
│   ├── main.py        — entry point, async loop reescrito
│   └── dbus_api.py    — interface D-Bus (dasbus)
├── gui/
│   ├── app.py         — AdwApplication + AppIndicator setup
│   ├── tray.py        — menu do tray, ícone dinâmico
│   ├── window.py      — janela única, todas as seções
│   ├── color_helpers.py — sem alteração
│   └── main.py        — entry point GUI
data/
├── avell-rgb-daemon.service
├── avell-rgb-autostart.desktop   — novo
├── io.github.avellrgb.Avell.desktop
└── io.github.avellrgb.Avell.svg
scripts/
└── install-user.sh    — atualizado com autostart
```

## Testes

- **Unit tests** para: config migration, state dataclasses, solar (existentes), D-Bus API (mock bus)
- **Integration tests** para: daemon loop com fake backends + real D-Bus session bus
- **Todos os testes do v0.1 que não dependem de schedule/manual_state** são atualizados, não deletados
- Mínimo: `pytest -q` passa 100% antes de cada commit
