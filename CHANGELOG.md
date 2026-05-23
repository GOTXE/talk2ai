# Changelog

Todas las versiones notables de este proyecto se documentan aquí.  
Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).  
Versionado según [SemVer](https://semver.org/lang/es/).

---

## [1.1.0] — 2026-05-23

### Añadido
- **Driver Ollama** (`config/ia/ollama`) — llama a la API REST de Ollama con streaming; soporta servidores locales y remotos
- **Icono Ollama en el tray** — el icono cambia según el driver activo (estrella Gemini, logo Ollama, inicial en gris para otros)
- **Submenú Ollama en el tray** — permite cambiar el servidor (host) y seleccionar modelo desde un diálogo con scroll; el host y el modelo se persisten entre sesiones
- **Modelo por driver** — `~/.talk2ai/model-<driver>` guarda el modelo elegido para cada driver de forma independiente
- **Instalador: verificación completa** (paso 7/7) — comprueba scripts, drivers, servicio y tray al finalizar
- **Instalador: despliegue automático de drivers** — todos los drivers de `config/ia/` se copian a `~/.talk2ai/ia/` en la instalación
- **Instalador: limpieza de tray.lock** — al detener procesos previos se elimina el lock para evitar instancias bloqueadas
- **Instalador: voice-prompt.md** — se instala automáticamente sin preguntar al usuario
- `assets/ollama-dark.svg` — icono Ollama para el tray (blanco sobre transparente)

### Cambiado
- El daemon selecciona el modelo según el driver activo (`DRIVER_MODELS` map) y respeta el override `~/.talk2ai/model-<driver>`
- El check de estado del tray para Ollama ya no hace petición de red (evitaba race condition con el event loop de Qt que hacía desaparecer el icono)
- Los pasos del instalador se renumeran 0–7 para incluir la verificación final

### Corregido
- El tray aparecía y desaparecía al activar el driver Ollama (race condition por llamada de red bloqueante en hilo de estado)
- El SVG de Ollama embebido en el tray producía un renderer inválido e icono invisible (fragmentación manual de strings Python)

---

## [1.0.0] — 2026-05-22

### Añadido
- Dos modos de uso: **dictado** (voz → texto en ventana activa) e **IA** (voz → driver → audio)
- Driver de IA extensible (`~/.talk2ai/ia/<nombre>`) — incluye driver Gemini CLI
- `talk2ai-daemon` — supervisor, polling SQLite, streaming TTS con espeak-ng
- `talk2ai-handler` — script externo de Handy para modo dictado (<100 ms)
- `talk2ai-tray` — tray icon PyQt6 con modo, driver y estado en tiempo real
- `talk2ai-keys` — atajos globales vía evdev (Wayland) y xbindkeys (X11)
- `talk2ai-control` — menú interactivo kdialog para gestión del servicio
- `install.sh` — instalador interactivo con configuración automática de Handy
- Soporte Wayland (`ydotool`) y X11 (`xdotool`)
- Servicio systemd + autostart KDE
