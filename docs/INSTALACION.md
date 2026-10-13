# Guía de instalación — talk2ai

## Tabla de contenidos

1. [Requisitos](#requisitos)
2. [Instalar Handy](#instalar-handy)
3. [Instalar el driver de IA](#instalar-el-driver-de-ia)
4. [Instalar talk2ai](#instalar-talk2ai)
5. [Configurar Handy](#configurar-handy)
6. [Verificar la instalación](#verificar-la-instalación)
7. [Troubleshooting](#troubleshooting)

---

## Requisitos

- **SO:** Linux x86_64 (probado en CachyOS/Arch; compatible con otras distribuciones)
- **Escritorio:** KDE Plasma (recomendado); otros entornos soportados
- **Sesión:** Wayland o X11
- **Python:** 3.10–3.13 (versiones verificadas en CI)
- **Micrófono:** funcional y accesible por PipeWire/PulseAudio

---

## Instalar Handy

[Handy](https://handy.computer) es la aplicación de transcripción voz→texto local. Funciona completamente offline mediante Whisper. Licencia MIT — [github.com/cjpais/Handy](https://github.com/cjpais/Handy).

Descarga la última versión desde la [página de releases](https://github.com/cjpais/Handy/releases):

```bash
chmod +x Handy_*.AppImage
mv Handy_*.AppImage ~/.local/bin/handy
```

**Modelo recomendado:** en Handy → Models, descarga **Parakeet v3** (rápido, offline, funciona bien en español e inglés).

---

## Instalar el driver de IA

talk2ai usa un sistema de drivers intercambiables. El instalador despliega automáticamente todos los drivers incluidos en el repo (`gemini` y `ollama`).

### Gemini / Antigravity AGY CLI (por defecto)

El driver utiliza Antigravity AGY CLI (`agy`) o Gemini CLI (`gemini`) con el modelo `gemini-3.8-flash-low`:

```bash
# Antigravity AGY CLI (recomendado):
agy -p "hola" --model gemini-3.8-flash-low

# O Gemini CLI (fallback):
npm install -g @google/gemini-cli
gemini auth login
```

### Ollama (opcional, modelos locales o remotos)

El driver Ollama se instala automáticamente. Solo necesitas un servidor Ollama accesible (local o remoto):

- **Local:** `http://127.0.0.1:11434` (valor por defecto)
- **Remoto:** configura el host desde el tray → menú Ollama → *Cambiar servidor…*

El modelo por defecto es `qwen3.5:2b`. Puedes cambiarlo desde el tray → Ollama → *Seleccionar modelo…*

### Personalizar el prompt de cada driver

Cada driver puede tener su propio prompt de sistema en `~/.talk2ai/voice-prompt-<driver>.md`. Si no existe, se usa el genérico `~/.talk2ai/voice-prompt.md`.

Puedes editar el prompt activo en cualquier momento desde el tray → *✏️ Editar prompt del driver…* (abre el fichero en tu editor de texto). El cambio se aplica en la siguiente consulta sin reiniciar nada.

| Fichero | Propósito |
|---|---|
| `~/.talk2ai/voice-prompt.md` | Prompt genérico (fallback para cualquier driver) |
| `~/.talk2ai/voice-prompt-ollama.md` | Prompt específico para Ollama (sin enlaces) |
| `~/.talk2ai/voice-prompt-gemini.md` | Prompt específico para Gemini (si existe) |

### Otros drivers

Cualquier script ejecutable en `~/.talk2ai/ia/<nombre>` que siga el contrato de driver es válido. Ver la sección **Drivers de IA** en el README.

---

## Instalar talk2ai

El instalador se encarga de todo: dependencias del sistema, scripts, servicio systemd, autostart, configuración automática de Handy y arranque del tray. Usa `TALK2AI_DIR` si se define; si no, conserva una instalación existente en `~/.talk2ai` o usa `${XDG_STATE_HOME:-~/.local/state}/talk2ai` para una instalación nueva. Los catálogos van a `${TALK2AI_DATA_DIR:-${XDG_DATA_HOME:-~/.local/share}/talk2ai}`.

```bash
git clone https://github.com/GOTXE/talk2ai.git
cd talk2ai
bash install.sh
```

El instalador realiza estos pasos:

0. Detiene procesos previos y sólo elimina el lock del tray después de verificar
   que su PID terminó; si sigue activo, la instalación se detiene sin romper la
   exclusión mutua
1. Instala dependencias del sistema que falten (`xdotool`, `ydotool`, `espeak-ng`, etc.)
2. Configura Handy automáticamente: `paste_method=external_script`, ruta del handler, atajo interno desactivado
3. Informa sobre los drivers disponibles (Gemini y Ollama)
4. Copia los scripts a `~/.local/bin/` **y los drivers** a `$TALK2AI_DIR/ia/`; actualiza los catálogos TTS versionados en `$TALK2AI_DATA_DIR` sin modificar las preferencias de voz
5. Instala el servicio systemd y el autostart del tray
6. Instala `voice-prompt.md` y ofrece instalar el contexto de personalidad
7. Verifica que todo esté correcto (scripts, drivers, servicio, tray) y muestra un resumen; escribe `~/.talk2ai/version` con la versión instalada

---

## Configurar Handy

El instalador configura Handy automáticamente. Si necesitas revisarlo o hacerlo a mano:

### Pestaña General — Shortcut

El atajo de grabación (PTT) debe ser uno que **no** entre en conflicto con los atajos de talk2ai:

| Atajo | Reservado por |
|---|---|
| `Ctrl+Space` | talk2ai-keys (PTT, gestionado vía evdev) |
| `Alt+Super+G` | talk2ai (cambiar a modo IA) |
| `Alt+Super+H` | talk2ai (cambiar a modo Dictado) |
| `Ctrl+Alt+Q` | talk2ai (detener audio) |

> Deja el atajo interno de Handy **desactivado** — talk2ai gestiona `Ctrl+Space` directamente para evitar doble disparo.

### Pestaña Avanzado — Paste method

Selecciona **External script** e introduce la ruta:

```
/home/TU_USUARIO/.local/bin/talk2ai-handler
```

### Modelos

Descarga **Parakeet v3** desde Handy → Models → Parakeet v3 → Download.

---

## Verificar la instalación

```bash
# Servicio activo
systemctl --user status talk2ai.service

# Estado runtime
cat ~/.talk2ai/mode      # debe mostrar: ai
cat ~/.talk2ai/driver    # nombre del driver activo
cat ~/.talk2ai/model     # modelo activo

# Proceso de atajos corriendo (Wayland)
pgrep -a -f "python3.*talk2ai-keys"

# Probar el driver activo directamente
DRIVER=$(cat ~/.talk2ai/driver)
TALK2AI_MODEL=$(cat ~/.talk2ai/model) \
TALK2AI_VOICE_PROMPT=~/.talk2ai/voice-prompt.md \
TALK2AI_CONTEXT_FILE=~/.talk2ai/context/$DRIVER.md \
~/.talk2ai/ia/$DRIVER "pregunta de prueba"

# Probar síntesis de voz
espeak-ng "instalación completada"
```

## Voz / TTS opcional

`install.sh` deja eSpeak-ng Retro configurado y no descarga pesos, wheels ni
voces. Esto funciona igual en CachyOS/Arch y Debian/Ubuntu; ambos instaladores
incluyen `alsa-utils` y el soporte de venv, pero no modifican el Python global.

```bash
talk2ai-tts list
talk2ai-tts test espeak-retro
talk2ai-tts download kokoro-ef-dora --confirm
```

La última orden sólo descarga `kokoro-v1.0.int8.onnx` y `voices-v1.0.bin` a la
caché privada después de comprobar sus SHA-256; nunca sobrescribe un fichero
que no coincida. Las tres voces españolas de Kokoro comparten ese paquete de
voces. Para usarlo hace falta además el runtime aislado
`~/.talk2ai/tts-venv`: su instalación automática está deliberadamente
deshabilitada mientras falta un lock auditado de las dependencias transitivas
por plataforma. No instales paquetes TTS en el Python de sistema para saltar
esta barrera.

Piper no se instala ni se habilita. En concreto DaveFX y Sharvard continúan
bloqueados; Carlfm también queda bloqueado hasta verificar los derechos de los
pesos. Consulta [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) antes de
revisar o ampliar el catálogo.

Para detener cualquier motor, síntesis pendiente y reproducción:

```bash
talk2ai-tts cancel
```

---

## Troubleshooting

### El daemon no arranca

```bash
journalctl --user -u talk2ai.service -n 50
```

Causa habitual: `handy` o el driver no están en PATH. Añade en `~/.config/systemd/user/talk2ai.service`:

```ini
[Service]
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin
```

### El dictado no escribe en la ventana

En Wayland, verifica `ydotool.service` y el grupo `input`:

```bash
systemctl --user status ydotool.service
groups $USER | grep input
```

Si acabas de ser añadido al grupo `input`, cierra sesión y vuelve a entrar.

### El atajo Ctrl+Space no funciona

```bash
# Wayland
pgrep -a -f talk2ai-keys

# X11
pgrep -a xbindkeys
xbindkeys --show
```

Verifica también que el atajo interno de Handy está **desactivado** (campo vacío en Handy → General → Shortcut).

### El driver de IA no responde

```bash
cat ~/.talk2ai/errors.log
cat ~/.talk2ai/driver
```

Prueba el driver directamente (ver sección Verificar la instalación).

### Ollama no responde

```bash
cat ~/.talk2ai/ollama-host    # host configurado
# Probar conectividad
curl $(cat ~/.talk2ai/ollama-host)/api/tags
```

Si el host es incorrecto, cámbialo desde el tray → Ollama → *Cambiar servidor…*, o directamente:

```bash
echo "http://IP:11434" > ~/.talk2ai/ollama-host
```

### No hay audio

```bash
espeak-ng "prueba"
pactl list sinks
cat ~/.talk2ai/errors.log
```

### Ctrl+Alt+Q no corta el audio

```bash
pgrep -a espeak
# X11: relanzar xbindkeys si no está corriendo
pgrep -a xbindkeys || xbindkeys
```
