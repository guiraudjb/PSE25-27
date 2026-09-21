"""Lecture de la voix off pré-générée (VoiceStudio, en lot hors ligne) à
partir du cache disque.

Toute la synthèse vocale (quiz, flashcards, fiches) est désormais générée à
l'avance par le pipeline `generate_tts_voicestudio.py` /
`generate_fiche_audio_voicestudio.py` et déployée avec le jeu - il n'y a plus
de synthèse à la demande sur la Batocera (Piper, abandonné : bien trop lent
sur cette machine, ~1.5x le temps réel, et rendu redondant par le
pré-calcul en lot). Ce module se limite donc à lire un fichier déjà en
cache ; s'il n'existe pas pour un contenu donné, aucun son n'est joué.

Cache organisé en UN SOUS-DOSSIER PAR MODULE (cache/<base>/<suffix>.ext) et non
plus à plat (~20 000 fichiers dans un seul dossier ralentissaient le listage,
en particulier via SMB) - voir migrate_cache_to_subfolders.py pour la
migration ponctuelle des fichiers déjà générés à plat avant ce changement.
"""
import os
import pygame

GAME_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(GAME_DIR, 'tts_assets')
CACHE_DIR = os.path.join(ASSETS_DIR, 'cache')

STATUS_IDLE = 'idle'
STATUS_PLAYING = 'playing'
STATUS_ERROR = 'error'
STATUS_UNAVAILABLE = 'indisponible'


def _sanitize(name):
    return ''.join(c if (c.isalnum() or c in '-_') else '_' for c in name)


def _cache_path(base, suffix, ext='wav'):
    return os.path.join(CACHE_DIR, _sanitize(base), _sanitize(suffix) + '.' + ext)


def _cache_path_existing(base, suffix):
    """Chemin du cache déjà présent pour ce module/contenu (mp3, pré-généré
    en lot par VoiceStudio), ou None si rien n'est en cache."""
    mp3 = _cache_path(base, suffix, 'mp3')
    if os.path.exists(mp3):
        return mp3
    wav = _cache_path(base, suffix, 'wav')
    if os.path.exists(wav):
        return wav
    return None


class TTSManager:
    def __init__(self):
        self.enabled = True
        self.current_key = None   # (base, suffix) du dernier contenu demandé par l'utilisateur
        self.channel = None
        self.status = STATUS_IDLE

    def cached_duration(self, base, suffix):
        """Durée en secondes du fichier déjà en cache, ou None s'il n'existe
        pas encore (rien à ajuster dans ce cas : sans fichier en cache il n'y
        a pas de lecture automatique - voir play_if_cached - donc pas de
        minuteur à étendre). Passe par pygame.mixer.Sound plutôt que le
        module `wave` : ce dernier ne lit que du PCM WAV, alors que le cache
        pré-généré est en mp3."""
        path = _cache_path_existing(base, suffix)
        if path is None:
            return None
        try:
            return pygame.mixer.Sound(path).get_length()
        except pygame.error:
            return None

    def play_if_cached(self, text, base, suffix):
        """Lit immédiatement l'audio pré-généré s'il existe pour ce contenu,
        sinon ne fait rien. Utilisée pour la lecture automatique à
        l'affichage d'une question/carte."""
        if not self.enabled or not text:
            return
        path = _cache_path_existing(base, suffix)
        if path is not None:
            self.current_key = (base, suffix)
            self._play(path)

    def request(self, text, base, suffix):
        """Demande la lecture de `text` (touche Écouter), identifié par
        (`base`, `suffix`). Lit l'audio pré-généré s'il existe ; sinon ne
        fait rien (plus de génération à la demande depuis l'abandon de
        Piper - tout est pré-calculé par le pipeline VoiceStudio)."""
        if not self.enabled or not text:
            return
        self.current_key = (base, suffix)
        path = _cache_path_existing(base, suffix)
        if path is not None:
            self._play(path)

    def _play(self, path):
        try:
            sound = pygame.mixer.Sound(path)
            self.channel = sound.play()
            self.status = STATUS_PLAYING
        except Exception:
            self.status = STATUS_ERROR

    def stop(self):
        if self.channel:
            try:
                self.channel.stop()
            except Exception:
                pass
        self.status = STATUS_IDLE if self.enabled else STATUS_UNAVAILABLE
        self.current_key = None

    def is_busy(self):
        """Lecture en cours, pour l'indicateur écran."""
        if self.channel is not None:
            try:
                return bool(self.channel.get_busy())
            except Exception:
                return False
        return False
