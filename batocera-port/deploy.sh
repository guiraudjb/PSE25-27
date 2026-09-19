#!/usr/bin/env bash
# Déploie le dossier local batocera-port/pse2527 vers le partage réseau Batocera
# (smb://batocerasalon.local/share/roms/pygame/pse2527/), fichier par fichier via gio.
#
# Le protocole SMB ne préserve ni les liens symboliques ni le bit exécutable
# (constaté avec le binaire Piper et ses .so versionnés) : `find -type f`
# ignore les liens (ce ne sont pas des fichiers réguliers), et gio copy -p ne
# réplique pas le mode Unix via un partage SMB. On corrige donc les deux après
# coup via SSH (accès root déjà en place sur cette machine).
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/pse2527" && pwd)"
DEST_BASE="smb://batocerasalon.local/share/roms/pygame/pse2527"
SSH_HOST="root@192.168.1.38"
REMOTE_BASE="/userdata/roms/pygame/pse2527"

echo "Source : $SRC_DIR"
echo "Destination : $DEST_BASE"

# Recrée l'arborescence des dossiers
find "$SRC_DIR" -type d | while read -r dir; do
    rel="${dir#$SRC_DIR}"
    dest="$DEST_BASE$rel"
    gio mkdir -p "$dest" 2>/dev/null || true
done

# Copie chaque fichier régulier (les liens symboliques sont traités à part plus bas)
find "$SRC_DIR" -type f | while read -r file; do
    rel="${file#$SRC_DIR}"
    dest="$DEST_BASE$rel"
    gio copy -p "$file" "$dest"
done

echo "Fichiers copiés. Correction des permissions et des liens symboliques via SSH..."

# Recrée les liens symboliques locaux sur la machine distante (chemin relatif,
# donc valides même si REMOTE_BASE est monté ailleurs qu'attendu)
LINK_CMDS="$(find "$SRC_DIR" -type l -printf '%P\t%l\n' | while IFS=$'\t' read -r rel target; do
    printf 'ln -sf %q %q\n' "$target" "$REMOTE_BASE/$rel"
done)"

# Restaure le bit exécutable pour les fichiers qui l'ont localement
CHMOD_CMDS="$(find "$SRC_DIR" -type f -perm -u+x -printf '%P\n' | while read -r rel; do
    printf 'chmod +x %q\n' "$REMOTE_BASE/$rel"
done)"

if [ -n "$LINK_CMDS" ] || [ -n "$CHMOD_CMDS" ]; then
    ssh "$SSH_HOST" bash <<EOF
$LINK_CMDS
$CHMOD_CMDS
EOF
fi

echo "Terminé."
