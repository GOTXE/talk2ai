# Arquitectura talk2ai + Handy

> Cómo conviven [Handy](https://handy.computer) (STT local), el daemon de IA, el handler de dictado
> y el resto de piezas para formar un asistente de voz en KDE Wayland.

---

## Visión general de componentes

```
╔══════════════════════════════════════════════════════════════════════╗
║                        USUARIO / TECLADO                            ║
║                                                                      ║
║   Ctrl+Space          Alt+Super+G        Alt+Super+H                ║
║   (grabar/parar)      (modo IA)          (modo Dictado)             ║
╚══════════╤══════════════════╤═══════════════════╤════════════════════╝
           │                  │                   │
           ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────┐
│              talk2ai-keys  (Python/evdev)            │
│  Lee /dev/input directamente — sin portal KDE        │
│  Keepalive automático tras suspend/resume            │
└────────────┬───────────────────────────┬────────────┘
             │ handy                     │ escribe
             │ --toggle-transcription    │ ~/.talk2ai/mode
             ▼                           ▼
  ┌──────────────────────┐    ┌─────────────────────────┐
  │   Handy  (AppImage)  │    │   talk2ai-tray (PyQt6)  │
  │   Speech-to-Text     │    │   Icono en system tray  │
  │   Wayland / PipeWire │    │   Watcher sobre archivos│
  └──────┬───────────────┘    └─────────────────────────┘
         │                              ▲
         │ graba + transcribe           │ lee cada 3s
         │ (Whisper local)              │ mode / driver /
         │                              │ ai-state / model
         ├──► SQLite  ──────────────────┤
         │    history.db                │
         │                    ┌─────────────────────────┐
         │                    │   talk2ai-daemon         │
         └──► talk2ai-handler │   (systemd user service) │
              (script externo)│   polling SQLite c/1s    │
              │               └────────────┬────────────┘
              │                            │ nueva fila
              │                            │ en modo IA
              │                            ▼
              │                   ~/.talk2ai/ia/<driver>
              │                   (driver ejecutable)
              │                            │
              │                            ▼
              │                      driver de IA
              │                   (streaming stdout)
              │                            │
              │                     espeak-ng (TTS)
              │                     + notify-send (enlaces)
              │
              └─── modo dictado ──► ydotool type
                                    (uinput kernel)
                                    ventana activa
```

---

## Los dos modos en detalle

### Modo IA  (`Alt+Super+G`)

```
  Ctrl+Space ×2
      │
      ├─ talk2ai-keys → handy --toggle-transcription (×2: start/stop)
      │
      ├─ Handy graba audio → Whisper → texto
      │
      ├─ Handy guarda en SQLite (history.db)
      │
      ├─ Handy llama talk2ai-handler → MODE=ai → exit 0  (< 10 ms)
      │   Handy queda libre inmediatamente
      │
      └─ talk2ai-daemon detecta nueva fila en SQLite
              │
              ├─ escribe "processing" en ai-state
              │   └─ talk2ai-tray anima el icono (latido)
              │
              ├─ exporta TALK2AI_MODEL / TALK2AI_VOICE_PROMPT /
              │          TALK2AI_CONTEXT_FILE
              │
              ├─ llama al driver: ~/.talk2ai/ia/<driver> "$pregunta"
              │        │
              │        └─ driver de IA — streaming de texto por stdout
              │
              ├─ acumula frases (. ! ? : o > 150 chars)
              │   └─ espeak-ng -v es -m -s 140 -p 40  (voz)
              │
              ├─ detecta [ENLACE: url] en la respuesta
              │   ├─ notify-send con botón "Abrir" → xdg-open
              │   └─ debug.log  tipo L  (enlace clickable en tray)
              │
              ├─ escribe respuesta en debug.log (tipo Q/A/STAT)
              │
              └─ escribe "idle" en ai-state
                  └─ talk2ai-tray vuelve al icono estático
```

### Modo Dictado  (`Alt+Super+H`)

```
  Ctrl+Space ×2
      │
      ├─ talk2ai-keys → handy --toggle-transcription (×2: start/stop)
      │
      ├─ Handy graba audio → Whisper → texto
      │
      ├─ Handy guarda en SQLite (history.db)
      │   └─ talk2ai-daemon lo lee pero lo ignora (modo dictate)
      │
      └─ Handy llama talk2ai-handler "$texto"
              │
              ├─ lee ~/.talk2ai/mode → "dictate"
              │
              ├─ lanza subshell DESACOPLADO (</dev/null, disown)
              │   Handy recibe exit 0 inmediatamente (< 10 ms)
              │
              └─ subshell (0.5s después):
                    ydotool type --key-delay 12 -- "$texto"
                    (inyección vía /dev/uinput, sin portal KDE)
                    → texto aparece en la ventana activa
```

---

## Estado compartido: `~/.talk2ai/`

```
~/.talk2ai/
  ├── mode          ← "ai" | "dictate"
  │                   escrito por: talk2ai-keys / tray
  │                   leído por:   daemon, handler, tray
  │
  ├── driver        ← nombre del driver activo (ej: "gemini", "claude", "ollama")
  │                   escrito por: tray
  │                   leído por:   daemon, tray
  │
  ├── model         ← modelo activo (escrito por el daemon al arrancar)
  │                   escrito por: daemon al arrancar
  │                   leído por:   tray (tooltip)
  │
  ├── ai-state      ← "idle" | "processing"
  │                   escrito por: daemon
  │                   leído por:   tray (animación latido)
  │
  ├── debug         ← fichero vacío (flag de activación)
  │                   touch/unlink por: tray
  │                   comprobado por:  daemon, handler
  │
  ├── debug.log     ← líneas  timestamp|tipo|texto
  │                   tipos: SEP, INFO, Q, A, STAT, L, D
  │                   escrito por: daemon (IA), handler (dictado)
  │                   leído por:   tray (ventana debug)
  │
  ├── voice-prompt.md  ← instrucciones TTS para el modelo
  ├── errors.log       ← respuestas vacías / errores del driver
  ├── tray.lock        ← flock instancia única del tray
  ├── context/
  │     └── <driver>.md  ← personalidad / contexto persistente por driver
  └── ia/
        └── <driver>     ← driver ejecutable (contrato: $1=prompt, stdout=respuesta)
```

---

## Contrato del driver IA

Cualquier fichero ejecutable en `~/.talk2ai/ia/` puede ser un driver.

```
Entrada:   $1  →  texto del usuario

Entorno:
  TALK2AI_MODEL          modelo a usar (definido por el daemon al arrancar)
  TALK2AI_VOICE_PROMPT   ruta a instrucciones TTS
  TALK2AI_CONTEXT_FILE   ruta al contexto de personalidad (opcional)

Salida:    stdout  →  texto plano en streaming, sin markdown
           stderr  →  mensaje de error si algo falla

Exit:      0  →  éxito
           ≠0 →  error  (daemon lo registra en errors.log)
```

---

## Ciclo de vida del servicio

```
systemd --user
    └── talk2ai.service
            │
            ├── arranca talk2ai-daemon
            │       │
            │       ├── _init_talk2ai()
            │       │     copia driver, voice-prompt, inicializa archivos
            │       │
            │       ├── detecta sesión (Wayland / X11)
            │       │
            │       ├── lanza talk2ai-keys (Wayland)
            │       │   o xbindkeys (X11)
            │       │   con keepalive cada 10 s
            │       │
            │       └── bucle polling SQLite cada 1 s
            │
            └── talk2ai-tray.desktop  (autostart KDE)
                    └── talk2ai-tray
                            ├── flock tray.lock (instancia única)
                            ├── QFileSystemWatcher sobre mode/driver/state
                            └── check_status() cada 3 s en hilo aparte
```

---

## Dependencias del sistema

| Herramienta   | Función                                      |
|---------------|----------------------------------------------|
| `handy`        | STT (Whisper local), graba y transcribe — [handy.computer](https://handy.computer) |
| driver de IA   | ejecutable en `~/.talk2ai/ia/` — por defecto Gemini CLI |
| `espeak-ng`    | TTS — síntesis de voz en español              |
| `ydotool`      | Inyección de teclado vía uinput (Wayland)     |
| `xdotool`      | Inyección de teclado fallback (X11)           |
| `xbindkeys`    | Atajos globales en X11                        |
| `python-evdev` | Lectura de /dev/input para atajos globales    |
| `python-pyqt6` | Tray icon y ventana debug                    |
| `python-dbus`  | Comunicación con el entorno de escritorio     |
| `sqlite3`      | Lectura directa de la BD de Handy             |
| `notify-send`  | Notificaciones KDE (enlaces clickables)       |
| `xdg-open`     | Abrir URLs en el navegador por defecto        |
