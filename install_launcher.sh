#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$(realpath -- "$0")")"
[[ $EUID != 0 ]] || { echo 'Run as your desktop user, not root'; exit 1; }
command -v python3 >/dev/null || { echo 'Python 3 is required to generate desktop entries (no Tkinter).'; exit 1; }
python3 - <<'PY'
from pathlib import Path
import shutil, subprocess
root=Path.cwd(); home=Path.home()
def quote(s):
    # Exec quoting and desktop-entry string escaping are separate layers.
    v=str(s).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')
    return ('"'+v+'"').replace('\\','\\\\')
apps=home/'.local/share/applications'; apps.mkdir(parents=True,exist_ok=True)
try:
    desktop=Path(subprocess.check_output(['xdg-user-dir','DESKTOP'],text=True).strip())
except (OSError, subprocess.CalledProcessError):
    desktop=home/'Desktop'
for filename,name,script,args,icon in [
    ('movella-dot.desktop','Launch Movella DOT','run_movella.sh','network','bluetooth'),
    ('movella-dot-setup.desktop','Install / Repair Movella DOT','setup_dependencies.sh','--repair','system-software-install')]:
    # Hold the terminal on failure so the user can read diagnostics.
    command='"$@"; rc=$?; if [ "$rc" -ne 0 ]; then printf "\\nFailed (exit %s). Press Enter to close.\\n" "$rc"; read -r _; fi; exit "$rc"'
    exec_line='/bin/bash -c '+quote(command)+' movella /bin/bash '+quote(root/script)+' '+args
    entry=apps/filename
    entry.write_text('[Desktop Entry]\nType=Application\nName='+name+'\nExec='+exec_line+'\nIcon='+icon+'\nTerminal=true\nCategories=Science;Utility;\n')
    entry.chmod(0o755)
    if desktop.is_dir() and desktop != home: shutil.copy2(entry,desktop/filename)
PY
echo 'Shortcuts installed. If required, mark the desktop files trusted in your file manager.'
