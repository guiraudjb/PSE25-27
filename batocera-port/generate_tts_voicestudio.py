#!/usr/bin/env python3
"""Pré-génère les fichiers audio TTS (quiz + flashcards) via VoiceStudio local,
directement dans pse2527/tts_assets/cache/, avec la MÊME convention de nom de
fichier que tts.py : le jeu les trouve donc automatiquement en cache au
lancement, Piper ne servant plus que de secours pour ce qui n'est pas
(encore) pré-généré.

Nécessite VoiceStudio démarré (http://127.0.0.1:3900, voir memory
voicestudio-tts-fiches-wavfiche.md).

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


def _cache_path(cache_key):
    # Doit rester identique à tts._cache_path() du jeu : c'est cette convention
    # de nommage qui permet au jeu de retrouver l'audio pré-généré ici en cache.
    safe = ''.join(c if (c.isalnum() or c in '-_') else '_' for c in cache_key)
    return os.path.join(CACHE_DIR, safe + '.wav')


def synth(text, cache_key):
    path = _cache_path(cache_key)
    if os.path.exists(path):
        return 'skip'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    t0 = time.time()
    try:
        r = requests.post(VOICESTUDIO_URL, data={
            "text": text, "profile_id": PROFILE_ID, "language": LANGUAGE,
            "num_step": NUM_STEP, "crossfade_ms": CROSSFADE_MS,
            "effect_preset": EFFECT_PRESET,
        }, timeout=300)
    except Exception as e:
        print('[ERREUR réseau] {} : {}'.format(cache_key, e), flush=True)
        return 'error'
    if r.status_code != 200:
        print('[ERREUR {}] {} : {}'.format(r.status_code, cache_key, r.text[:200]), flush=True)
        return 'error'
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(r.content)
    os.replace(tmp, path)
    print('[ok] {} ({:.1f}s, {} octets)'.format(cache_key, time.time() - t0, len(r.content)), flush=True)
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
                ask_key = '{}_quiz_{}_ask'.format(base, q['id'])
                stats[synth(ask_text, ask_key)] += 1

                for outcome, prefix in (('correct', 'Bonne réponse. '), ('incorrect', 'Mauvaise réponse. ')):
                    fb_text = prefix + q['explication']
                    fb_key = '{}_quiz_{}_feedback_{}'.format(base, q['id'], outcome)
                    stats[synth(fb_text, fb_key)] += 1

        if not args.only_quiz:
            for idx, card in enumerate(load_all_flash_rows(base)):
                for face in ('recto', 'verso'):
                    key = '{}_flash_{}_{}'.format(base, idx, face)
                    stats[synth(card[face], key)] += 1

        elapsed = time.time() - t_start
        print('--- cumul : ok={} skip={} error={} -- {:.0f} min écoulées ---'.format(
            stats['ok'], stats['skip'], stats['error'], elapsed / 60), flush=True)

    print('TERMINÉ.', stats, flush=True)


if __name__ == '__main__':
    main()
