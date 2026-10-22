"""Shared look for the in-game UI: panels, bars and text helpers so HUD, minimap and boss bar match."""
import pygame

PANEL_BG = (16, 14, 24)
PANEL_BORDER = (78, 68, 104)
PANEL_HIGHLIGHT = (120, 108, 150)
TEXT = (238, 234, 246)
TEXT_DIM = (150, 144, 170)
ACCENT = (232, 186, 96)

_panel_cache: dict[tuple, pygame.Surface] = {}


def lerp_color(a, b, t: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def shade(color, factor: float) -> tuple[int, int, int]:
    """factor > 1 lightens, < 1 darkens."""
    if factor >= 1:
        return lerp_color(color, (255, 255, 255), min(1.0, factor - 1))
    return tuple(int(c * factor) for c in color)


def draw_panel(surface: pygame.Surface, rect: pygame.Rect, alpha: int = 215, border=PANEL_BORDER,
               radius: int = 8, accent=None):
    """Translucent rounded panel with a soft inner highlight and an optional accent stripe on top."""
    key = (rect.width, rect.height, alpha, border, radius, accent)
    panel = _panel_cache.get(key)
    if panel is None:
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, (*PANEL_BG, alpha), panel.get_rect(), border_radius=radius)
        pygame.draw.rect(panel, (*shade(PANEL_BG, 1.25), min(255, alpha)), panel.get_rect().inflate(-4, -4),
                         width=1, border_radius=max(2, radius - 2))
        pygame.draw.rect(panel, border, panel.get_rect(), width=2, border_radius=radius)
        if accent:
            pygame.draw.line(panel, accent, (radius + 2, 1), (rect.width - radius - 2, 1), 2)
        _panel_cache[key] = panel
    surface.blit(panel, rect.topleft)


def draw_text(surface: pygame.Surface, font: pygame.font.Font, text: str, color, pos, anchor: str = "topleft",
              shadow: bool = True) -> pygame.Rect:
    img = font.render(text, True, color)
    rect = img.get_rect(**{anchor: pos})
    if shadow:
        surface.blit(font.render(text, True, (0, 0, 0)), rect.move(1, 1))
    surface.blit(img, rect)
    return rect


def draw_bar(surface: pygame.Surface, rect: pygame.Rect, pct: float, color, font=None, label: str = "",
             ghost_pct: float | None = None, bg=None, radius: int = 4):
    """Glossy rounded bar. `ghost_pct` draws a pale trail (recent damage) behind the fill."""
    pct = max(0.0, min(1.0, pct))
    bg = bg or shade(color, 0.28)
    pygame.draw.rect(surface, bg, rect, border_radius=radius)

    if ghost_pct is not None and ghost_pct > pct:
        gw = int(rect.width * min(1.0, ghost_pct))
        pygame.draw.rect(surface, (235, 225, 215), (rect.x, rect.y, gw, rect.height), border_radius=radius)

    fw = int(rect.width * pct)
    if fw > 0:
        fill = pygame.Rect(rect.x, rect.y, max(fw, 2 * radius if pct > 0 else 0), rect.height)
        fill.width = min(fill.width, rect.width)
        pygame.draw.rect(surface, color, fill, border_radius=radius)
        gloss = pygame.Rect(fill.x + 2, fill.y + 1, max(0, fill.width - 4), max(1, fill.height // 2 - 1))
        gloss_surf = pygame.Surface(gloss.size, pygame.SRCALPHA)
        gloss_surf.fill((255, 255, 255, 46))
        surface.blit(gloss_surf, gloss.topleft)
        pygame.draw.line(surface, shade(color, 0.6), (fill.x + 2, fill.bottom - 1), (fill.right - 3, fill.bottom - 1))

    pygame.draw.rect(surface, shade(bg, 0.5), rect, width=1, border_radius=radius)
    if font and label:
        draw_text(surface, font, label, TEXT, rect.center, anchor="center")


def draw_pill(surface: pygame.Surface, font: pygame.font.Font, text: str, color, pos, anchor: str = "topleft") -> pygame.Rect:
    img = font.render(text, True, color)
    rect = img.get_rect().inflate(12, 4)
    setattr(rect, anchor, pos)
    pill = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(pill, (*shade(color, 0.25), 200), pill.get_rect(), border_radius=rect.height // 2)
    pygame.draw.rect(pill, color, pill.get_rect(), width=1, border_radius=rect.height // 2)
    surface.blit(pill, rect.topleft)
    surface.blit(img, img.get_rect(center=rect.center))
    return rect
