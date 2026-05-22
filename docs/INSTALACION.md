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
- **Python:** 3.10+
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

talk2ai usa un sistema de drivers intercambiables. El driver por defecto es **Gemini CLI**.

### Gemini CLI (por defecto)

Requiere Node.js 18+:

```bash
npm install -g @google/gemini-cli
gemini auth login
echo "hola" | gemini   # verificar que funciona
```

### Otros drivers

Cualquier script ejecutable en `~/.talk2ai/ia/<nombre>` que siga el contrato de driver es válido. Ver la sección **Drivers de IA** en el README.

---

## Instalar talk2ai

El instalador se encarga de todo: dependencias del sistema, scripts, servicio systemd, autostart, configuración automática de Handy y arranque del tray.

```bash
git clone https://github.com/GOTXE/talk2ai.git
cd talk2ai
bash install.sh
```

El instalador realiza estos pasos:

1. Instala dependencias del sistema que falten (`xdotool`, `ydotool`, `espeak-ng`, etc.)
2. Activa `ydotool.service` y añade el usuario al grupo `input` (Wayland)
3. Configura Handy automáticamente: `paste_method=external_script`, ruta del handler, atajo interno desactivado
4. Copia los scripts a `~/.local/bin/`
5. Instala el servicio systemd y el autostart del tray
6. Arranca el servicio y el tray
7. Muestra una notificación de finalización

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

---

## Troubleshooting

### El daemon no arranca

```bash
journalctl --user -u talk2ai.service -n 50
```

Causa habitual: `handy` o el driver no están en PATH. Añade en `~/.config/systemd/user/talk2ai.service`:

```ini
[Service]
Environment=PATH=/home/TU_USUARIO/.local/bin:/usr/local/bin:/usr/bin:/bin
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
