# Avell RGB — Design Spec

**Data:** 2026-04-10
**Autor:** ALC (com Claude Opus 4.6)
**Status:** Draft (aguardando revisão do usuário)

## 1. Contexto e Problema

O notebook Avell STORM 570 TI tem dois sistemas de iluminação RGB:

1. **Teclado** — matriz controlada pelo chip ITE 8291 (`048D:600B`, rev 0.03), operado via a ferramenta `ite8291r3-ctl` (CLI Python, instalada via pipx, já funcional nesta máquina).
2. **Light bar inferior** — uma barra de LEDs separada, controlada pelo EC ITE 8233 (`048D:7001`), exposta no kernel via o módulo `ite_8291_lb` (parte do `tuxedo-drivers`, já compilado e carregado nesta máquina) como `/sys/class/leds/rgb:lightbar/`.

Hoje, controlar os dois exige comandos de terminal distintos. Não há aplicação nativa Linux que gerencie ambos numa interface unificada, muito menos que aplique cores diferentes por horário do dia.

## 2. Objetivo

Construir um utilitário Linux nativo, com interface gráfica polida, que permita ao usuário:

1. Configurar cor, brilho e efeitos do teclado e da barra inferior de forma unificada.
2. Criar, editar e gerenciar **presets** (combinações nomeadas de estados pros dois dispositivos).
3. Agendar presets por **faixa horária** (ex: "Trabalho" das 7h–18h).
4. Alternativamente, usar um **modo solar** que interpola entre uma "cor de dia" e uma "cor de noite" usando a posição real do sol pra localização geográfica configurada.
5. Funcionar mesmo com a GUI fechada — o scheduler roda em background.
6. Integrar-se nativamente ao GNOME/Ubuntu, com aparência consistente com o resto do sistema.

## 3. Não-Objetivos (YAGNI)

- Controlar iluminação de outros componentes (ventoinhas, mouse, periféricos externos). Só teclado + barra.
- Suportar outros modelos de laptop. Código é isolado o suficiente pra adaptação futura, mas o MVP é Avell STORM 570 TI.
- Sincronizar cores com áudio, jogo, ou conteúdo da tela (exceto o modo `--screen` que o `ite8291r3-ctl` já oferece nativamente — se o usuário quiser, usa direto pela CLI).
- Editor per-key (acender teclas individualmente em cores diferentes). Só cor global + zona única na barra.
- Suporte multiplataforma (Windows/macOS). Linux-only.
- Tray icon. GNOME 47+ não suporta tray nativo; exigiria extensão; complexidade não vale o ganho.

## 4. Arquitetura

Três componentes, responsabilidade única cada:

```
┌─────────────────────┐      SIGHUP              ┌──────────────────────┐
│    avell-rgb-gui    │ ───────────────────────▶ │   avell-rgb-daemon   │
│  (PyGObject GTK4)   │                          │  (systemd --user)    │
│                     │      reads/writes        │                      │
│  edita config       │ ◀──────────────────────▶ │  aplica config       │
│  preview ao vivo    │       ~/.config/         │  agenda próximo      │
│                     │       avell-rgb/         │  evento              │
└─────────────────────┘       config.json        └──────────────────────┘
                                                         │     │
                                  ┌──────────────────────┘     │
                                  ▼                            ▼
                    ┌─────────────────────┐      ┌──────────────────────┐
                    │   ite8291r3-ctl     │      │  /sys/class/leds/    │
                    │   (subprocess)      │      │  rgb:lightbar/       │
                    │   → teclado         │      │  → barra             │
                    └─────────────────────┘      └──────────────────────┘
```

### 4.1 `avell-rgb-daemon`

Processo Python enxuto rodando como `systemd --user`. Responsabilidades:

- Ler `~/.config/avell-rgb/config.json` na inicialização.
- Calcular qual estado deve estar aplicado AGORA (preset ativo por agenda, interpolação solar, ou estado manual).
- Executar a aplicação via backends (subprocess `ite8291r3-ctl` pro teclado, escrita em sysfs pra barra).
- Calcular quantos segundos até o próximo evento (próxima borda de faixa, próximo tick de interpolação solar, ou ∞ em manual) e dormir (`asyncio.wait_for`).
- Receber `SIGHUP` da GUI → recarregar config → reaplicar.

### 4.2 `avell-rgb-gui`

Aplicação GTK4 + libadwaita em Python (PyGObject). Responsabilidades:

- Editar `config.json`.
- Ao salvar, mandar `SIGHUP` pro daemon via `systemctl --user kill -s HUP avell-rgb-daemon.service`.
- Modo "preview ao vivo": qualquer mudança em slider/color picker escreve o novo estado em `config.manual_state` e manda SIGHUP. O daemon, por sempre respeitar `manual_state` quando presente, aplica imediatamente.
- Ao fechar a janela: se `manual_paused == false` (default), limpa `manual_state` e manda SIGHUP (daemon volta pro modo automático). Se `manual_paused == true`, mantém `manual_state` como está ("congelado" até próxima intervenção).

### 4.3 Config

Único arquivo JSON em `~/.config/avell-rgb/config.json`. Versionado (`"version": 1`), humano-legível, editável na mão.

### 4.4 Justificativa de escolhas

- **SIGHUP em vez de DBus**: DBus seria o canal mais "rico" pra comunicação GUI↔daemon, mas adiciona ~3× o volume de código e dependências. Pro caso "recarregue config", SIGHUP é antigo, testado e suficiente. Migração futura pra DBus é local — não afeta o resto do sistema.
- **Daemon separado em vez de GUI rodando em background**: responsabilidade única. O daemon não depende do GTK, é testável em isolamento, continua funcionando se a GUI crashar.
- **Python + GTK4 + libadwaita** em vez de Qt ou Electron: estética nativa GNOME, widgets prontos (AdwColorDialog, AdwPreferencesPage, AdwActionRow, AdwToast), zero compilação, dependências leves (`python3-gi`, `gir1.2-adw-1`).

## 5. Modelo de Dados

### 5.1 Schema do `config.json`

```json
{
  "version": 1,
  "mode": "schedule",
  "manual_paused": false,
  "manual_state": null,
  "presets": {
    "trabalho": {
      "keyboard": { "type": "solid", "color": "#00FFFF", "brightness": 30 },
      "lightbar": { "color": "#00FFFF", "brightness": 80 }
    },
    "noite": {
      "keyboard": { "type": "solid", "color": "#FF3300", "brightness": 10 },
      "lightbar": { "color": "#FF3300", "brightness": 20 }
    },
    "game": {
      "keyboard": {
        "type": "effect",
        "effect": "wave",
        "color": "rainbow",
        "speed": 5,
        "brightness": 50,
        "direction": "right"
      },
      "lightbar": { "color": "#FF00FF", "brightness": 100 }
    },
    "off": {
      "keyboard": { "type": "off" },
      "lightbar": { "color": "#000000", "brightness": 0 }
    }
  },
  "schedule": [
    { "start": "07:00", "end": "18:00", "preset": "trabalho" },
    { "start": "18:00", "end": "23:00", "preset": "noite" },
    { "start": "23:00", "end": "07:00", "preset": "game" }
  ],
  "solar": {
    "latitude": -23.55,
    "longitude": -46.63,
    "day_color": "#FFFFFF",
    "night_color": "#FF6600",
    "day_brightness": 50,
    "night_brightness": 20,
    "apply_to": ["keyboard", "lightbar"]
  }
}
```

### 5.2 Semântica dos campos

- **`mode`**: `"schedule"` | `"solar"`. Determina qual lógica de cálculo automática o daemon usa quando não há override manual. Modos mutuamente exclusivos.
- **`manual_state`**: quando presente (objeto com `keyboard` + `lightbar`), sobrescreve completamente o modo automático — o daemon aplica esse estado e ignora `schedule`/`solar`. Usado pela GUI pro preview ao vivo. Quando `null`, o daemon segue o `mode`.
- **`manual_paused`**: flag controlado pela GUI (o daemon não lê este campo). Quando `true`, a GUI NÃO limpa `manual_state` ao fechar a janela (modo "congelado"). Quando `false`, a GUI limpa `manual_state` ao fechar (volta pro agendamento automático). Persistido no config pra lembrar a preferência entre sessões.
- **`presets`**: dicionário indexado por slug. Valor é um objeto `{keyboard, lightbar}` no mesmo formato de estado.
- **`keyboard.type`**: `"solid"` (campos: `color`, `brightness`), `"effect"` (campos: `effect`, `color`, `speed`, `direction`, `brightness`), `"off"` (sem campos extras).
- **`keyboard.effect`**: um de `breathing`, `wave`, `random`, `rainbow`, `ripple`, `marquee`, `raindrop`, `aurora`, `fireworks` (os nove que o `ite8291r3-ctl` expõe).
- **`keyboard.color`**: ou `"#RRGGBB"` (cor fixa) ou nome de paleta (`"rainbow"`, `"random"`, ou uma das cores aceitas pelo flag `--color` do tool).
- **`lightbar`**: sempre `{color, brightness}`. A barra não tem efeitos (kernel driver só expõe RGB estático).
- **`schedule`**: lista ordenada. Faixas onde `end < start` (string) significam "atravessa meia-noite" (ex: `23:00–07:00`).
- **`solar.apply_to`**: subset de `["keyboard", "lightbar"]` — controla se o modo solar cobre só um dispositivo, só o outro, ou ambos.
- **`solar.latitude/longitude`**: coordenadas geográficas. Usadas pela lib `astral` pra calcular elevação do sol.

### 5.3 Migração e defaults

Na ausência de `config.json`, o daemon grava um default com 4 presets (Trabalho, Noite, Game, Off), agenda mínima `07:00–19:00 Trabalho` / `19:00–07:00 Noite`, modo `schedule`, solar `enabled=false`.

Migração é trivial hoje (version 1 é o nascimento). Um campo `version` existe só pra viabilizar migrações futuras sem quebrar configs antigos.

## 6. Comportamento do Daemon

### 6.1 Loop principal (pseudocódigo)

```python
class Daemon:
    def __init__(self):
        self.config = load_config()
        self.reload_event = asyncio.Event()
        signal.signal(signal.SIGHUP, lambda *_: self.reload_event.set())

    async def run(self):
        while True:
            desired = self.compute_desired_state()
            self.apply(desired)
            delay = self.seconds_until_next_change()
            try:
                await asyncio.wait_for(self.reload_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass  # horário mudou, recomputar
            if self.reload_event.is_set():
                self.config = load_config()
                self.reload_event.clear()

    def compute_desired_state(self) -> State:
        if self.config.manual_state is not None:
            return self.config.manual_state
        if self.config.mode == "solar":
            return self.interpolate_solar(now())
        return self.resolve_schedule(now())  # mode == "schedule"

    def seconds_until_next_change(self) -> float:
        if self.config.manual_state is not None:
            return float("inf")  # manual override: só acorda em SIGHUP
        if self.config.mode == "solar":
            return min(300, seconds_until_next_solar_tick())
        return seconds_until_next_schedule_boundary()  # mode == "schedule"
```

### 6.2 Resolução de schedule

Dado `now` (hora local), percorre `schedule` procurando faixa que contenha `now`. Faixas atravessando meia-noite (`end < start`) são tratadas testando `now >= start or now < end`. Se nenhuma faixa casa, aplica o último preset conhecido (fallback: `off`). Se houver overlap entre faixas, a primeira na lista vence (ordem = prioridade).

### 6.3 Interpolação solar

Usa `astral` (pura Python, bem mantida, MIT):

1. Calcula elevação do sol em graus para (lat, lon, now).
2. Normaliza: `t = clamp((elevation + 6) / 12, 0, 1)` — transição suave entre crepúsculo civil (-6°) e 6° de elevação.
3. Converte `day_color` e `night_color` de RGB pra HSL.
4. Interpola H/S/L linearmente com `t`.
5. Converte de volta pra RGB.
6. Brilho segue a mesma lógica linear entre `night_brightness` e `day_brightness`.

Reaplica a cada 5 min quando em modo solar. Intervalo pode virar configurável se necessário.

### 6.4 Reload via SIGHUP

Handler instalado com `signal.signal(signal.SIGHUP, handler)`. Handler seta `asyncio.Event`. Loop sai do `wait_for` com `TimeoutError` se o timeout bater, ou com o evento setado se SIGHUP chegou. Em ambos os casos, recomputa estado.

## 7. Backends de Hardware

Duas classes em `avell_rgb/backends/`, cada uma com interface finita e injetável.

### 7.1 `KeyboardBackend`

Wraps `ite8291r3-ctl` via `subprocess.run`. Interface:

```python
class KeyboardBackend:
    def available(self) -> bool: ...
    def apply_solid(self, rgb: tuple[int,int,int], brightness: int) -> None: ...
    def apply_effect(self, effect: str, color: str, speed: int,
                     direction: str | None, brightness: int) -> None: ...
    def off(self) -> None: ...
```

- `available()`: checa presença do binário `ite8291r3-ctl` no PATH com `shutil.which`.
- `apply_solid`: chama `ite8291r3-ctl monocolor --rgb R,G,B -b BRI`.
- `apply_effect`: chama `ite8291r3-ctl effect EFFECT -c COLOR -s SPEED [-d DIR] -b BRI`.
- `off`: chama `ite8291r3-ctl off`.

Erros não-zero do subprocess são logados mas não crasham o daemon — hardware pode estar temporariamente ausente.

### 7.2 `LightbarBackend`

Escreve em `/sys/class/leds/rgb:lightbar/`. Interface:

```python
class LightbarBackend:
    SYSFS = Path("/sys/class/leds/rgb:lightbar")

    def available(self) -> bool: ...
    def apply(self, rgb: tuple[int,int,int], brightness: int) -> None: ...
    def off(self) -> None: ...
```

- `available()`: `SYSFS.exists()` E `(SYSFS / "brightness").access(os.W_OK)`.
- `apply`: escreve `"R G B"` em `multi_intensity` e `brightness` em `brightness` (0–100, escalado a partir do parâmetro 0–100).
- `off`: escreve `0` em `brightness`.

Assume que a permissão de escrita no sysfs já foi configurada pelo systemd service `lightbar.service` (feito em etapa anterior ao projeto).

### 7.3 Fakes para testes

Duas classes em `tests/conftest.py` (`FakeKeyboardBackend`, `FakeLightbarBackend`) que guardam o último comando aplicado em memória, permitindo assertions sem tocar hardware real.

## 8. Interface Gráfica

### 8.1 Janela principal

`AdwApplicationWindow` com `AdwNavigationSplitView`: sidebar à esquerda com 4 itens, `AdwViewStack` à direita com 4 páginas.

### 8.2 Página "Agora" (default)

Controle manual direto, sem salvar preset. Layout:

- Header: status textual ("Modo atual: Preset 'Trabalho' — automático via agenda") + botão toggle "Pausar agendamento".
- Seção "⌨ Teclado": radio entre "Cor sólida" / "Efeito" / "Desligado". Se sólida: `AdwColorDialogButton` + slider de brilho (0–50). Se efeito: combobox com os 9 efeitos, combobox de cor, sliders de velocidade e direção.
- Seção "▬ Barra inferior": `AdwColorDialogButton` + slider de brilho (0–100).
- Botão "Salvar como preset..." no rodapé abre um dialog modal pra nomear.

Comportamento: qualquer alteração num controle grava em `config.manual_state` e manda SIGHUP. O daemon aplica imediatamente. Ao fechar a janela: se `manual_paused` é `false`, limpa `manual_state` e manda SIGHUP (volta pro modo automático). Se `true`, mantém.

### 8.3 Página "Presets"

`AdwPreferencesGroup` com uma `AdwActionRow` por preset. Cada linha mostra nome, thumbnail de cores (dois quadrados coloridos) e um `GtkMenuButton` com ações: Editar, Duplicar, Apagar. Header tem botão "+ Novo preset".

Editar/novo abre um dialog modal com os mesmos controles da página "Agora", mais um campo de nome.

### 8.4 Página "Agenda"

Duas seções:

- **Faixas horárias**: lista de `AdwActionRow` mostrando "07:00 – 18:00 → Trabalho". Botão `+ Adicionar faixa`. Editar/remover via menu `⋮` na linha. Cada faixa tem horário de início, horário de fim e um dropdown com presets existentes.
- **Modo solar**: `AdwExpanderRow` com toggle "Seguir sol". Quando ligado: campos lat/lon (com botão "Detectar via timedatectl" ou entrada manual), `AdwColorDialogButton` pra cor de dia e de noite, sliders de brilho, checkboxes `Aplicar a: [x] Teclado [x] Barra`.

Ligar "modo solar" desmarca todas as faixas visualmente (elas continuam no config, apenas inativas). Desligar "modo solar" reativa as faixas.

### 8.5 Página "Preferências"

- Toggle "Iniciar daemon no login" (`systemctl --user enable/disable avell-rgb-daemon.service`).
- Toggle "Manter estado manual ao fechar" (seta `manual_paused`: quando ligado, fechar a janela NÃO limpa `manual_state`, fixando a cor/efeito atual indefinidamente).
- Botão "Abrir config.json no editor padrão" (`xdg-open ~/.config/avell-rgb/config.json`).
- Seção "Sobre" com versão, link do repo (placeholder), licença.

### 8.6 Interação e feedback

- `AdwToast` ("Preset 'Trabalho' salvo", "Faixa aplicada", etc) no topo da janela — 3 segundos, sem modal.
- Mudanças são aplicadas direto (não há botão "Aplicar"). Desfazer = mexer o slider de volta.

## 9. Estrutura de Arquivos

```
~/src/avell-rgb/
├── README.md
├── LICENSE                             # MIT
├── pyproject.toml                      # pipx-installable
│
├── avell_rgb/
│   ├── __init__.py
│   ├── config.py                       # load/save/validate
│   ├── state.py                        # dataclasses
│   ├── scheduler.py                    # resolve_schedule, next_change
│   ├── solar.py                        # interpolate_solar
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── keyboard.py
│   │   └── lightbar.py
│   ├── daemon/
│   │   ├── __init__.py
│   │   └── main.py                     # entry: avell-rgb-daemon
│   └── gui/
│       ├── __init__.py
│       ├── main.py                     # entry: avell-rgb-gui
│       ├── app.py                      # AdwApplication
│       ├── window.py                   # AdwApplicationWindow + NavigationSplitView
│       ├── page_now.py
│       ├── page_presets.py
│       ├── page_schedule.py
│       ├── page_preferences.py
│       └── widgets/
│           ├── color_button.py
│           ├── effect_picker.py
│           └── preset_row.py
│
├── tests/
│   ├── conftest.py                     # fakes
│   ├── test_config.py
│   ├── test_scheduler.py
│   ├── test_solar.py
│   ├── test_backends.py
│   └── test_daemon_loop.py
│
├── data/
│   ├── io.github.avellrgb.Avell.desktop
│   ├── io.github.avellrgb.Avell.svg
│   └── avell-rgb-daemon.service
│
└── scripts/
    └── install-user.sh
```

## 10. Instalação

Script `scripts/install-user.sh`, idempotente, sem sudo:

```bash
#!/bin/sh
set -e
pipx install --force .
install -Dm644 data/io.github.avellrgb.Avell.desktop \
    ~/.local/share/applications/io.github.avellrgb.Avell.desktop
install -Dm644 data/io.github.avellrgb.Avell.svg \
    ~/.local/share/icons/hicolor/scalable/apps/io.github.avellrgb.Avell.svg
update-desktop-database ~/.local/share/applications 2>/dev/null || true
install -Dm644 data/avell-rgb-daemon.service \
    ~/.config/systemd/user/avell-rgb-daemon.service
systemctl --user daemon-reload
systemctl --user enable --now avell-rgb-daemon.service
echo "Instalado."
```

`avell-rgb-daemon.service` (systemd user unit):

```ini
[Unit]
Description=Avell RGB daemon (keyboard + lightbar scheduler)
After=graphical-session.target

[Service]
Type=simple
ExecStart=%h/.local/bin/avell-rgb-daemon
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

Pré-requisitos externos (já configurados nesta máquina, mas documentados pra portabilidade futura):

- `ite8291r3-ctl` instalado e no `PATH` (pipx).
- Módulo kernel `ite_8291_lb` carregado no boot (via `/etc/modules-load.d/`).
- `/sys/class/leds/rgb:lightbar/{brightness,multi_intensity}` com permissão de escrita pro usuário (via `lightbar.service` systemd já instalado).

## 11. Testes

### 11.1 Unitários (pytest)

- **`test_config.py`**: serialização round-trip, validação de schema (versão, campos obrigatórios, tipos), preenchimento de defaults.
- **`test_scheduler.py`**: faixa normal contendo o horário, faixa atravessando meia-noite, faixa com `start == end`, lista vazia (fallback), overlap (primeira vence), cálculo de `next_change` em cada caso.
- **`test_solar.py`**: elevação máxima (zênite → 100% day_color), horizonte (t=0.5), nadir (night_color), transições suaves, mudança de dia.
- **`test_backends.py`**: `KeyboardBackend` com `subprocess.run` mockado verifica que os args certos saem pra cada chamada. `LightbarBackend` com `tmp_path` simula o sysfs e valida escritas.
- **`test_daemon_loop.py`**: daemon com `FakeKeyboardBackend` + `FakeLightbarBackend` + clock fake. Valida que `apply` é chamado nos horários corretos, que SIGHUP dispara reload, que manual_state sobrescreve schedule.

### 11.2 Verificação manual (checklist antes de declarar pronto)

- [ ] `./scripts/install-user.sh` instala sem erros.
- [ ] `systemctl --user status avell-rgb-daemon` mostra `active`.
- [ ] Abrir "Avell RGB" no menu de aplicações abre a janela.
- [ ] Página "Agora": mover slider de cor do teclado muda a cor ao vivo.
- [ ] Criar preset "Teste" aparece na página Presets.
- [ ] Adicionar faixa `agora+1min – agora+3min → Teste` aplica o preset no minuto seguinte.
- [ ] Ligar modo solar com lat/lon locais → cores assumem interpolação.
- [ ] Fechar GUI e esperar próxima faixa → daemon aplica sem a GUI aberta.
- [ ] `systemctl --user restart avell-rgb-daemon` preserva o estado correto.
- [ ] Reboot do sistema → config persiste e estado é restaurado no login.

## 12. Riscos e Mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| `ite8291r3-ctl` ser atualizado via `pipx upgrade` e perder o patch do `0x600b` | Teclado para de ser controlado | Documentar no README; considerar fork permanente no futuro |
| Kernel update quebra o módulo `ite_8291_lb` (compilado manualmente, não DKMS) | Barra para de responder | Fora do escopo deste projeto, mas mencionado no README como manutenção |
| `astral` retornar elevação imprecisa em latitudes polares | Transição solar estranha | Clamp no `t` e fallback pra `day_color` se `elevation > 90` (inválido) |
| Usuário cria overlap de faixas | Comportamento ambíguo | Primeira na ordem vence; UI alerta via toast |
| Daemon crasha por exceção não tratada | Estado para de ser aplicado | `Restart=on-failure` no systemd unit; log no journal; except abrangente no loop |

## 13. Decisões Em Aberto

Nenhuma no momento do commit inicial. Revisar antes de implementar.

## 14. Próximos Passos

1. Usuário revê este spec.
2. Se aprovado, a skill `writing-plans` é invocada pra gerar um plano de implementação detalhado (arquivo por arquivo, ordem, critérios de "pronto").
3. Implementação segue o plano, com `test-driven-development` nos módulos puros (scheduler, solar, config) e abordagem pragmática nos backends/GUI.
4. `verification-before-completion` roda a checklist manual da seção 11.2 antes de declarar finalizado.
