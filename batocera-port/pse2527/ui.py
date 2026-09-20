"""Widgets et utilitaires de rendu pour le jeu pygame PSE25-27."""
import os
import pygame
import pygame.freetype

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')

# --- Palette (reprise du thème par défaut de l'appli web index.html) ---
COLOR_BG = (245, 245, 254)
COLOR_PRIMARY = (0, 0, 145)       # --primary
COLOR_ACCENT = (225, 0, 15)       # --accent
COLOR_TEXT = (22, 22, 22)
COLOR_WHITE = (255, 255, 255)
COLOR_SUCCESS = (24, 117, 60)
COLOR_ERROR = (206, 5, 0)
COLOR_PANEL = (255, 255, 255)
COLOR_SELECTED_BG = (0, 0, 145)
COLOR_SELECTED_TEXT = (255, 255, 255)
COLOR_HINT_BG = (0, 0, 60)


class Fonts:
    def __init__(self, scale=1.0):
        regular_path = os.path.join(ASSETS_DIR, 'DejaVuSans.ttf')
        bold_path = os.path.join(ASSETS_DIR, 'DejaVuSans-Bold.ttf')
        self.title = pygame.freetype.Font(bold_path, int(48 * scale))
        self.large = pygame.freetype.Font(bold_path, int(34 * scale))
        self.medium = pygame.freetype.Font(regular_path, int(26 * scale))
        self.small = pygame.freetype.Font(regular_path, int(20 * scale))
        self.hint = pygame.freetype.Font(regular_path, int(18 * scale))


def draw_text(surface, font, text, pos, color=COLOR_TEXT, max_width=None):
    """Dessine du texte, avec retour à la ligne automatique si max_width est fourni.
    Renvoie la hauteur totale dessinée."""
    if max_width is None:
        font.render_to(surface, pos, text, color)
        return font.get_rect(text).height

    lines = wrap_text(font, text, max_width)
    x, y = pos
    line_h = font.get_sized_height() + 6
    for line in lines:
        font.render_to(surface, (x, y), line, color)
        y += line_h
    return y - pos[1]


def wrap_text(font, text, max_width):
    words = text.split(' ')
    lines = []
    current = ''
    for word in words:
        candidate = (current + ' ' + word).strip()
        rect = font.get_rect(candidate)
        if rect.width > max_width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def wrap_paragraphs(font, text, max_width):
    """Découpe un texte multi-paragraphes (format des fiches de révision : un
    paragraphe par ligne source, lignes vides = séparateurs) en lignes
    d'affichage repliées à max_width, une ligne vide étant conservée entre
    paragraphes pour l'aération visuelle."""
    display_lines = []
    for raw_line in text.split('\n'):
        raw_line = raw_line.strip()
        if not raw_line:
            display_lines.append('')
            continue
        display_lines.extend(wrap_text(font, raw_line, max_width))
    return display_lines


SCROLL_SPEED = 70   # px/s
SCROLL_GAP = 60      # px entre la fin et la reprise du texte, en boucle


def draw_scrolling_text(surface, font, text, rect, color=COLOR_TEXT):
    """Dessine `text` aligné à gauche et centré verticalement dans `rect`. S'il
    tient dans la largeur, affichage statique. Sinon, défilement horizontal en
    boucle (clippé à `rect`), sans jamais réduire la taille de police : c'est
    la seule façon de garder un texte long intégralement lisible dans un cadre
    fixe (titre d'en-tête, libellé de menu, choix de quiz...)."""
    text_rect = font.get_rect(text)
    y = rect.y + (rect.height - text_rect.height) // 2
    if text_rect.width <= rect.width or rect.width <= 0:
        font.render_to(surface, (rect.x, y), text, color)
        return

    old_clip = surface.get_clip()
    surface.set_clip(rect)
    loop_w = text_rect.width + SCROLL_GAP
    offset = int((pygame.time.get_ticks() / 1000.0 * SCROLL_SPEED) % loop_w)
    x = rect.x - offset
    while x < rect.right:
        font.render_to(surface, (x, y), text, color)
        x += loop_w
    surface.set_clip(old_clip)


TTS_LABELS = {
    'generating': 'VOIX : préparation…',
    'playing': 'VOIX : lecture…',
    'error': 'VOIX : erreur',
}


def draw_tts_indicator(surface, fonts, screen_w, status, header_h):
    """Petit badge dans l'en-tête, en haut à droite, indiquant l'état de la
    synthèse vocale. Silencieux (rien affiché) si inactif ou indisponible,
    pour ne pas encombrer l'écran en dehors d'une lecture demandée."""
    label = TTS_LABELS.get(status)
    if not label:
        return
    rect = fonts.small.get_rect(label)
    pad = 10
    badge_h = rect.height + 2 * pad
    badge = pygame.Rect(screen_w - rect.width - 2 * pad - 16, (header_h - badge_h) // 2, rect.width + 2 * pad, badge_h)
    pygame.draw.rect(surface, COLOR_ACCENT, badge, border_radius=10)
    fonts.small.render_to(surface, (badge.x + pad, badge.y + pad), label, COLOR_WHITE)


def draw_button_hints(surface, fonts, screen_w, screen_h, hints, right_text=None, right_color=COLOR_WHITE):
    """hints: liste de tuples (bouton, libellé), ex: [('A', 'Valider'), ('B', 'Retour')].
    right_text : texte optionnel affiché à droite du même bandeau (même police
    que les instructions), ex. le statut de lecture d'un média."""
    bar_h = 48
    pygame.draw.rect(surface, COLOR_HINT_BG, (0, screen_h - bar_h, screen_w, bar_h))
    x = 24
    for button, label in hints:
        text = "[{}] {}".format(button, label)
        rect = fonts.hint.get_rect(text)
        fonts.hint.render_to(surface, (x, screen_h - bar_h // 2 - rect.height // 2), text, COLOR_WHITE)
        x += rect.width + 40
    if right_text:
        rect = fonts.hint.get_rect(right_text)
        fonts.hint.render_to(surface, (screen_w - rect.width - 24, screen_h - bar_h // 2 - rect.height // 2), right_text, right_color)


class ListMenu:
    """Menu vertical navigable au D-pad, avec défilement si la liste est longue."""

    def __init__(self, items, screen_w, screen_h, top=100, item_height=64, visible_count=None):
        self.items = items  # liste de dicts avec au moins 'label'
        self.selected = 0
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.top = top
        self.item_height = item_height
        self.visible_count = visible_count or max(1, (screen_h - top - 56) // item_height)
        self.scroll = 0

    def move(self, direction):
        if not self.items:
            return
        if direction == 'up':
            self.selected = (self.selected - 1) % len(self.items)
        elif direction == 'down':
            self.selected = (self.selected + 1) % len(self.items)
        self._adjust_scroll()

    def _adjust_scroll(self):
        if self.selected < self.scroll:
            self.scroll = self.selected
        elif self.selected >= self.scroll + self.visible_count:
            self.scroll = self.selected - self.visible_count + 1

    def current(self):
        if not self.items:
            return None
        return self.items[self.selected]

    def draw(self, surface, fonts, label_key='label', badge_key=None):
        visible = self.items[self.scroll:self.scroll + self.visible_count]
        for i, item in enumerate(visible):
            real_index = self.scroll + i
            y = self.top + i * self.item_height
            rect = pygame.Rect(60, y, self.screen_w - 120, self.item_height - 10)
            is_selected = (real_index == self.selected)
            if is_selected:
                pygame.draw.rect(surface, COLOR_SELECTED_BG, rect, border_radius=10)
            else:
                pygame.draw.rect(surface, COLOR_PANEL, rect, border_radius=10)
                pygame.draw.rect(surface, (221, 221, 221), rect, width=2, border_radius=10)
            color = COLOR_SELECTED_TEXT if is_selected else COLOR_TEXT
            label = item[label_key]
            badge_reserved = 0
            if badge_key and item.get(badge_key):
                badge = str(item[badge_key])
                badge_rect = fonts.small.get_rect(badge)
                badge_reserved = badge_rect.width + 36
                fonts.small.render_to(surface, (rect.right - badge_rect.width - 20, rect.y + (rect.height - badge_rect.height) // 2), badge, color)
            max_label_width = rect.width - 48 - badge_reserved
            label_rect = pygame.Rect(rect.x + 24, rect.y, max_label_width, rect.height)
            draw_scrolling_text(surface, fonts.medium, label, label_rect, color)

        # indicateurs de défilement
        if self.scroll > 0:
            fonts.small.render_to(surface, (self.screen_w // 2 - 10, self.top - 30), "▲", COLOR_PRIMARY)
        if self.scroll + self.visible_count < len(self.items):
            fonts.small.render_to(surface, (self.screen_w // 2 - 10, self.top + self.visible_count * self.item_height + 4), "▼", COLOR_PRIMARY)


def draw_progress_bar(surface, rect, fraction, fg_color=COLOR_PRIMARY, bg_color=(221, 221, 221)):
    """Barre de progression simple (compte à rebours quiz, minuteur flashcard),
    même principe visuel que .timer-fill dans la page web : `fraction` (0..1)
    est la portion remplie depuis la gauche."""
    fraction = max(0.0, min(1.0, fraction))
    pygame.draw.rect(surface, bg_color, rect, border_radius=rect.height // 2)
    if fraction > 0:
        fill_rect = pygame.Rect(rect.x, rect.y, int(rect.width * fraction), rect.height)
        pygame.draw.rect(surface, fg_color, fill_rect, border_radius=rect.height // 2)


LETTER_BADGES = ('A', 'B', 'C', 'D')  # esprit manette NeoGeo (4 boutons de face en ligne)


def draw_choice_rows(surface, fonts, screen_w, top, bottom, choices, selected_index,
                      correct_index=None, chosen_index=None):
    """Dessine les 4 choix du quiz en pavés larges avec une pastille A/B/C/D à
    gauche (bouton physique correspondant), en occupant tout l'espace vertical
    disponible entre `top` et `bottom`.

    - Avant réponse (correct_index is None) : le choix `selected_index` (repli
      D-pad) est simplement surligné.
    - Après réponse : le bon choix est en vert, le choix donné faux en rouge.
    """
    margin = 60
    gap = 16
    count = len(choices)
    total_gap = gap * (count - 1)
    item_h = (bottom - top - total_gap) // count
    badge_size = min(item_h - 16, 64)

    for i, label in enumerate(choices):
        y = top + i * (item_h + gap)
        rect = pygame.Rect(margin, y, screen_w - 2 * margin, item_h)

        if correct_index is not None:
            if i == correct_index:
                bg, fg = COLOR_SUCCESS, COLOR_WHITE
            elif i == chosen_index:
                bg, fg = COLOR_ERROR, COLOR_WHITE
            else:
                bg, fg = COLOR_PANEL, COLOR_TEXT
        else:
            if i == selected_index:
                bg, fg = COLOR_SELECTED_BG, COLOR_SELECTED_TEXT
            else:
                bg, fg = COLOR_PANEL, COLOR_TEXT

        pygame.draw.rect(surface, bg, rect, border_radius=14)
        if bg == COLOR_PANEL:
            pygame.draw.rect(surface, (221, 221, 221), rect, width=2, border_radius=14)

        badge_rect = pygame.Rect(rect.x + 16, rect.y + (rect.height - badge_size) // 2, badge_size, badge_size)
        badge_color = fg if bg != COLOR_PANEL else COLOR_PRIMARY
        pygame.draw.rect(surface, badge_color, badge_rect, width=3, border_radius=10)
        letter = LETTER_BADGES[i] if i < len(LETTER_BADGES) else str(i + 1)
        letter_rect = fonts.large.get_rect(letter)
        fonts.large.render_to(surface, (badge_rect.centerx - letter_rect.width // 2,
                                         badge_rect.centery - letter_rect.height // 2), letter, badge_color)

        text_x = badge_rect.right + 24
        text_rect_area = pygame.Rect(text_x, rect.y, rect.right - text_x - 20, rect.height)
        draw_scrolling_text(surface, fonts.medium, label, text_rect_area, fg)
