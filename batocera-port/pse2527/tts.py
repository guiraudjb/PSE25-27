"""Synthèse vocale locale (Piper, voix française fr_FR-siwis-medium) avec
cache disque et génération en tâche de fond.

Mesuré sur la machine Batocera cible : facteur temps-réel ~1.5 (plus lent
que le temps réel, ~12s pour une phrase de 20 mots), très différent des ~20x
plus rapide que le temps réel observés sur une machine de développement plus
puissante. La synthèse à la demande, bloquante, gèlerait donc le jeu de façon
inacceptable. Solution : un fichier `.wav` par contenu (carte, question,
explication) est généré UNE SEULE FOIS dans un thread d'arrière-plan et mis en
cache sur le disque ; les lectures suivantes du même contenu sont instantanées.
"""
import os
import subprocess
import threading
import wave
import pygame

GAME_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(GAME_DIR, 'tts_assets')
PIPER_DIR = os.path.join(ASSETS_DIR, 'piper_bin')
PIPER_BIN = os.path.join(PIPER_DIR, 'piper')
VOICE_MODEL = os.path.join(ASSETS_DIR, 'voices', 'fr_FR-siwis-medium.onnx')
CACHE_DIR = os.path.join(ASSETS_DIR, 'cache')

AVAILABLE = os.path.isfile(PIPER_BIN) and os.path.isfile(VOICE_MODEL)

STATUS_IDLE = 'idle'
STATUS_GENERATING = 'generating'
STATUS_PLAYING = 'playing'
STATUS_ERROR = 'error'
STATUS_UNAVAILABLE = 'indisponible'


def _cache_path(cache_key):
    safe = ''.join(c if (c.isalnum() or c in '-_') else '_' for c in cache_key)
    return os.path.join(CACHE_DIR, safe + '.wav')


class TTSManager:
    def __init__(self):
        self.enabled = AVAILABLE
        if self.enabled:
            os.makedirs(CACHE_DIR, exist_ok=True)
        self.pending = set()      # cache_keys dont la génération est en cours
        self.current_key = None   # dernier contenu demandé par l'utilisateur
        self.channel = None
        self.status = STATUS_IDLE if self.enabled else STATUS_UNAVAILABLE

    def cached_duration(self, cache_key):
        """Durée en secondes du fichier déjà en cache pour `cache_key`, ou
        None s'il n'existe pas encore (rien à ajuster dans ce cas : sans
        fichier en cache il n'y a pas de lecture automatique - voir
        play_if_cached - donc pas de minuteur à étendre)."""
        path = _cache_path(cache_key)
        if not os.path.exists(path):
            return None
        try:
            with wave.open(path, 'rb') as w:
                return w.getnframes() / float(w.getframerate())
        except (wave.Error, EOFError, OSError):
            return None

    def play_if_cached(self, text, cache_key):
        """Comme request(), mais sans jamais déclencher de génération à la
        volée : lit immédiatement si l'audio est déjà pré-généré, sinon ne
        fait rien. Utilisée pour la lecture automatique à l'affichage d'une
        question/carte - l'utilisateur garde request() (touche Écouter) pour
        forcer la génération Piper à la demande si rien n'est en cache."""
        if not self.enabled or not text:
            return
        path = _cache_path(cache_key)
        if os.path.exists(path):
            self.current_key = cache_key
            self._play(path)

    def request(self, text, cache_key):
        """Demande la lecture de `text`, identifié de façon stable par
        `cache_key` (même contenu -> même clé, quel que soit l'ordre de
        tirage des questions). Lecture immédiate si déjà en cache, sinon
        génération en tâche de fond puis lecture automatique à la fin, sauf
        si l'utilisateur a changé de carte/question entre-temps."""
        if not self.enabled or not text:
            return
        self.current_key = cache_key
        path = _cache_path(cache_key)
        if os.path.exists(path):
            self._play(path)
            return
        self.status = STATUS_GENERATING
        if cache_key in self.pending:
            return
        self.pending.add(cache_key)
        threading.Thread(target=self._generate, args=(text, cache_key, path), daemon=True).start()

    def _generate(self, text, cache_key, path):
        tmp_path = path + '.tmp-{}'.format(os.getpid())
        try:
            env = dict(os.environ)
            env['LD_LIBRARY_PATH'] = PIPER_DIR + os.pathsep + env.get('LD_LIBRARY_PATH', '')
            proc = subprocess.run(
                [PIPER_BIN, '--model', VOICE_MODEL, '--output_file', tmp_path],
                input=text.encode('utf-8'), env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
            if proc.returncode == 0 and os.path.exists(tmp_path):
                os.replace(tmp_path, path)
                if self.current_key == cache_key:
                    self._play(path)
            elif self.current_key == cache_key:
                self.status = STATUS_ERROR
        except Exception:
            if self.current_key == cache_key:
                self.status = STATUS_ERROR
        finally:
            self.pending.discard(cache_key)
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

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
        """Génération en cours ou lecture en cours, pour l'indicateur écran."""
        if self.status == STATUS_GENERATING:
            return True
        if self.channel is not None:
            try:
                return bool(self.channel.get_busy())
            except Exception:
                return False
        return False
