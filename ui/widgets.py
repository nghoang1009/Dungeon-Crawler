"""Clickable UI widgets shared by the menus, modals and the in-game toolbar."""
import pygame
from ui.theme import draw_text, shade, lerp_color, TEXT, TEXT_DIM, ACCENT

STYLES = {
    "normal": (74, 66, 104),
    "primary": (214, 164, 70),
    "danger": (200, 70, 66),
    "good": (80, 180, 110),
}


class Button:
    """A rectangular button identified by `action`; `hint` is a small hotkey tag drawn at the right."""
    def __init__(self, action: str, rect: pygame.Rect, label: str, hint: str = "", style: str = "normal",
                 enabled: bool = True):
        self.action = action
        self.rect = pygame.Rect(rect)
        self.label = label
        self.hint = hint
        self.style = style
        self.enabled = enabled

    def hovered(self, pos) -> bool:
        return self.enabled and self.rect.collidepoint(pos)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, mouse_pos, small_font=None,
             pressed: bool = False):
        base = STYLES.get(self.style, STYLES["normal"])
        hot = self.hovered(mouse_pos)
        if not self.enabled:
            fill, border, color = (30, 28, 38), (60, 56, 74), TEXT_DIM
        else:
            fill = lerp_color(shade(base, 0.28), shade(base, 0.5), 1.0 if hot else 0.0)
            border = shade(base, 1.25) if hot else base
            color = (255, 244, 205) if (hot and self.style == "primary") else TEXT
        rect = self.rect.move(0, 1 if (hot and pressed) else 0)

        pygame.draw.rect(surface, fill, rect, border_radius=7)
        gloss = pygame.Surface((rect.width - 6, max(1, rect.height // 2 - 2)), pygame.SRCALPHA)
        gloss.fill((255, 255, 255, 22 if hot else 12))
        surface.blit(gloss, (rect.x + 3, rect.y + 3))
        pygame.draw.rect(surface, border, rect, width=2 if hot else 1, border_radius=7)

        text_rect = draw_text(surface, font, self.label, color, rect.center, anchor="center")
        if self.hint and small_font and text_rect.right + 10 < rect.right - 10 - small_font.size(self.hint)[0]:
            draw_text(surface, small_font, self.hint, TEXT_DIM if not hot else ACCENT,
                      (rect.right - 10, rect.centery), anchor="midright")
        return text_rect


def button_at(buttons: list[Button], pos) -> Button | None:
    for b in buttons:
        if b.hovered(pos):
            return b
    return None
