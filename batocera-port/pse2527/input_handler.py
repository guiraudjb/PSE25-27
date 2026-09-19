"""Gestion manette/clavier via l'API sémantique SDL_GameController de pygame
(pygame._sdl2.controller), qui s'appuie sur la base de mappings de Batocera :
les boutons A/B/X/Y, Select (Back), Start et le D-pad sont identifiés par leur
FONCTION plutôt que par un numéro d'index brut, ce qui évite les incohérences
entre manettes (et le bug de "double mouvement" observé avec la lecture brute
de pygame.joystick, quand une même pression physique du D-pad était rapportée
par deux canaux différents en même temps).

Repli : si une manette n'est pas reconnue par la base SDL (cas rare), on
retombe sur une heuristique d'index bruts (mêmes valeurs que le jeu Retrotrivia
déjà validé sur ce salon Batocera).
"""
import pygame

try:
    import pygame._sdl2.controller as sdl2ctrl
    sdl2ctrl.init()
    HAVE_SDL2_CONTROLLER = True
except Exception:
    HAVE_SDL2_CONTROLLER = False

REPEAT_DELAY_MS = 350   # délai avant répétition d'une direction maintenue
REPEAT_RATE_MS = 120    # intervalle de répétition
AXIS_DEADZONE = 0.5

SEMANTIC_BUTTON_IDS = {}
if HAVE_SDL2_CONTROLLER:
    SEMANTIC_BUTTON_IDS = {
        'a': pygame.CONTROLLER_BUTTON_A,
        'b': pygame.CONTROLLER_BUTTON_B,
        'x': pygame.CONTROLLER_BUTTON_X,
        'y': pygame.CONTROLLER_BUTTON_Y,
        'back': pygame.CONTROLLER_BUTTON_BACK,     # Select
        'start': pygame.CONTROLLER_BUTTON_START,
        'dpad_up': pygame.CONTROLLER_BUTTON_DPAD_UP,
        'dpad_down': pygame.CONTROLLER_BUTTON_DPAD_DOWN,
        'dpad_left': pygame.CONTROLLER_BUTTON_DPAD_LEFT,
        'dpad_right': pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
        'leftshoulder': pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
        'rightshoulder': pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
    }

# Repli : index bruts observés sur ce salon Batocera pour une manette non
# reconnue par la base SDL (cf. Retrotrivia).
LEGACY_BUTTON_INDEXES = {
    'a': (0,), 'b': (1,), 'x': (2,), 'y': (3,),
    'dpad_up': (8, 13), 'dpad_down': (9, 14),
    'dpad_left': (10, 15), 'dpad_right': (11, 16),
    'back': (6,), 'start': (7,),
    'leftshoulder': (4,), 'rightshoulder': (5,),
}


class Pad:
    """Une manette, avec mapping sémantique fiable quand SDL la reconnaît."""

    def __init__(self, index):
        self.index = index
        self.controller = None
        self.joystick = None
        if HAVE_SDL2_CONTROLLER and sdl2ctrl.is_controller(index):
            self.controller = sdl2ctrl.Controller(index)
        else:
            self.joystick = pygame.joystick.Joystick(index)
            self.joystick.init()

    def button(self, name):
        if self.controller is not None:
            try:
                return bool(self.controller.get_button(SEMANTIC_BUTTON_IDS[name]))
            except Exception:
                return False
        if self.joystick is not None:
            try:
                n = self.joystick.get_numbuttons()
                return any(idx < n and self.joystick.get_button(idx)
                           for idx in LEGACY_BUTTON_INDEXES.get(name, ()))
            except Exception:
                return False
        return False

    def stick_direction(self):
        """Direction du stick analogique gauche (None si dans la zone morte)."""
        try:
            if self.controller is not None:
                x = self.controller.get_axis(pygame.CONTROLLER_AXIS_LEFTX) / 32768.0
                y = self.controller.get_axis(pygame.CONTROLLER_AXIS_LEFTY) / 32768.0
            elif self.joystick is not None:
                x = self.joystick.get_axis(0)
                y = self.joystick.get_axis(1)
            else:
                return None
        except Exception:
            return None
        if y <= -AXIS_DEADZONE:
            return 'up'
        if y >= AXIS_DEADZONE:
            return 'down'
        if x <= -AXIS_DEADZONE:
            return 'left'
        if x >= AXIS_DEADZONE:
            return 'right'
        return None

    def direction(self):
        """Une seule direction par manette et par frame (D-pad, puis Select/Start
        pour le haut/bas, puis stick analogique)."""
        if self.button('dpad_up'):
            return 'up'
        if self.button('dpad_down'):
            return 'down'
        if self.button('dpad_left'):
            return 'left'
        if self.button('dpad_right'):
            return 'right'
        if self.button('back'):     # Select = haut
            return 'up'
        if self.button('start'):    # Start = bas
            return 'down'
        return self.stick_direction()


def init_pads(max_pads=4):
    """Énumère les manettes en les dédoublonnant par GUID : certaines manettes
    (notamment des pads Xbox sans fil) apparaissent sous DEUX index/périphériques
    différents pour un seul objet physique, ce qui, sans dédoublonnage, peut faire
    lire un bouton comme "appuyé" sur le second index fantôme alors que personne
    n'y touche (observé : sortie immédiate et silencieuse du jeu au lancement,
    provoquée par une fausse pression sur B)."""
    pygame.joystick.init()
    count = pygame.joystick.get_count()
    chosen = {}  # guid -> (index, reconnu_par_sdl)
    for i in range(count):
        try:
            j = pygame.joystick.Joystick(i)
            j.init()
            guid = j.get_guid()
        except Exception:
            guid = 'inconnu-{}'.format(i)
        recognized = HAVE_SDL2_CONTROLLER and sdl2ctrl.is_controller(i)
        if guid in chosen:
            prev_index, prev_recognized = chosen[guid]
            if recognized and not prev_recognized:
                chosen[guid] = (i, recognized)
            continue
        chosen[guid] = (i, recognized)
    indexes = [idx for idx, _ in chosen.values()][:max_pads]
    return [Pad(i) for i in indexes]


def current_direction(pads):
    for pad in pads:
        direction = pad.direction()
        if direction:
            return direction
    return None


FACE_BUTTON_NAMES = ('a', 'b', 'x', 'y')


def pressed_face_button(pads):
    """Renvoie 'face_a'|'face_b'|'face_x'|'face_y' si l'un de ces boutons vient
    d'être identifié comme actif sur une manette (utilisé en secours ; la
    détection principale se fait par évènement JOYBUTTONDOWN/CONTROLLERBUTTONDOWN)."""
    for pad in pads:
        for name in FACE_BUTTON_NAMES:
            if pad.button(name):
                return 'face_' + name
    return None


def translate_event(event, pads):
    """Renvoie une action logique pour un évènement ponctuel (pas les directions,
    gérées par sondage continu via current_direction/RepeatState)."""
    if event.type == pygame.QUIT:
        return 'quit'

    if event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            return 'action'
        if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            return 'back'
        if event.key == pygame.K_1:
            return 'face_a'
        if event.key == pygame.K_2:
            return 'face_b'
        if event.key == pygame.K_3:
            return 'face_x'
        if event.key == pygame.K_4:
            return 'face_y'
        return None

    if event.type == pygame.CONTROLLERBUTTONDOWN:
        return _button_id_to_action(event.button)

    if event.type == pygame.JOYBUTTONDOWN:
        # Repli uniquement pour les manettes NON reconnues par SDL (pad.controller
        # est alors None pour cet index) : sinon l'évènement CONTROLLERBUTTONDOWN
        # équivalent est déjà émis par SDL et on éviterait un double déclenchement.
        for pad in pads:
            if pad.joystick is not None and pad.controller is None:
                for name, idxs in LEGACY_BUTTON_INDEXES.items():
                    if event.button in idxs:
                        if name in ('dpad_up', 'dpad_down', 'dpad_left', 'dpad_right'):
                            return None  # géré par le sondage continu
                        return _semantic_name_to_action(name)
        return None

    return None


def _button_id_to_action(button_id):
    for name, bid in SEMANTIC_BUTTON_IDS.items():
        if bid == button_id:
            if name in ('dpad_up', 'dpad_down', 'dpad_left', 'dpad_right', 'back', 'start'):
                return None  # directions : gérées par le sondage continu (current_direction)
            return _semantic_name_to_action(name)
    return None


def _semantic_name_to_action(name):
    if name in ('a', 'b', 'x', 'y'):
        return 'face_' + name
    if name == 'leftshoulder':
        return 'shoulder_l'
    if name == 'rightshoulder':
        return 'shoulder_r'
    return None


class RepeatState:
    """Gère la répétition d'une direction maintenue (D-pad / Select-Start / stick)."""

    def __init__(self):
        self.held = None
        self.next_time = 0

    def poll(self, pads):
        """À appeler une fois par frame : renvoie au plus une direction."""
        direction = current_direction(pads)
        if not direction:
            self.held = None
            return None
        now = pygame.time.get_ticks()
        if self.held != direction:
            self.held = direction
            self.next_time = now + REPEAT_DELAY_MS
            return direction
        if now >= self.next_time:
            self.next_time = now + REPEAT_RATE_MS
            return direction
        return None
