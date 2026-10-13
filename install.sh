#!/bin/bash
# talk2ai installer

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Keep the historic state location for compatibility with existing installs;
# new installs use XDG state unless TALK2AI_DIR is explicitly provided.
# There is no XDG base-directory standard for executable user scripts; use the
# conventional location also referenced by the user systemd units.
BIN_DIR="$HOME/.local/bin"
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
SYSTEMD_DIR="$XDG_CONFIG_HOME/systemd/user"
AUTOSTART_DIR="$XDG_CONFIG_HOME/autostart"
LEGACY_TALK2AI_DIR="$HOME/.talk2ai"
TALK2AI_DIR="${TALK2AI_DIR:-$(if [[ -d "$LEGACY_TALK2AI_DIR" ]]; then printf '%s' "$LEGACY_TALK2AI_DIR"; else printf '%s/talk2ai' "${XDG_STATE_HOME:-$HOME/.local/state}"; fi)}"
TTS_DATA_DIR="${TALK2AI_DATA_DIR:-$XDG_DATA_HOME/talk2ai}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✔${NC}  $*"; }
warn() { echo -e "  ${YELLOW}⚠${NC}  $*"; }
err()  { echo -e "  ${RED}✘${NC}  $*"; }
info() { echo -e "  ${CYAN}→${NC}  $*"; }
step() { echo -e "\n${BOLD}$*${NC}"; }

# ── Sanity checks ──────────────────────────────────────────────────────────────

if [[ $EUID -eq 0 ]]; then
    err "No ejecutes el instalador como root."
    exit 1
fi

echo -e "\n${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║         talk2ai  —  instalador       ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}\n"

# ── Detener procesos previos ───────────────────────────────────────────────────

step "0/7  Detener procesos existentes"

systemctl --user stop talk2ai.service 2>/dev/null && ok "Servicio detenido" || true
systemctl --user stop talk2ai-tts.service 2>/dev/null && ok "Broker TTS detenido" || true

stop_tray() {
    local lock="$TALK2AI_DIR/tray.lock" pid cmd
    [[ -f "$lock" ]] || return 0
    pid=$(head -n 1 "$lock" 2>/dev/null || true)
    # Older releases left an empty lock. Discover only the exact installed
    # executable and verify its /proc command line; never use pkill -f.
    if [[ ! "$pid" =~ ^[0-9]+$ ]]; then
        while read -r candidate; do
            [[ -r "/proc/$candidate/cmdline" ]] || continue
            cmd=$(tr '\0' ' ' < "/proc/$candidate/cmdline")
            if [[ "$cmd" == *"$BIN_DIR/talk2ai-tray"* ]]; then
                pid="$candidate"
                break
            fi
        done < <(pgrep -f -- "$BIN_DIR/talk2ai-tray" 2>/dev/null || true)
    fi
    if [[ "$pid" =~ ^[0-9]+$ ]] && [[ -r "/proc/$pid/cmdline" ]]; then
        cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline")
        if [[ "$cmd" == *"$BIN_DIR/talk2ai-tray"* ]]; then
            kill -TERM "$pid" 2>/dev/null || true
            for _ in {1..30}; do
                kill -0 "$pid" 2>/dev/null || break
                sleep 0.1
            done
            if kill -0 "$pid" 2>/dev/null; then
                warn "El tray no terminó ordenadamente (PID $pid); no se elimina su lock"
                return 1
            fi
            ok "Tray detenido (PID $pid)"
        fi
    fi
    if [[ -n "$pid" ]] && [[ -e "/proc/$pid" ]]; then
        warn "Lock del tray pertenece a un proceso no verificable; no se elimina"
        return 1
    fi
    rm -f "$lock"
}

stop_tray

# ── Detectar gestor de paquetes ───────────────────────────────────────────────

step "1/7  Dependencias del sistema"

if command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
    INSTALL_CMD="sudo pacman -S --needed --noconfirm"
    PKGS=(xdotool ydotool espeak-ng alsa-utils sqlite3 xbindkeys
          python-pyqt6 python-dbus python-gobject python-evdev python-virtualenv)
elif command -v apt &>/dev/null; then
    PKG_MANAGER="apt"
    INSTALL_CMD="sudo apt install -y"
    PKGS=(xdotool ydotool espeak-ng alsa-utils sqlite3 xbindkeys
          python3-pyqt6 python3-dbus python3-gi python3-evdev python3-venv)
else
    warn "Gestor de paquetes no reconocido. Instala manualmente:"
    warn "  xdotool ydotool espeak-ng sqlite3 xbindkeys"
    warn "  python-pyqt6 python-dbus python-gobject python-evdev"
    PKG_MANAGER=""
fi

MISSING=()
if [[ "$PKG_MANAGER" == "pacman" ]]; then
    for pkg in "${PKGS[@]}"; do
        pacman -Q "$pkg" &>/dev/null || MISSING+=("$pkg")
    done
elif [[ "$PKG_MANAGER" == "apt" ]]; then
    for pkg in "${PKGS[@]}"; do
        dpkg -s "$pkg" &>/dev/null || MISSING+=("$pkg")
    done
fi

if [[ ${#MISSING[@]} -gt 0 ]]; then
    info "Instalando: ${MISSING[*]}"
    $INSTALL_CMD "${MISSING[@]}"
    ok "Dependencias instaladas"
else
    ok "Todas las dependencias ya están presentes"
fi

# ── ydotool ───────────────────────────────────────────────────────────────────

if ! systemctl --user is-enabled ydotool.service &>/dev/null; then
    info "Activando ydotool.service..."
    systemctl --user enable --now ydotool.service
    ok "ydotool.service activado"
else
    ok "ydotool.service ya estaba activo"
fi

# ── Grupo input ───────────────────────────────────────────────────────────────

if ! groups "$USER" | grep -q '\binput\b'; then
    info "Añadiendo $USER al grupo input..."
    sudo usermod -aG input "$USER"
    warn "Deberás cerrar sesión y volver a entrar para que los atajos Wayland funcionen"
else
    ok "Usuario ya pertenece al grupo input"
fi

# ── Comprobar y configurar Handy ─────────────────────────────────────────────

step "2/7  Comprobar y configurar Handy"

HANDY_SETTINGS="$HOME/.local/share/com.pais.handy/settings_store.json"

if command -v handy &>/dev/null; then
    ok "Handy encontrado: $(which handy)"

    if [[ -f "$HANDY_SETTINGS" ]]; then
        # Configurar external_script_path y paste_method via python3
        python3 - "$HANDY_SETTINGS" "$BIN_DIR/talk2ai-handler" <<'PYEOF'
import sys, json
path, script = sys.argv[1], sys.argv[2]
with open(path) as f:
    cfg = json.load(f)
s = cfg.setdefault("settings", {})
s["paste_method"] = "external_script"
s["external_script_path"] = script
# Desactivar el atajo interno de Ctrl+Space para evitar doble disparo
bindings = s.setdefault("bindings", {})
if "transcribe" in bindings:
    bindings["transcribe"]["current_binding"] = ""
with open(path, "w") as f:
    json.dump(cfg, f, indent=4)
PYEOF
        ok "Handy configurado: paste_method=external_script"
        ok "Handy configurado: external_script_path=$BIN_DIR/talk2ai-handler"
        ok "Handy configurado: atajo interno de transcripción desactivado"
    else
        warn "Handy aún no tiene configuración guardada"
        warn "Ábrelo una vez, ciérralo y vuelve a ejecutar el instalador"
        warn "O configúralo manualmente → Avanzado → External Script:"
        warn "  $BIN_DIR/talk2ai-handler"
    fi
else
    warn "Handy no está en PATH"
    warn "Descárgalo desde https://handy.computer y colócalo en ~/.local/bin/handy"
    warn "Luego vuelve a ejecutar el instalador para configurarlo automáticamente"
fi

# ── Comprobar driver de IA ────────────────────────────────────────────────────

step "3/7  Comprobar drivers de IA"

if command -v agy &>/dev/null; then
    ok "Antigravity AGY CLI encontrado: $(which agy)"
elif command -v gemini &>/dev/null; then
    ok "Gemini CLI encontrado: $(which gemini)"
else
    warn "CLI de Gemini/AGY no encontrado (driver por defecto)"
    warn "Asegúrate de tener 'agy' o 'gemini' instalado en PATH"
fi

if [[ -f "$TALK2AI_DIR/ollama-host" ]]; then
    ok "Ollama configurado: $(cat "$TALK2AI_DIR/ollama-host")"
else
    info "Ollama (opcional): si tienes un servidor Ollama, configúralo desde"
    info "  el menú del tray → Ollama → Cambiar servidor…"
fi

# ── Scripts ───────────────────────────────────────────────────────────────────

step "4/7  Instalar scripts y drivers"

mkdir -p "$BIN_DIR" "$TALK2AI_DIR/ia" "$TTS_DATA_DIR"

SCRIPTS=(talk2ai-daemon talk2ai-handler talk2ai-tray talk2ai-keys talk2ai-control talk2ai-tts talk2ai-tts-kokoro)
for s in "${SCRIPTS[@]}"; do
    cp "$REPO_DIR/scripts/$s" "$BIN_DIR/$s"
    chmod +x "$BIN_DIR/$s"
    ok "$s → $BIN_DIR/$s"
done

# Catálogo cerrado y manifiesto de hashes: son datos versionados del programa,
# no preferencias del usuario. Se actualizan en cada instalación; las
# preferencias tts-engine, tts-voice y tts-speed permanecen intactas.
# No se descarga ningún modelo ni runtime neuronal durante la instalación.
for tts_config in tts-catalog.json tts-artifacts.json; do
    install -m 0644 "$REPO_DIR/config/$tts_config" "$TTS_DATA_DIR/$tts_config"
done
[ -f "$TALK2AI_DIR/tts-engine" ] || echo "espeak-ng" > "$TALK2AI_DIR/tts-engine"
[ -f "$TALK2AI_DIR/tts-voice" ] || echo "es" > "$TALK2AI_DIR/tts-voice"
[ -f "$TALK2AI_DIR/tts-speed" ] || echo "140" > "$TALK2AI_DIR/tts-speed"
mkdir -p "$TALK2AI_DIR/tts/tmp"
ok "TTS Retro configurado; Kokoro sigue como descarga explícita y verificada"

# Drivers de IA
for driver_src in "$REPO_DIR/config/ia/"*; do
    driver_name="$(basename "$driver_src")"
    cp "$driver_src" "$TALK2AI_DIR/ia/$driver_name"
    chmod +x "$TALK2AI_DIR/ia/$driver_name"
    ok "driver $driver_name → $TALK2AI_DIR/ia/$driver_name"
done

# Asegurar que ~/.local/bin está en PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    warn "$BIN_DIR no está en PATH"
    warn "Añade a tu shell:  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

# ── Servicio systemd y autostart ──────────────────────────────────────────────

step "5/7  Configurar servicio systemd"

mkdir -p "$SYSTEMD_DIR" "$AUTOSTART_DIR"

cp "$REPO_DIR/config/talk2ai.service"      "$SYSTEMD_DIR/talk2ai.service"
cp "$REPO_DIR/config/talk2ai-tts.service"  "$SYSTEMD_DIR/talk2ai-tts.service"
# User services do not necessarily inherit variables from the installer shell.
# Materialize the selected portable paths in the units on every upgrade.
python3 - "$SYSTEMD_DIR/talk2ai.service" "$SYSTEMD_DIR/talk2ai-tts.service" "$TALK2AI_DIR" "$TTS_DATA_DIR" <<'PYEOF'
from pathlib import Path
import sys

service_paths = list(map(Path, sys.argv[1:3]))
state, data = sys.argv[3:]
def quote(value):
    return value.replace('\\', '\\\\').replace('"', '\\"')
for path in service_paths:
    text = path.read_text(encoding="utf-8")
    text = text.replace("Environment=TALK2AI_DIR=@TALK2AI_DIR@", f'Environment="TALK2AI_DIR={quote(state)}"')
    text = text.replace("Environment=TALK2AI_DATA_DIR=@TALK2AI_DATA_DIR@", f'Environment="TALK2AI_DATA_DIR={quote(data)}"')
    path.write_text(text, encoding="utf-8")
PYEOF
# Desktop Entry does not support systemd's %h specifier.  Materialize the
# current user's executable path at install time, with desktop-entry escaping
# for the unusual but valid case of spaces in HOME.
python3 - "$REPO_DIR/config/talk2ai-tray.desktop" "$AUTOSTART_DIR/talk2ai-tray.desktop" "$BIN_DIR/talk2ai-tray" "$TALK2AI_DIR" "$TTS_DATA_DIR" <<'PYEOF'
from pathlib import Path
import sys

template, destination, executable = map(Path, sys.argv[1:4])
state, data = sys.argv[4:]
escaped = str(executable).replace("\\", "\\\\").replace('"', '\\"')
entry = template.read_text(encoding="utf-8").replace(
    'Exec=env TALK2AI_DIR="@TALK2AI_DIR@" TALK2AI_DATA_DIR="@TALK2AI_DATA_DIR@" talk2ai-tray',
    f'Exec=env TALK2AI_DIR="{state.replace(chr(34), chr(92) + chr(34))}" '
    f'TALK2AI_DATA_DIR="{data.replace(chr(34), chr(92) + chr(34))}" "{escaped}"', 1
)
destination.write_text(entry, encoding="utf-8")
PYEOF
ok "talk2ai.service instalado"
ok "talk2ai-tray.desktop instalado (autostart)"

# Atajos X11
if [[ "${XDG_SESSION_TYPE:-}" != "wayland" ]]; then
    cp "$REPO_DIR/config/xbindkeysrc" "$HOME/.xbindkeysrc"
    TALK2AI_DIR_ESCAPED=${TALK2AI_DIR//\\/\\\\}
    TALK2AI_DIR_ESCAPED=${TALK2AI_DIR_ESCAPED//|/\\|}
    sed -i "s|@TALK2AI_DIR@|$TALK2AI_DIR_ESCAPED|g" "$HOME/.xbindkeysrc"
    ok "~/.xbindkeysrc instalado (atajos X11)"
fi

systemctl --user daemon-reload
systemctl --user enable talk2ai-tts.service talk2ai.service
info "Iniciando servicios..."
systemctl --user restart talk2ai-tts.service
systemctl --user restart talk2ai.service
sleep 2

for service in talk2ai-tts.service talk2ai.service; do
    if systemctl --user is-active "$service" &>/dev/null; then
        ok "$service activo y corriendo"
    else
        err "$service no arrancó. Revisa:"
        err "  journalctl --user -u $service -n 30"
    fi
done

# ── Contexto de personalidad (opcional) ──────────────────────────────────────

step "6/7  voice-prompt y contexto de personalidad"

mkdir -p "$TALK2AI_DIR/context"

# versión instalada (usada por el tray para mostrar actualizaciones)
cp "$REPO_DIR/VERSION" "$TALK2AI_DIR/version"
ok "version → $TALK2AI_DIR/version  ($(cat "$REPO_DIR/VERSION" | tr -d '\n'))"

# voice-prompt genérico + específicos por driver
cp "$REPO_DIR/config/voice-prompt.md" "$TALK2AI_DIR/voice-prompt.md"
ok "voice-prompt.md → $TALK2AI_DIR/voice-prompt.md"
for vp_src in "$REPO_DIR/config/voice-prompt-"*.md; do
    [ -f "$vp_src" ] || continue
    vp_name="$(basename "$vp_src")"
    cp "$vp_src" "$TALK2AI_DIR/$vp_name"
    ok "$vp_name → $TALK2AI_DIR/$vp_name"
done
info "Edita los prompts en $TALK2AI_DIR/voice-prompt*.md para personalizar cada driver"

if [[ ! -f "$TALK2AI_DIR/context/gemini.md" ]]; then
    read -r -p "  ¿Instalar contexto de personalidad por defecto? [s/N] " resp
    if [[ "${resp,,}" == "s" ]]; then
        cp "$REPO_DIR/config/gemini-context.md" "$TALK2AI_DIR/context/gemini.md"
        ok "Contexto instalado en $TALK2AI_DIR/context/gemini.md"
    else
        info "Omitido. Puedes instalarlo luego:"
        info "  cp config/gemini-context.md ~/.talk2ai/context/gemini.md"
    fi
else
    ok "Contexto ya existente, no se sobreescribe"
fi

# ── Verificación final ────────────────────────────────────────────────────────

step "7/7  Verificación"

# Scripts
all_ok=true
for s in "${SCRIPTS[@]}"; do
    if [[ -x "$BIN_DIR/$s" ]]; then
        ok "$s instalado"
    else
        err "$s FALTA"
        all_ok=false
    fi
done

# Drivers
for driver_src in "$REPO_DIR/config/ia/"*; do
    driver_name="$(basename "$driver_src")"
    if [[ -x "$TALK2AI_DIR/ia/$driver_name" ]]; then
        ok "driver $driver_name instalado"
    else
        err "driver $driver_name FALTA"
        all_ok=false
    fi
done

# Systemd
for service in talk2ai-tts.service talk2ai.service; do
    if systemctl --user is-active "$service" &>/dev/null; then
        ok "$service activo"
    else
        err "$service NO activo — revisa: journalctl --user -u $service -n 30"
        all_ok=false
    fi
done

# Lanzar tray
if [[ -x "$BIN_DIR/talk2ai-tray" ]] && ! pgrep -f "$BIN_DIR/talk2ai-tray" >/dev/null 2>&1; then
    nohup "$BIN_DIR/talk2ai-tray" &>/dev/null &
    disown
    sleep 1
    if pgrep -f "$BIN_DIR/talk2ai-tray" &>/dev/null; then
        ok "Tray lanzado"
    else
        warn "Tray no pudo arrancar — prueba: talk2ai-tray"
        all_ok=false
    fi
fi

$all_ok && ok "Todo OK" || warn "Algunas comprobaciones fallaron (ver arriba)"

# ── Resumen ───────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║        Instalación completada        ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "  Modo actual:   $(cat "$TALK2AI_DIR/mode"   2>/dev/null || echo '—')"
echo -e "  Driver activo: $(cat "$TALK2AI_DIR/driver"  2>/dev/null || echo '—')"
echo -e "  Modelo:        $(cat "$TALK2AI_DIR/model"   2>/dev/null || echo '—')"
echo ""
echo -e "  ${BOLD}Atajos:${NC}"
echo -e "    Alt+Super+G   → modo IA"
echo -e "    Alt+Super+H   → modo Dictado"
echo -e "    Ctrl+Space    → grabar / parar (PTT)"
echo -e "    Ctrl+Alt+Q    → detener audio"
echo ""
echo -e "  Logs: journalctl --user -u talk2ai.service -f"
echo ""

notify-send "talk2ai instalado" \
    "Servicio activo · Driver: $(cat "$TALK2AI_DIR/driver" 2>/dev/null || echo '—') · Modelo: $(cat "$TALK2AI_DIR/model" 2>/dev/null || echo '—')" \
    --icon=dialog-ok --urgency=normal 2>/dev/null || true
