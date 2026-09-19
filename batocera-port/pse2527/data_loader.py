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
        for row in csv.reader(f, delimiter=';'):
            if len(row) < 7:
                continue
            question, c1, c2, c3, c4, idx, expl = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
            try:
                correct = int(idx) - 2  # colonne 2..5 -> index 0..3
            except ValueError:
                continue
            questions.append({
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
