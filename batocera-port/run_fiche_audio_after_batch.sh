#!/usr/bin/env bash
# Attend la fin du batch quiz/flashcard en cours (PID donné en argument), puis
# enchaîne automatiquement sur la génération audio des fiches - jamais les
# deux en parallèle (même backend VoiceStudio/GPU).
set -u
QUIZ_PID="$1"
echo "[chain] attente de la fin du batch quiz/flashcard (PID $QUIZ_PID)..."
while kill -0 "$QUIZ_PID" 2>/dev/null; do
    sleep 30
done
echo "[chain] batch quiz/flashcard terminé, vérification VoiceStudio..."
for i in $(seq 1 20); do
    status=$(curl -s -m 3 http://127.0.0.1:3900/health | python3 -c "import sys,json;print(json.load(sys.stdin).get('status',''))" 2>/dev/null)
    if [ "$status" = "ok" ]; then
        echo "[chain] VoiceStudio pret, lancement de la generation audio des fiches."
        cd /home/adm1/PSE25-27/batocera-port
        exec python3 generate_fiche_audio_voicestudio.py
    fi
    sleep 15
done
echo "[chain] VoiceStudio indisponible apres attente, abandon."
exit 1
