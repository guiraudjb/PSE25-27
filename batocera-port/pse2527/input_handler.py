"""Traduction clavier/manette en actions logiques : up, down, left, right, action, back.

Le mapping manette reprend celui, éprouvé sur Batocera, du jeu pygame Retrotrivia
(hat/axes standards + numéros de boutons bruts observés sur les manettes de ce salon),
avec en plus un bouton "back" (B) distinct de "action" (A).
"""
import pygame

REPEAT_DELAY_MS = 350   # délai avant répétition d'une direction maintenue
REPEAT_RATE_MS = 120    # intervalle de répétition


def axis_direction(joypad):
    try:
        if joypad.get_axis(1) <= -0.6:
            return 'up'
        if joypad.get_axis(1) >= 0.6:
            return 'down'
        if joypad.get_axis(0) <= -0.6:
            return 'left'
        if joypad.get_axis(0) >= 0.6:
            return 'right'
    except Exception:
        pass
    return None


def hat_direction(joypad):
    try:
        hat = joypad.get_hat(0)
        if hat == (0, 1):
            return 'up'
        if hat == (0, -1):
            return 'down'
        if hat == (-1, 0):
            return 'left'
        if hat == (1, 0):
            return 'right'
    except Exception:
        pass
    return None


def button_action(joypad, button):
    # Boutons standards SDL_GameController : 0=A, 1=B
    if button == 0:
        return 'action'
    if button == 1:
        return 'back'
    # Repli sur les index bruts déjà observés sur ce salon Batocera (cf. Retrotrivia)
    if button in (2, 3):
        return 'action'
    if button in (8, 13):
        return 'up'
    if button in (9, 14):
        return 'down'
    if button in (10, 15):
        return 'left'
    if button in (11, 16):
        return 'right'
    return None


def translate_event(event):
    """Renvoie ('up'|'down'|'left'|'right'|'action'|'back'|'quit'|None, is_repeatable)."""
    if event.type == pygame.QUIT:
        return 'quit', False

    if event.type == pygame.KEYDOWN:
        if event.key in (pygame.K_UP, pygame.K_w):
            return 'up', True
        if event.key in (pygame.K_DOWN, pygame.K_s):
            return 'down', True
        if event.key in (pygame.K_LEFT, pygame.K_a):
            return 'left', True
        if event.key in (pygame.K_RIGHT, pygame.K_d):
            return 'right', True
        if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_KP_ENTER):
            return 'action', False
        if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            return 'back', False
        return None, False

    if event.type == pygame.JOYBUTTONDOWN:
        joypad = pygame.joystick.Joystick(event.joy) if hasattr(event, 'joy') else None
        action = button_action(joypad, event.button)
        repeatable = action in ('up', 'down', 'left', 'right')
        return action, repeatable

    if event.type == pygame.JOYHATMOTION:
        joypad = pygame.joystick.Joystick(event.joy) if hasattr(event, 'joy') else None
        direction = hat_direction(joypad) if joypad else None
        return direction, True

    return None, False


class RepeatState:
    """Gère la répétition d'une direction maintenue (D-pad / stick analogique)."""

    def __init__(self):
        self.held = None
        self.next_time = 0

    def start(self, direction):
        self.held = direction
        self.next_time = pygame.time.get_ticks() + REPEAT_DELAY_MS

    def stop(self):
        self.held = None

    def poll(self, joysticks):
        """À appeler chaque frame : renvoie une direction si le stick/D-pad est
        maintenu et que le délai de répétition est écoulé (axes analogiques)."""
        for joypad in joysticks:
            if joypad is None:
                continue
            direction = axis_direction(joypad)
            if direction:
                now = pygame.time.get_ticks()
                if self.held != direction:
                    self.held = direction
                    self.next_time = now + REPEAT_DELAY_MS
                    return direction
                if now >= self.next_time:
                    self.next_time = now + REPEAT_RATE_MS
                    return direction
                return None
        self.held = None
        return None
