#!/usr/bin/env bash
# Déploie le dossier local batocera-port/pse2527 vers les partages réseau des
# machines Batocera, fichier par fichier via gio (SMB uniquement).
#
# Depuis l'abandon de Piper (synthèse vocale à la demande, remplacée par le
# pipeline VoiceStudio pré-calculé en lot), l'arborescence déployée ne
# contient plus aucun lien symbolique ni bit exécutable à restaurer : la
# correction via SSH après coup n'est donc plus nécessaire, SMB seul suffit.
set -uo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/pse2527" && pwd)"

# Toutes les Batocera à synchroniser. Ajouter/retirer des entrées ici si le
# parc change.
HOSTS=(
    "batocerasalon.local"
    "batocera.local"
)

for HOST in "${HOSTS[@]}"; do
    DEST_BASE="smb://$HOST/share/roms/pygame/pse2527"
    echo "=== Déploiement vers $HOST ==="
    echo "Source : $SRC_DIR"
    echo "Destination : $DEST_BASE"

    # Recrée l'arborescence des dossiers
    find "$SRC_DIR" -type d | while read -r dir; do
        rel="${dir#$SRC_DIR}"
        dest="$DEST_BASE$rel"
        gio mkdir -p "$dest" 2>/dev/null || true
    done

    # Copie chaque fichier régulier. Une copie individuelle peut échouer sans
    # que ce soit une vraie erreur : si le jeu tourne en direct sur la machine
    # cible, il peut retenir un handle ouvert (ex. média en cours de lecture)
    # et Samba renvoie alors "device busy" - on avertit et on continue plutôt
    # que d'abandonner toute la synchronisation pour un seul fichier occupé
    # (voir memory batocera-salon-acces-reseau).
    FAILED_LOG="$(mktemp)"
    find "$SRC_DIR" -type f | while read -r file; do
        rel="${file#$SRC_DIR}"
        dest="$DEST_BASE$rel"
        if ! gio copy -p "$file" "$dest" 2>&1; then
            echo "AVERTISSEMENT : échec de copie (probablement fichier occupé par le jeu en cours) : $rel"
            echo "$rel" >> "$FAILED_LOG"
        fi
    done

    if [ -s "$FAILED_LOG" ]; then
        echo "Fichiers copiés vers $HOST (avec $(wc -l < "$FAILED_LOG") échec(s) ci-dessus, probablement verrouillés par le jeu en cours - relancer deploy.sh une fois le jeu quitté pour les rattraper)."
    else
        echo "Fichiers copiés vers $HOST, aucun échec."
    fi
    rm -f "$FAILED_LOG"
    echo
done

echo "Terminé."
