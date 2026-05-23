#!/bin/bash
# talk2ai installer

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SYSTEMD_DIR="$HOME/.config/systemd/user"
AUTOSTART_DIR="$HOME/.config/autostart"
TALK2AI_DIR="$HOME/.talk2ai"

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
pkill -f "talk2ai-tray"  2>/dev/null && ok "Tray detenido"    || true
pkill -f "talk2ai-keys"  2>/dev/null && ok "Keys detenido"    || true
pkill -f "talk2ai-daemon" 2>/dev/null && ok "Daemon detenido" || true
sleep 1
rm -f "$TALK2AI_DIR/tray.lock" && true

# ── Detectar gestor de paquetes ───────────────────────────────────────────────

step "1/7  Dependencias del sistema"

if command -v pacman &>/dev/null; then
    PKG_MANAGER="pacman"
    INSTALL_CMD="sudo pacman -S --needed --noconfirm"
    PKGS=(xdotool ydotool espeak-ng sqlite3 xbindkeys
          python-pyqt6 python-dbus python-gobject python-evdev)
elif command -v apt &>/dev/null; then
    PKG_MANAGER="apt"
    INSTALL_CMD="sudo apt install -y"
    PKGS=(xdotool ydotool espeak-ng sqlite3 xbindkeys
          python3-pyqt6 python3-dbus python3-gi python3-evdev)
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

if command -v gemini &>/dev/null; then
    ok "Gemini CLI encontrado: $(which gemini)"
else
    warn "Gemini CLI no encontrado (driver por defecto)"
    warn "Instálalo con:  npm install -g @google/gemini-cli"
    warn "Luego autentícate:  gemini auth login"
fi

if [[ -f "$TALK2AI_DIR/ollama-host" ]]; then
    ok "Ollama configurado: $(cat "$TALK2AI_DIR/ollama-host")"
else
    info "Ollama (opcional): si tienes un servidor Ollama, configúralo desde"
    info "  el menú del tray → Ollama → Cambiar servidor…"
fi

# ── Scripts ───────────────────────────────────────────────────────────────────

step "4/7  Instalar scripts y drivers"

mkdir -p "$BIN_DIR" "$TALK2AI_DIR/ia"

SCRIPTS=(talk2ai-daemon talk2ai-handler talk2ai-tray talk2ai-keys talk2ai-control)
for s in "${SCRIPTS[@]}"; do
    cp "$REPO_DIR/scripts/$s" "$BIN_DIR/$s"
    chmod +x "$BIN_DIR/$s"
    ok "$s → $BIN_DIR/$s"
done

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
cp "$REPO_DIR/config/talk2ai-tray.desktop" "$AUTOSTART_DIR/talk2ai-tray.desktop"
ok "talk2ai.service instalado"
ok "talk2ai-tray.desktop instalado (autostart)"

# Atajos X11
if [[ "${XDG_SESSION_TYPE:-}" != "wayland" ]]; then
    cp "$REPO_DIR/config/xbindkeysrc" "$HOME/.xbindkeysrc"
    ok "~/.xbindkeysrc instalado (atajos X11)"
fi

systemctl --user daemon-reload
systemctl --user enable talk2ai.service
info "Iniciando servicio..."
systemctl --user restart talk2ai.service
sleep 2

if systemctl --user is-active talk2ai.service &>/dev/null; then
    ok "talk2ai.service activo y corriendo"
else
    err "El servicio no arrancó. Revisa:"
    err "  journalctl --user -u talk2ai.service -n 30"
fi

# ── Contexto de personalidad (opcional) ──────────────────────────────────────

step "6/7  voice-prompt y contexto de personalidad"

mkdir -p "$TALK2AI_DIR/context"

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
if systemctl --user is-active talk2ai.service &>/dev/null; then
    ok "talk2ai.service activo"
else
    err "talk2ai.service NO activo — revisa: journalctl --user -u talk2ai.service -n 30"
    all_ok=false
fi

# Lanzar tray
if [[ -x "$BIN_DIR/talk2ai-tray" ]]; then
    nohup "$BIN_DIR/talk2ai-tray" &>/dev/null &
    disown
    sleep 1
    if pgrep -f talk2ai-tray &>/dev/null; then
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
