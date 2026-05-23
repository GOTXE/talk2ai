# Changelog

Todas las versiones notables de este proyecto se documentan aquí.  
Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).  
Versionado según [SemVer](https://semver.org/lang/es/).

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
