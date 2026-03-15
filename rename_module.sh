#!/bin/bash

# --- CONFIGURATION ET COULEURS ---
GREEN=$'\e[32m'
RED=$'\e[31m'
CYAN=$'\e[36m'
YELLOW=$'\e[33m'
NC=$'\e[0m'

QUIZ_DIR="./quizz"
FLASH_DIR="./flashcard"
TP_DIR="./tp"
FICHE_DIR="./fiche"
INFO_DIR="./infographie"
PODCAST_DIR="./podcast"
JSON_FILE="modules.json"

# --- FONCTION DE RÉÉCRITURE PROPRE DU JSON ---
# Cette fonction garantit que le JSON est toujours bien formaté
rewrite_json() {
    cp "$JSON_FILE" "$JSON_FILE.bak"
    echo "[" > "$JSON_FILE"
    local count=${#json_bases[@]}
    local i=0
    for m in "${json_bases[@]}"; do
        if [ $i -lt $((count - 1)) ]; then
            echo "    \"$m.csv\"," >> "$JSON_FILE"
        else
            echo "    \"$m.csv\"" >> "$JSON_FILE" # Le dernier élément n'a pas de virgule
        fi
        ((i++))
    done
    echo "]" >> "$JSON_FILE"
}

# --- BOUCLE PRINCIPALE ---
while true; do
    clear
    echo "========================================="
    echo "      GESTIONNAIRE DE MODULES V39"
    echo "========================================="
    echo ""

    # 1. Chargement de la source de vérité (compatible Mac/Linux sans array avancé)
    if [ ! -f "$JSON_FILE" ]; then
        echo "${RED}Erreur CRITIQUE : Le fichier $JSON_FILE est introuvable.${NC}"
        exit 1
    fi

    json_bases=()
    while IFS= read -r line; do
        json_bases+=("$line")
    done < <(grep -o '"[^"]*"' "$JSON_FILE" | sed 's/"//g' | sed 's/\.csv$//')

    echo "Source de vérité : $JSON_FILE (${#json_bases[@]} modules référencés)"
    echo "Que souhaitez-vous faire ?"
    echo "  1) Gérer / Renommer un module existant"
    echo "  2) Chercher et intégrer des fichiers orphelins"
    echo "  0) Quitter"
    echo ""
    read -p "Votre choix : " main_choice

    case $main_choice in
        0)
            echo "Fermeture du script."
            exit 0
            ;;
        
        1)
            # ==========================================================
            # SOUS-MENU 1 : GESTION ET RENOMMAGE
            # ==========================================================
            echo ""
            echo "Sélectionnez le module à inspecter/renommer :"
            PS3="Choix du module (0 pour annuler) : "
            select old_base in "${json_bases[@]}"; do
                if [ "$REPLY" == "0" ]; then
                    break
                elif [ -n "$old_base" ]; then
                    # --- TABLEAU DE VÉRIFICATION D'INTÉGRITÉ ---
                    echo ""
                    echo "==============================================================="
                    echo " CONTRÔLE D'INTÉGRITÉ : $old_base"
                    echo "==============================================================="
                    printf "%-15s | %-35s | %-10s\n" "TYPE" "FICHIER ATTENDU" "STATUT"
                    echo "---------------------------------------------------------------"

                    check_file() {
                        local type=$1
                        local file_path=$2
                        local filename=$(basename "$file_path")
                        if [ -f "$file_path" ]; then
                            printf "%-15s | %-35s | ${GREEN}%-10s${NC}\n" "$type" "$filename" "[OK]"
                        else
                            printf "%-15s | %-35s | ${RED}%-10s${NC}\n" "$type" "$filename" "[KO]"
                        fi
                    }

                    check_file "Quiz" "$QUIZ_DIR/$old_base.csv"
                    check_file "Flashcard" "$FLASH_DIR/$old_base.csv"
                    check_file "TP" "$TP_DIR/$old_base.csv"
                    check_file "Fiche" "$FICHE_DIR/$old_base.txt"
                    check_file "Infographie" "$INFO_DIR/$old_base.png"
                    check_file "Podcast" "$PODCAST_DIR/$old_base.m4a"
                    echo "---------------------------------------------------------------"
                    echo ""

                    read -p "Entrez le nouveau nom (sans extension) ou 'A' pour annuler : " new_base
                    if [[ -z "$new_base" || "$new_base" == "A" || "$new_base" == "a" ]]; then
                        echo "Annulation..."
                        sleep 1
                        break
                    fi

                    if [ "$old_base" == "$new_base" ]; then
                        echo "Nom identique. Annulation..."
                        sleep 2
                        break
                    fi

                    echo ""
                    echo "--- Début du renommage ---"
                    rename_if_exists() {
                        local dir=$1
                        local ext=$2
                        if [ -f "$dir/$old_base$ext" ]; then
                            mv "$dir/$old_base$ext" "$dir/$new_base$ext"
                            echo "  -> Renommé : $dir/$new_base$ext"
                        fi
                    }

                    rename_if_exists "$QUIZ_DIR" ".csv"
                    rename_if_exists "$FLASH_DIR" ".csv"
                    rename_if_exists "$TP_DIR" ".csv"
                    rename_if_exists "$FICHE_DIR" ".txt"
                    rename_if_exists "$INFO_DIR" ".png"
                    rename_if_exists "$PODCAST_DIR" ".m4a"

                    # Mise à jour de la mémoire et réécriture du JSON
                    for i in "${!json_bases[@]}"; do
                        if [ "${json_bases[$i]}" == "$old_base" ]; then
                            json_bases[$i]="$new_base"
                        fi
                    done
                    rewrite_json
                    echo "  -> $JSON_FILE mis à jour."
                    
                    echo "--- Terminé ---"
                    read -p "Appuyez sur Entrée pour continuer..."
                    break
                else
                    echo "Sélection invalide."
                fi
            done
            ;;

        2)
            # ==========================================================
            # SOUS-MENU 2 : DÉTECTION DES ORPHELINS
            # ==========================================================
            echo ""
            echo "Analyse des répertoires en cours..."
            
            # Récupère tous les fichiers, extrait le nom sans l'extension et dédoublonne
            all_bases=$(find "$QUIZ_DIR" "$FLASH_DIR" "$TP_DIR" "$FICHE_DIR" "$INFO_DIR" "$PODCAST_DIR" -type f 2>/dev/null | rev | cut -d/ -f1 | rev | sed -E 's/\.(csv|txt|png|m4a)$//' | sort -u)

            orphans=()
            while IFS= read -r base; do
                [ -z "$base" ] && continue
                is_in_json=0
                for jb in "${json_bases[@]}"; do
                    if [ "$jb" == "$base" ]; then
                        is_in_json=1
                        break
                    fi
                done
                if [ $is_in_json -eq 0 ]; then
                    orphans+=("$base")
                fi
            done <<< "$all_bases"

            if [ ${#orphans[@]} -eq 0 ]; then
                echo "${GREEN}Excellente nouvelle : Aucun fichier orphelin détecté.${NC}"
                echo "Tous les fichiers présents dans vos dossiers sont bien référencés dans modules.json."
                read -p "Appuyez sur Entrée pour revenir au menu..."
                continue
            fi

            echo "${YELLOW}Attention : ${#orphans[@]} module(s) trouvé(s) dans les dossiers mais absent(s) de modules.json.${NC}"
            echo "Lequel souhaitez-vous intégrer à l'application ?"
            
            PS3="Choix (0 pour annuler) : "
            select orphan_choice in "${orphans[@]}"; do
                if [ "$REPLY" == "0" ]; then
                    break
                elif [ -n "$orphan_choice" ]; then
                    # Ajout du nouvel orphelin à notre tableau en mémoire
                    json_bases+=("$orphan_choice")
                    
                    # Réécriture propre du fichier JSON
                    rewrite_json
                    
                    echo ""
                    echo "${GREEN}Succès !${NC} Le module \"$orphan_choice\" a été ajouté à modules.json."
                    echo "Il est désormais visible dans l'application."
                    read -p "Appuyez sur Entrée pour continuer..."
                    break
                else
                    echo "Sélection invalide."
                fi
            done
            ;;

        *)
            echo "Choix invalide."
            sleep 1
            ;;
    esac
done
