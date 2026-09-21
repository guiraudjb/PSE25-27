#!/usr/bin/env python3
"""Pré-génère les fichiers audio TTS (quiz + flashcards) via VoiceStudio local,
directement dans pse2527/tts_assets/cache/<module>/, avec la MÊME convention
de sous-dossier/nom que tts.py : le jeu les trouve donc automatiquement en
cache au lancement (plus de synthèse à la demande depuis l'abandon de Piper -
un contenu non pré-généré reste simplement muet). Un sous-dossier par module (pas tout à plat) : plus
de 20 000 fichiers dans un seul dossier posaient un problème de performance
(listage, notamment via SMB) - voir migrate_cache_to_subfolders.py pour la
migration ponctuelle des fichiers déjà générés à plat avant ce changement.

Nécessite VoiceStudio démarré (http://127.0.0.1:3900, voir memory
voicestudio-tts-fiches-wavfiche.md) ET ffmpeg (conversion en mp3 après
génération, comme generate_fiche_audio_voicestudio.py - tts.py du jeu
reconnaît le mp3 en priorité, voir sa fonction _cache_path_existing).

Voix : profil cloné PROFILE_ID (voix masculine, référence Common Voice FR
nettoyée via /clean-audio pour retirer le bruit de fond du micro d'origine),
et non plus un archetype `instruct` — l'archetype resample une voix
différente à chaque appel (même avec un seed fixe), ce qui donnait
l'impression d'un narrateur différent d'un fichier à l'autre. Un profil
cloné fige l'identité vocale sur un extrait de référence fixe.

num_step=32 (relevé de 16) et effect_preset=raw (pas de post-traitement) :
artefacts d'écho/larsen constatés sur le premier batch avec num_step=16 et
le preset par défaut "broadcast".

Usage:
    python3 generate_tts_voicestudio.py [--limit-modules N] [--only-quiz] [--only-flash]
"""
import argparse
import csv
import json
import os
import subprocess
import sys
import time

import requests

GAME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pse2527')
DATA_DIR = os.path.join(GAME_DIR, 'data')
CACHE_DIR = os.path.join(GAME_DIR, 'tts_assets', 'cache')

VOICESTUDIO_URL = "http://127.0.0.1:3900/generate"
PROFILE_ID = "cc1ebb9c"  # NarrateurPSE_H1_clean : voix masculine clonée, référence nettoyée
LANGUAGE = "fr"
NUM_STEP = 32
CROSSFADE_MS = 20
EFFECT_PRESET = "raw"
LETTERS = ('A', 'B', 'C', 'D')


def _sanitize(name):
    return ''.join(c if (c.isalnum() or c in '-_') else '_' for c in name)


def _cache_path(base, suffix, ext):
    # Doit rester identique à tts._cache_path() du jeu : c'est cette
    # convention (sous-dossier par module, mp3 prioritaire sur wav) qui
    # permet au jeu de retrouver l'audio pré-généré ici en cache.
    return os.path.join(CACHE_DIR, _sanitize(base), _sanitize(suffix) + '.' + ext)


def synth(text, base, suffix):
    log_key = '{}/{}'.format(base, suffix)
    mp3_path = _cache_path(base, suffix, 'mp3')
    if os.path.exists(mp3_path) or os.path.exists(_cache_path(base, suffix, 'wav')):
        return 'skip'
    os.makedirs(os.path.dirname(mp3_path), exist_ok=True)
    t0 = time.time()
    try:
        r = requests.post(VOICESTUDIO_URL, data={
            "text": text, "profile_id": PROFILE_ID, "language": LANGUAGE,
            "num_step": NUM_STEP, "crossfade_ms": CROSSFADE_MS,
            "effect_preset": EFFECT_PRESET,
        }, timeout=300)
    except Exception as e:
        print('[ERREUR réseau] {} : {}'.format(log_key, e), flush=True)
        return 'error'
    if r.status_code != 200:
        print('[ERREUR {}] {} : {}'.format(r.status_code, log_key, r.text[:200]), flush=True)
        return 'error'

    tmp_wav = mp3_path + '.tmp.wav'
    with open(tmp_wav, 'wb') as f:
        f.write(r.content)
    tmp_mp3 = mp3_path + '.tmp.mp3'
    try:
        proc = subprocess.run(
            ['ffmpeg', '-y', '-i', tmp_wav, '-codec:a', 'libmp3lame', '-qscale:a', '4', tmp_mp3],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    finally:
        os.remove(tmp_wav)
    if proc.returncode != 0 or not os.path.exists(tmp_mp3):
        print('[ERREUR ffmpeg] {} : conversion mp3 échouée (code {})'.format(log_key, proc.returncode), flush=True)
        return 'error'
    os.replace(tmp_mp3, mp3_path)

    print('[ok] {} ({:.1f}s, {} octets mp3)'.format(log_key, time.time() - t0, os.path.getsize(mp3_path)), flush=True)
    return 'ok'


def load_all_quiz_rows(base):
    path = os.path.join(DATA_DIR, 'quizz', base + '.csv')
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding='utf-8') as f:
        for row_index, row in enumerate(csv.reader(f, delimiter=';')):
            if len(row) < 7:
                continue
            try:
                int(row[5])
            except ValueError:
                continue
            rows.append({'id': row_index, 'question': row[0], 'choix': row[1:5], 'explication': row[6]})
    return rows


def load_all_flash_rows(base):
    path = os.path.join(DATA_DIR, 'flashcard', base + '.csv')
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding='utf-8') as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            rows.append({'recto': row[0], 'verso': row[1]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit-modules', type=int, default=None)
    ap.add_argument('--only-quiz', action='store_true')
    ap.add_argument('--only-flash', action='store_true')
    args = ap.parse_args()

    modules = json.load(open(os.path.join(DATA_DIR, 'modules.json'), encoding='utf-8'))
    bases = [m[:-4] for m in modules]
    if args.limit_modules:
        bases = bases[:args.limit_modules]

    stats = {'ok': 0, 'skip': 0, 'error': 0}
    t_start = time.time()

    for i, base in enumerate(bases):
        print('=== module {}/{} : {} ==='.format(i + 1, len(bases), base), flush=True)
        if not args.only_flash:
            for q in load_all_quiz_rows(base):
                letters_text = ' '.join('Réponse {}. {}'.format(l, c) for l, c in zip(LETTERS, q['choix']))
                ask_text = q['question'] + ' ' + letters_text
                ask_suffix = 'quiz_{}_ask'.format(q['id'])
                stats[synth(ask_text, base, ask_suffix)] += 1

                for outcome, prefix in (('correct', 'Bonne réponse. '), ('incorrect', 'Mauvaise réponse. ')):
                    fb_text = prefix + q['explication']
                    fb_suffix = 'quiz_{}_feedback_{}'.format(q['id'], outcome)
                    stats[synth(fb_text, base, fb_suffix)] += 1

        if not args.only_quiz:
            for idx, card in enumerate(load_all_flash_rows(base)):
                for face in ('recto', 'verso'):
                    suffix = 'flash_{}_{}'.format(idx, face)
                    stats[synth(card[face], base, suffix)] += 1

        elapsed = time.time() - t_start
        print('--- cumul : ok={} skip={} error={} -- {:.0f} min écoulées ---'.format(
            stats['ok'], stats['skip'], stats['error'], elapsed / 60), flush=True)

    print('TERMINÉ.', stats, flush=True)


if __name__ == '__main__':
    main()
