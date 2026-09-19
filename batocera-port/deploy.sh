#!/usr/bin/env bash
# Déploie le dossier local batocera-port/pse2527 vers le partage réseau Batocera
# (smb://batocerasalon.local/share/roms/pygame/pse2527/), fichier par fichier via gio.
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/pse2527" && pwd)"
DEST_BASE="smb://batocerasalon.local/share/roms/pygame/pse2527"

echo "Source : $SRC_DIR"
echo "Destination : $DEST_BASE"

# Recrée l'arborescence des dossiers
find "$SRC_DIR" -type d | while read -r dir; do
    rel="${dir#$SRC_DIR}"
    dest="$DEST_BASE$rel"
    gio mkdir -p "$dest" 2>/dev/null || true
done

# Copie chaque fichier
count=0
find "$SRC_DIR" -type f | while read -r file; do
    rel="${file#$SRC_DIR}"
    dest="$DEST_BASE$rel"
    gio copy -p "$file" "$dest"
    count=$((count + 1))
done

echo "Terminé."
