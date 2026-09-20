#!/usr/bin/env python3
"""Pré-génère la narration audio des fiches de révision via VoiceStudio local,
dans pse2527/data/fiche_audio/, lue en jeu via dl.fiche_audio_path() (voir
data_loader.py) et pygame.mixer.music (streaming, pas pygame.mixer.Sound :
ces fichiers sont bien trop longs pour tenir chargés entièrement en mémoire
comme le quiz/flashcard).

Nécessite VoiceStudio démarré (http://127.0.0.1:3900) ET ffmpeg (conversion
WAV->MP3 après génération, pour une taille raisonnable : une narration de
20-30 min en PCM WAV brut pèserait ~150-300 Mo, contre ~5-15 Mo en mp3).

Même voix que generate_tts_voicestudio.py (PROFILE_ID, profil cloné à
référence audio fixe - jamais un archetype `instruct`, voir memory
voicestudio-tts-fiches-wavfiche.md et le skill ajoutfiche). num_step=32 :
c'est justement le réglage retenu à l'origine pour ce cas d'usage précis
(éviter l'artefact de fondu enchaîné entre les chunks internes de VoiceStudio
sur un texte long découpé, max_chunk_chars=800 par défaut côté API).

Débit mesuré sur le batch quiz/flashcard : ~61 caractères/s de génération.
Une fiche moyenne (~18 150 caractères) prend donc ~5 min, la plus longue
mesurée (~61 000 caractères) ~17 min. Pour les 166 fiches (~2,8M caractères
au total) : compter ~13h de génération séquentielle. À ne JAMAIS lancer en
même temps que generate_tts_voicestudio.py (même backend VoiceStudio/GPU,
risque de contention et de corruption du contexte CUDA documenté dans la
memory ci-dessus) - enchaîner après, pas en parallèle.

Usage:
    python3 generate_fiche_audio_voicestudio.py [--limit-modules N]
"""
import argparse
import json
import os
import subprocess
import sys
import time

import requests

GAME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pse2527')
DATA_DIR = os.path.join(GAME_DIR, 'data')
FICHE_DIR = os.path.join(DATA_DIR, 'fiche')
OUT_DIR = os.path.join(DATA_DIR, 'fiche_audio')

VOICESTUDIO_URL = "http://127.0.0.1:3900/generate"
PROFILE_ID = "cc1ebb9c"  # NarrateurPSE_H1_clean : même voix que le quiz/flashcard
LANGUAGE = "fr"
NUM_STEP = 32
CROSSFADE_MS = 50  # défaut API : lissage entre chunks internes sur un texte long
EFFECT_PRESET = "raw"
REQUEST_TIMEOUT_S = 1800  # jusqu'à ~17 min mesurées pour la fiche la plus longue


def synth_fiche(base):
    txt_path = os.path.join(FICHE_DIR, base + '.txt')
    if not os.path.exists(txt_path):
        return 'skip'
    out_path = os.path.join(OUT_DIR, base + '.mp3')
    if os.path.exists(out_path):
        return 'skip'
    with open(txt_path, encoding='utf-8') as f:
        text = f.read()
    if not text.strip():
        return 'skip'

    os.makedirs(OUT_DIR, exist_ok=True)
    t0 = time.time()
    try:
        r = requests.post(VOICESTUDIO_URL, data={
            "text": text, "profile_id": PROFILE_ID, "language": LANGUAGE,
            "num_step": NUM_STEP, "crossfade_ms": CROSSFADE_MS,
            "effect_preset": EFFECT_PRESET,
        }, timeout=REQUEST_TIMEOUT_S)
    except Exception as e:
        print('[ERREUR réseau] {} : {}'.format(base, e), flush=True)
        return 'error'
    if r.status_code != 200:
        print('[ERREUR {}] {} : {}'.format(r.status_code, base, r.text[:200]), flush=True)
        return 'error'

    tmp_wav = out_path + '.tmp.wav'
    with open(tmp_wav, 'wb') as f:
        f.write(r.content)

    tmp_mp3 = out_path + '.tmp.mp3'
    try:
        proc = subprocess.run(
            ['ffmpeg', '-y', '-i', tmp_wav, '-codec:a', 'libmp3lame', '-qscale:a', '4', tmp_mp3],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    finally:
        os.remove(tmp_wav)
    if proc.returncode != 0 or not os.path.exists(tmp_mp3):
        print('[ERREUR ffmpeg] {} : conversion mp3 échouée (code {})'.format(base, proc.returncode), flush=True)
        return 'error'
    os.replace(tmp_mp3, out_path)

    print('[ok] {} ({:.0f}s de génération, {} caractères, {} octets mp3)'.format(
        base, time.time() - t0, len(text), os.path.getsize(out_path)), flush=True)
    return 'ok'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit-modules', type=int, default=None)
    args = ap.parse_args()

    modules = json.load(open(os.path.join(DATA_DIR, 'modules.json'), encoding='utf-8'))
    bases = [m[:-4] for m in modules]
    if args.limit_modules:
        bases = bases[:args.limit_modules]

    stats = {'ok': 0, 'skip': 0, 'error': 0}
    t_start = time.time()

    for i, base in enumerate(bases):
        result = synth_fiche(base)
        stats[result] += 1
        elapsed = time.time() - t_start
        print('=== {}/{} : {} [{}] -- cumul ok={} skip={} error={} -- {:.0f} min écoulées ==='.format(
            i + 1, len(bases), base, result, stats['ok'], stats['skip'], stats['error'], elapsed / 60), flush=True)

    print('TERMINÉ.', stats, flush=True)


if __name__ == '__main__':
    main()
