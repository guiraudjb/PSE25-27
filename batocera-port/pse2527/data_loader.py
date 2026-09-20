"""Chargement des données de révision PSE25-27 (modules.json, quizz/, flashcard/)."""
import csv
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')


def base_name(csv_filename):
    """'09-570 PSE-ER F6-7 ToIP et convergence....csv' -> '09-570 PSE-ER F6-7 ToIP et convergence....'"""
    return csv_filename[:-4] if csv_filename.lower().endswith('.csv') else csv_filename


def load_series():
    """Retourne une liste de séries triées : [(code_serie, [modules...]), ...]
    Chaque module est un dict {code, numero, titre, base}.
    """
    with open(os.path.join(DATA_DIR, 'modules.json'), encoding='utf-8') as f:
        entries = json.load(f)

    series = {}
    for entry in entries:
        base = base_name(entry)
        numero, _, titre = base.partition(' ')
        code = numero.split('-')[0]
        titre = titre.strip()
        series.setdefault(code, []).append({
            'code': code,
            'numero': numero,
            'titre': titre,
            'base': base,
        })

    def sort_key(m):
        parts = m['numero'].split('-')
        try:
            return (parts[0], int(parts[1]))
        except (IndexError, ValueError):
            return (parts[0], 0)

    for code in series:
        series[code].sort(key=sort_key)

    return sorted(series.items(), key=lambda kv: kv[0])


def load_quiz(base, max_questions=15):
    """Charge et renvoie une liste de questions mélangées pour le module `base`.
    Chaque question : {question, choix:[4], index_correct(0-3), explication}.
    """
    path = os.path.join(DATA_DIR, 'quizz', base + '.csv')
    questions = []
    if not os.path.exists(path):
        return questions
    with open(path, encoding='utf-8') as f:
        for row_index, row in enumerate(csv.reader(f, delimiter=';')):
            if len(row) < 7:
                continue
            question, c1, c2, c3, c4, idx, expl = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
            try:
                correct = int(idx) - 2  # colonne 2..5 -> index 0..3
            except ValueError:
                continue
            questions.append({
                'id': row_index,  # stable (position dans le CSV, avant mélange) : sert de clé de cache TTS
                'question': question,
                'choix': [c1, c2, c3, c4],
                'correct': correct,
                'explication': expl,
            })
    import random
    random.shuffle(questions)
    return questions[:max_questions]


def load_flashcards(base):
    """Charge les flashcards du module `base` : liste de {recto, verso}."""
    path = os.path.join(DATA_DIR, 'flashcard', base + '.csv')
    cards = []
    if not os.path.exists(path):
        return cards
    with open(path, encoding='utf-8') as f:
        for row in csv.reader(f):
            if len(row) < 2:
                continue
            cards.append({'recto': row[0], 'verso': row[1]})
    return cards


def chanson_path(base):
    """Chemin du fichier chanson (mp3) du module, ou None si absent."""
    path = os.path.join(DATA_DIR, 'chanson', base + '.mp3')
    return path if os.path.exists(path) else None


def podcast_path(base):
    """Chemin du fichier podcast (mp3, converti depuis le .m4a NotebookLM
    source - SDL_mixer sur Batocera ne décode pas l'AAC/m4a), ou None si absent."""
    path = os.path.join(DATA_DIR, 'podcast', base + '.mp3')
    return path if os.path.exists(path) else None


def infographie_path(base):
    """Chemin du fichier infographie (png) du module, ou None si absent."""
    path = os.path.join(DATA_DIR, 'infographie', base + '.png')
    return path if os.path.exists(path) else None


def fiche_path(base):
    """Chemin de la fiche de révision (txt) du module, ou None si absente."""
    path = os.path.join(DATA_DIR, 'fiche', base + '.txt')
    return path if os.path.exists(path) else None


def load_fiche(base):
    """Charge le texte complet de la fiche de révision du module, ou None si absente."""
    path = fiche_path(base)
    if path is None:
        return None
    with open(path, encoding='utf-8') as f:
        return f.read()


def fiche_audio_path(base):
    """Chemin de la narration audio (mp3) de la fiche de révision du module,
    ou None si absente. Fichier long (plusieurs dizaines de minutes possible)
    pré-généré à l'avance et streamé via pygame.mixer.music - jamais généré à
    la volée par Piper comme le quiz/flashcard (bien trop long pour ça)."""
    path = os.path.join(DATA_DIR, 'fiche_audio', base + '.mp3')
    return path if os.path.exists(path) else None
