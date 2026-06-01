# Changelog

Todas las versiones notables de este proyecto se documentan aquí.  
Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).  
Versionado según [SemVer](https://semver.org/lang/es/).

---

## [1.4.0] — 2026-06-01

### Añadido
- **Streaming OAuth nativo en el driver Gemini**: reemplaza la llamada al CLI de Node.js (`gemini -p`) por HTTP directo al endpoint interno `cloudcode-pa.googleapis.com`, reutilizando las credenciales OAuth del CLI. Primer token en ~2s frente a ~10s anteriores; el audio empieza en cuanto llega la primera frase
- **Google Search grounding**: activa `googleSearch` como tool en cada petición; el modelo busca en la web antes de responder, eliminando respuestas obsoletas del corte de entrenamiento (ej. versión de Arch Linux, ganador del Giro)
- **URL real de fuente**: extrae `groundingChunks[0].web.uri` (redirect de Vertex AI al artículo específico) en lugar de la URL inventada por el modelo

### Corregido
- **Rate limit silencioso**: cuando el endpoint devuelve 429, el driver espera el tiempo exacto indicado por la API y reintenta con search; si sigue bloqueado, reintenta sin search; solo falla si ambos intentos son imposibles
- **Último chunk SSE sin línea vacía**: el stream SSE cierra sin blank line final; el driver ahora procesa ese chunk pendiente para capturar los `groundingChunks`
- **Aviso de enlace sin URL**: cuando el modelo anuncia "te dejo el enlace en avisos" pero no hay grounding disponible, genera automáticamente un enlace de búsqueda de Google con la pregunta limpia (extrae desde la palabra interrogativa acentuada: "Quiero que busques quién…" → "quién…")
- **Voice-prompt**: instrucción explícita para que el modelo use siempre la herramienta de búsqueda cuando el usuario pida buscar en internet o pregunte por eventos recientes

---

## [1.3.1] — 2026-05-23

### Corregido
- **Check de actualizaciones bloqueado en "Comprobando…"**: `QTimer.singleShot(0, ...)` llamado desde `threading.Thread` no es fiable en PyQt6 para volver al hilo principal. Reemplazado por `UpdateSignal(QObject)` con `pyqtSignal`, que Qt enruta correctamente al event loop
- **Botón "Ver releases" de la notificación sin efecto**: formato incorrecto de acción (`--action "open:…"`); corregido a `-A "open=Ver releases"` según la especificación de `notify-send`
- El resultado del check ahora aparece siempre como notificación del sistema (sin necesidad de reabrir el menú)

---

## [1.3.0] — 2026-05-23

### Añadido
- **Versión instalada en el menú del tray**: muestra `v1.3.0 — Buscar actualizaciones…` al fondo del menú; el instalador escribe `~/.talk2ai/version` con la versión instalada
- **Check de actualizaciones bajo demanda**: al hacer clic consulta la GitHub API (timeout 3s), actualiza el label y, si hay versión nueva, el item se vuelve clickable y abre la página de releases

### Cambiado
- El check de actualizaciones es **bajo demanda** (clic del usuario), no automático al arrancar — evita race conditions con el event loop de Qt durante el inicio

---

## [1.2.0] — 2026-05-23

### Añadido
- **Voice-prompt por driver**: el daemon busca `~/.talk2ai/voice-prompt-<driver>.md` antes del genérico; si no existe, usa `voice-prompt.md` como fallback
- **`config/voice-prompt-ollama.md`**: prompt sin instrucción de enlaces (los modelos offline alucinan URLs)
- **Tray → "✏️ Editar prompt del driver…"**: abre con `xdg-open` el voice-prompt activo del driver actual para editarlo directamente; el cambio se aplica en la siguiente consulta sin reiniciar
- El instalador copia automáticamente todos los `config/voice-prompt-*.md` a `~/.talk2ai/`

### Cambiado
- `voice-prompt.md` genérico: añadida restricción explícita de no inventar URLs
- `TALK2AI_VOICE_PROMPT` ahora apunta al fichero específico del driver cuando existe

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
