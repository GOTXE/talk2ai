# talk2ai

![Linux](https://img.shields.io/badge/Linux-x86__64-FCC624?logo=linux&logoColor=black)
![Shell](https://img.shields.io/badge/Shell-Bash-4EAA25?logo=gnu-bash&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Wayland](https://img.shields.io/badge/Wayland-compatible-00ADEF?logo=wayland&logoColor=white)
![X11](https://img.shields.io/badge/X11-compatible-F05032?logo=x.org&logoColor=white)
[![Gemini CLI](https://img.shields.io/badge/Gemini_CLI-driver_por_defecto-4285F4?logo=google&logoColor=white)](https://github.com/google-gemini/gemini-cli)
![License](https://img.shields.io/badge/License-GPL--3.0-blue?logo=gnu&logoColor=white)

Asistente de voz para Linux con dos modos de uso: **dictado** (tu voz → texto en la ventana activa) e **IA** (tu voz → respuesta de la IA → audio). Usa [Handy](https://handy.computer) para la transcripción local voz→texto.

```
🎤 Hablas
  ├─ [modo dictado] → ⌨️  texto en la ventana activa
  └─ [modo IA]      → 🤖 IA responde → 🔊 escuchas
```

## Demo

<video src="https://github.com/GOTXE/talk2ai/releases/download/v1.0.0/demo.webm" controls width="100%"></video>

## Modos de uso

| Modo | Atajo | Qué hace |
|---|---|---|
| **Dictado** | `Alt+Super+H` | Transcribe tu voz e inyecta el texto en la ventana con foco |
| **IA** | `Alt+Super+G` | Envía tu voz al driver de IA activo y reproduce la respuesta en audio |

El modo persiste hasta que lo cambias. Puedes alternar entre ambos en cualquier momento.

## Componentes

| Componente | Función | Privacidad |
|---|---|---|
| [**Handy**](https://handy.computer) | Transcripción voz→texto (Whisper local) | 100 % local |
| **Driver de IA** (IA CLI) | Procesamiento de la consulta | Requiere internet |
| **espeak-ng** | Síntesis de voz texto→audio | 100 % local |
| **ydotool / xdotool** | Inyección de texto en la ventana activa (Wayland/X11) | 100 % local |
| **talk2ai-daemon** | Supervisor, polling IA, keepalive de atajos | — |
| **talk2ai-handler** | Script externo de Handy para modo dictado | — |
| **talk2ai-tray** | Icono de bandeja del sistema (PyQt6) | — |
| **talk2ai-keys** | Atajos globales via evdev en Wayland | — |
| **talk2ai-control** | Menú interactivo (kdialog) para gestionar el servicio | — |

## Características

- **Dos modos** — dictado directo en cualquier app o consulta a la IA, con un atajo cada uno
- **Transcripción local** — Handy usa Whisper en local; tu voz no sale del equipo
- **Driver extensible** — cada archivo en `~/.talk2ai/ia/<nombre>` es un driver intercambiable
- **Rápido** — el handler sale en <100 ms para no bloquear Handy; la IA responde en streaming
- **Tray icon** — muestra el modo activo y el estado del sistema en tiempo real
- **Wayland y X11** — `ydotool` en Wayland, `xdotool` en X11
- **Autostart** — servicio systemd + desktop entry para arrancar con la sesión

> **Nota:** en modo IA la consulta viaja a los servidores del proveedor del driver activo (a menos que uses un driver local como Ollama). El audio de respuesta siempre se sintetiza localmente con espeak-ng.

## Requisitos

- **SO:** Linux x86_64 (KDE Plasma recomendado; otros escritorios soportados)
- **Python:** 3.10+
- [**Handy**](https://handy.computer) AppImage en PATH como `handy`
- [**Gemini CLI**](https://github.com/google-gemini/gemini-cli) en PATH y autenticado (driver por defecto)

## Instalación

### Paso previo: instalar Handy y Gemini CLI

**1. Handy** — descarga la última versión desde [github.com/cjpais/Handy/releases](https://github.com/cjpais/Handy/releases) y colócalo en PATH:

```bash
chmod +x Handy_*.AppImage
mv Handy_*.AppImage ~/.local/bin/handy
```

**2. Gemini CLI** — driver de IA por defecto. Requiere Node.js 18+:

```bash
npm install -g @google/gemini-cli
gemini auth login
```

> Puedes usar cualquier otro driver compatible (Claude, Ollama, etc.) siguiendo el [contrato de driver](#drivers-de-ia).

### Instalar talk2ai

```bash
git clone https://github.com/GOTXE/talk2ai.git
cd talk2ai
bash install.sh
```

El instalador se encarga de todo: dependencias del sistema, scripts, servicio systemd, autostart, **configuración de Handy** y arranque del tray.

### Configurar Handy manualmente

El instalador configura Handy automáticamente, pero si necesitas revisarlo o hacerlo a mano:

Abre Handy y ajusta lo siguiente:

**Pestaña General — Shortcut**

Asigna un atajo de grabación que **no** entre en conflicto con los atajos de talk2ai. Los atajos reservados son:

| Atajo | Reservado por |
|---|---|
| `Ctrl+Space` | talk2ai (PTT gestionado por talk2ai-keys) |
| `Alt+Super+G` | talk2ai (modo IA) |
| `Alt+Super+H` | talk2ai (modo Dictado) |
| `Ctrl+Alt+Q` | talk2ai (detener audio) |

> Recomendado: deja el atajo interno de Handy **desactivado** — talk2ai gestiona `Ctrl+Space` directamente vía evdev para evitar doble disparo.

**Pestaña Avanzado — Paste method**

Selecciona **External script** e introduce la ruta:

```
/home/TU_USUARIO/.local/bin/talk2ai-handler
```

**Modelos**

Descarga **Parakeet v3** (transcripción offline en español e inglés, rápido y ligero). En Handy → Models → Parakeet v3 → Download.

## Atajos de teclado

| Atajo | Acción |
|---|---|
| `Alt+Super+G` | Cambiar a modo IA |
| `Alt+Super+H` | Cambiar a modo Dictado |
| `Ctrl+Space` | Toggle grabación (1ª pulsación = grabar, 2ª = transcribir) |
| `Ctrl+Alt+Q` | Detener audio (espeak-ng) inmediatamente |

## Estructura del repositorio

```
talk2ai/
├── scripts/
│   ├── talk2ai-daemon    ← supervisor + polling IA
│   ├── talk2ai-handler   ← script externo de Handy (modo dictado)
│   ├── talk2ai-tray      ← tray icon PyQt6
│   ├── talk2ai-keys      ← atajos globales evdev (Wayland)
│   └── talk2ai-control   ← menú kdialog
├── config/
│   ├── talk2ai.service      ← servicio systemd
│   ├── talk2ai-tray.desktop ← autostart KDE
│   ├── xbindkeysrc          ← atajos para X11
│   ├── voice-prompt.md      ← instrucciones TTS para el driver
│   ├── gemini-context.md    ← personalidad/contexto de Gemini
│   └── ia/
│       └── gemini           ← driver Gemini CLI
└── docs/
    └── ARQUITECTURA.md
```

## Gestión del servicio

```bash
systemctl --user start|stop|restart|status talk2ai.service
journalctl --user -u talk2ai.service -f   # logs en tiempo real
talk2ai-control                           # menú interactivo
```

## Drivers de IA

El sistema usa un contrato simple: cada archivo ejecutable en `~/.talk2ai/ia/<nombre>` es un driver.

- **Entrada:** prompt como `$1`
- **Entorno:** `TALK2AI_MODEL`, `TALK2AI_VOICE_PROMPT`, `TALK2AI_CONTEXT_FILE`
- **Salida:** texto en streaming por stdout (sin markdown)
- **Exit:** `0` = éxito, distinto de `0` = error

El driver activo se selecciona desde el tray icon o editando `~/.talk2ai/driver`.

## Diagnóstico rápido

```bash
cat ~/.talk2ai/mode       # ai | dictate
cat ~/.talk2ai/driver     # nombre del driver activo
cat ~/.talk2ai/ai-state   # idle | processing
cat ~/.talk2ai/errors.log # errores recientes

# Probar el driver activo directamente (ejemplo con el driver por defecto)
DRIVER=$(cat ~/.talk2ai/driver)
TALK2AI_MODEL=$(cat ~/.talk2ai/model) \
TALK2AI_VOICE_PROMPT=~/.talk2ai/voice-prompt.md \
TALK2AI_CONTEXT_FILE=~/.talk2ai/context/$DRIVER.md \
~/.talk2ai/ia/$DRIVER "pregunta de prueba"

espeak-ng "prueba"        # verificar audio
```

## Reconocimientos

- [**Handy**](https://handy.computer) de [CJ Pais](https://github.com/cjpais) — transcripción voz→texto local. Distribuido bajo [licencia MIT](https://github.com/cjpais/Handy/blob/main/LICENSE).

## Licencia

Copyright (C) 2026 gotxe

Este programa es software libre: puedes redistribuirlo y/o modificarlo bajo los términos de la **GNU General Public License** publicada por la Free Software Foundation, ya sea la versión 3 de la Licencia, o (a tu elección) cualquier versión posterior.

Este programa se distribuye con la esperanza de que sea útil, pero **SIN NINGUNA GARANTÍA**; sin siquiera la garantía implícita de **COMERCIABILIDAD** o **APTITUD PARA UN PROPÓSITO PARTICULAR**. Consulta la GNU General Public License para más detalles.

Deberías haber recibido una copia de la GNU General Public License junto con este programa. Si no es así, visita <https://www.gnu.org/licenses/>.
