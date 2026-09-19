"""Gestion manette/clavier en réutilisant le remapping déjà configuré et
validé par l'utilisateur dans EmulationStation (Batocera), plutôt que de
deviner des numéros de boutons bruts : EmulationStation enregistre, pour
chaque manette (identifiée par son GUID), le numéro de bouton/axe/hat exact
correspondant à chaque fonction logique (a, b, x, y, start, select, pageup,
pagedown, up/down/left/right) dans
/userdata/system/configs/emulationstation/es_input.cfg.

C'est la source la plus fiable possible : elle a été testée par l'utilisateur
lui-même dans le menu de configuration manette d'EmulationStation. Un contrôle
non reconnu par la base de mappings SDL de pygame (`pygame._sdl2.controller`,
peu fiable pour les manettes génériques/clonées) tombe en repli sur cette
configuration ES, puis, en dernier recours, sur une heuristique générique.
"""
import os
import pygame
import xml.etree.ElementTree as ET

try:
    import pygame._sdl2.controller as sdl2ctrl
    sdl2ctrl.init()
    HAVE_SDL2_CONTROLLER = True
except Exception:
    HAVE_SDL2_CONTROLLER = False

REPEAT_DELAY_MS = 350   # délai avant répétition d'une direction maintenue
REPEAT_RATE_MS = 120    # intervalle de répétition
AXIS_DEADZONE = 0.5

ES_INPUT_CFG_PATHS = (
    '/userdata/system/configs/emulationstation/es_input.cfg',
)

# Correspondance entre nos noms logiques et ceux utilisés par EmulationStation.
OUR_TO_ES_NAME = {
    'a': 'a', 'b': 'b', 'x': 'x', 'y': 'y',
    'start': 'start', 'back': 'select',
    'leftshoulder': 'pageup', 'rightshoulder': 'pagedown',
}
ES_TO_OUR_NAME = {es: ours for ours, es in OUR_TO_ES_NAME.items()}

# Correction pour les boutons de face (a/b/x/y) uniquement : es_input.cfg fait
# foi pour select/start/pageup/pagedown/hat (vérifié identique ci-dessous),
# mais l'assignation a/b/x/y qu'EmulationStation y stocke ne correspond PAS
# aux lettres A/B/C/D imprimées sur cette manette (ES ne teste que
# confirmer/annuler au moment de la configuration, sans égard aux lettres
# physiques). Mesuré bouton par bouton avec l'utilisateur via un outil pygame
# dédié (mapping_test.py) le 19/09/2026 : A=3, B=1, C=0, D=2.
VERIFIED_FACE_BUTTONS = {
    '030000005e0400008e02000010010000': {'a': 3, 'b': 1, 'x': 0, 'y': 2},
}

SEMANTIC_BUTTON_IDS = {}
if HAVE_SDL2_CONTROLLER:
    SEMANTIC_BUTTON_IDS = {
        'a': pygame.CONTROLLER_BUTTON_A,
        'b': pygame.CONTROLLER_BUTTON_B,
        'x': pygame.CONTROLLER_BUTTON_X,
        'y': pygame.CONTROLLER_BUTTON_Y,
        'back': pygame.CONTROLLER_BUTTON_BACK,     # Select
        'start': pygame.CONTROLLER_BUTTON_START,
        'leftshoulder': pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
        'rightshoulder': pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
    }

# Dernier recours si ni es_input.cfg ni la base SDL ne reconnaissent la
# manette (ex. tests hors Batocera). Purement indicatif, à ne pas considérer
# fiable sur une manette réelle non testée.
LEGACY_BUTTON_INDEXES = {
    'a': (0,), 'b': (1,), 'x': (2,), 'y': (3,),
    'back': (6,), 'start': (7,),
    'leftshoulder': (4,), 'rightshoulder': (5,),
}


def _load_es_button_mappings():
    """Lit es_input.cfg : {guid: {nom_es: id_bouton}} pour chaque manette
    qu'EmulationStation connaît déjà (boutons uniquement ; le D-pad est un hat
    standard SDL et n'a pas besoin de cette config, voir Pad.direction)."""
    mappings = {}
    for path in ES_INPUT_CFG_PATHS:
        if not os.path.exists(path):
            continue
        try:
            tree = ET.parse(path)
        except Exception:
            continue
        for cfg in tree.getroot().findall('inputConfig'):
            guid = cfg.get('deviceGUID')
            if not guid:
                continue
            buttons = {}
            for inp in cfg.findall('input'):
                if inp.get('type') == 'button':
                    try:
                        buttons[inp.get('name')] = int(inp.get('id'))
                    except (TypeError, ValueError):
                        pass
            if buttons:
                mappings.setdefault(guid, buttons)
    return mappings


ES_BUTTON_MAPPINGS = _load_es_button_mappings()


class Pad:
    """Une manette physique. Priorité de la source de mapping des boutons :
    1) es_input.cfg (config EmulationStation, déjà validée par l'utilisateur)
    2) base SDL_GameController de pygame (si la manette y est reconnue)
    3) repli générique (imprécis, dernier recours)
    Le D-pad et le stick analogique sont lus directement sur le joystick brut
    (hat standard SDL / axes 0-1), indépendamment de la source ci-dessus."""

    def __init__(self, index):
        self.index = index
        self.joystick = pygame.joystick.Joystick(index)
        self.joystick.init()
        try:
            self.guid = self.joystick.get_guid()
        except Exception:
            self.guid = None

        es_buttons = ES_BUTTON_MAPPINGS.get(self.guid)
        verified_face = VERIFIED_FACE_BUTTONS.get(self.guid)
        if verified_face:
            es_buttons = dict(es_buttons) if es_buttons else {}
            es_buttons.update(verified_face)
        self.es_buttons = es_buttons or None

        self.controller = None
        if self.es_buttons is None and HAVE_SDL2_CONTROLLER and sdl2ctrl.is_controller(index):
            self.controller = sdl2ctrl.Controller(index)

        if verified_face:
            source = 'vérifié manuellement + es_input.cfg'
        elif self.es_buttons is not None:
            source = 'es_input.cfg'
        elif self.controller is not None:
            source = 'sdl_gamecontroller'
        else:
            source = 'repli générique (non testé)'
        try:
            name = self.joystick.get_name()
        except Exception:
            name = '?'
        print('[pse2527] Pad {} "{}" (guid={}) -> mapping = {}'.format(
            index, name, self.guid, source), flush=True)

    def button(self, name):
        if self.es_buttons is not None:
            idx = self.es_buttons.get(OUR_TO_ES_NAME.get(name, name))
            if idx is None:
                return False
            try:
                return idx < self.joystick.get_numbuttons() and bool(self.joystick.get_button(idx))
            except Exception:
                return False
        if self.controller is not None:
            try:
                return bool(self.controller.get_button(SEMANTIC_BUTTON_IDS[name]))
            except Exception:
                return False
        try:
            n = self.joystick.get_numbuttons()
            return any(idx < n and self.joystick.get_button(idx)
                       for idx in LEGACY_BUTTON_INDEXES.get(name, ()))
        except Exception:
            return False

    def button_name_for_index(self, button_index):
        """Retrouve le nom logique (a/b/x/y/start/back/leftshoulder/...)
        correspondant à un numéro de bouton brut reçu par évènement."""
        if self.es_buttons is not None:
            # Un même index peut porter plusieurs noms ES pour un même bouton
            # physique (ex. id=6 est à la fois "select" ET "hotkey" sur cette
            # manette) : on ne s'arrête que sur un nom qu'on sait traduire,
            # sinon on continue de chercher plutôt que de renvoyer None trop tôt.
            for es_name, idx in self.es_buttons.items():
                if idx == button_index and es_name in ES_TO_OUR_NAME:
                    return ES_TO_OUR_NAME[es_name]
            return None
        if self.controller is not None:
            for name, bid in SEMANTIC_BUTTON_IDS.items():
                if bid == button_index:
                    return name
            return None
        for name, idxs in LEGACY_BUTTON_INDEXES.items():
            if button_index in idxs:
                return name
        return None

    def stick_direction(self):
        """Stick analogique gauche = axes 0/1 (lecture directe du joystick brut)."""
        try:
            x = self.joystick.get_axis(0)
            y = self.joystick.get_axis(1)
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
        """D-pad (hat standard SDL id=0), puis stick analogique en repli.
        Select/Start ne sont PAS des directions : ce sont des boutons de
        validation/retour (voir _semantic_name_to_action)."""
        try:
            hat = self.joystick.get_hat(0)
        except Exception:
            hat = (0, 0)
        if hat == (0, 1):
            return 'up'
        if hat == (0, -1):
            return 'down'
        if hat == (-1, 0):
            return 'left'
        if hat == (1, 0):
            return 'right'
        return self.stick_direction()


def init_pads(max_pads=4):
    """Énumère les manettes en les dédoublonnant par GUID : certaines manettes
    (notamment des pads Xbox sans fil) apparaissent sous DEUX index/périphériques
    différents pour un seul objet physique. Sans dédoublonnage, le second index
    fantôme peut faire lire un bouton comme "appuyé" alors que personne n'y
    touche (observé : fermeture immédiate et silencieuse du jeu au lancement)."""
    pygame.joystick.init()
    count = pygame.joystick.get_count()
    print('[pse2527] init_pads: {} périphérique(s) joystick, {} mapping(s) ES connu(s)'.format(
        count, len(ES_BUTTON_MAPPINGS)), flush=True)
    chosen = {}  # guid -> (index, priorité) ; priorité : 2=es_input.cfg, 1=sdl, 0=inconnu
    for i in range(count):
        try:
            j = pygame.joystick.Joystick(i)
            j.init()
            guid = j.get_guid()
        except Exception:
            guid = 'inconnu-{}'.format(i)
        if guid in ES_BUTTON_MAPPINGS or guid in VERIFIED_FACE_BUTTONS:
            priority = 2
        elif HAVE_SDL2_CONTROLLER and sdl2ctrl.is_controller(i):
            priority = 1
        else:
            priority = 0
        if guid not in chosen or priority > chosen[guid][1]:
            chosen[guid] = (i, priority)
    indexes = [idx for idx, _ in chosen.values()][:max_pads]
    print('[pse2527] init_pads: index retenus après dédoublonnage = {}'.format(indexes), flush=True)
    return [Pad(i) for i in indexes]


def current_direction(pads):
    for pad in pads:
        direction = pad.direction()
        if direction:
            return direction
    return None


def translate_event(event, pads):
    """Renvoie une action logique pour un évènement ponctuel (pas les
    directions, gérées par sondage continu via current_direction/RepeatState)."""
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

    # Sur cette manette (non reconnue par la base SDL), seuls les évènements
    # joystick "bruts" sont émis, pas les CONTROLLERBUTTONDOWN sémantiques ;
    # on gère donc les deux types d'évènements par le même chemin, en
    # retrouvant le nom logique via la manette concernée.
    if event.type in (pygame.JOYBUTTONDOWN, pygame.CONTROLLERBUTTONDOWN):
        for pad in pads:
            name = pad.button_name_for_index(event.button)
            if name:
                return _semantic_name_to_action(name)
        return None

    return None


def _semantic_name_to_action(name):
    if name in ('a', 'b', 'x', 'y'):
        return 'face_' + name
    if name == 'leftshoulder':
        return 'shoulder_l'
    if name == 'rightshoulder':
        return 'shoulder_r'
    if name == 'start':   # Start = validation, comme le bouton A
        return 'action'
    if name == 'back':    # Select = retour arrière, comme le bouton B
        return 'back'
    return None


class RepeatState:
    """Gère la répétition d'une direction maintenue (D-pad / stick)."""

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
