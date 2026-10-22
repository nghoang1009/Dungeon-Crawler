import time
import pygame
from settings import SCREEN_WIDTH
from ui.theme import draw_panel, draw_bar, draw_text, draw_pill, shade, ACCENT

BAR_W = 400          # narrow enough to clear the player HUD (left) and the minimap (right)
FADE_SECONDS = 0.35
GHOST_DELAY = 0.45   # seconds before the pale damage trail starts draining
GHOST_SPEED = 0.6    # fraction of max HP per second


class BossBar:
    """
    Top-centre Boss health bar. It only appears while the encounter is on (`engaged`), fades in and
    out, and shows a pale trail for recent damage. Walking past an unaware boss never shows it.
    """
    def __init__(self, font_name: pygame.font.Font, font_phase: pygame.font.Font):
        self.font_name = font_name
        self.font_phase = font_phase
        self._alpha = 0.0
        self._ghost = 1.0
        self._last_pct = 1.0
        self._ghost_hold = 0.0
        self._last_time = time.perf_counter()
        self._boss_id = None

    def _tick(self) -> float:
        now = time.perf_counter()
        dt = min(0.1, now - self._last_time)
        self._last_time = now
        return dt

    def render(self, surface: pygame.Surface, boss, engaged: bool = True):
        dt = self._tick()

        if boss is not self._boss_id:
            self._boss_id = boss
            self._alpha = 0.0
            self._ghost = self._last_pct = 1.0

        show = bool(boss and boss.is_alive and engaged)
        self._alpha = min(1.0, self._alpha + dt / FADE_SECONDS) if show else max(0.0, self._alpha - dt / FADE_SECONDS)
        if self._alpha <= 0.0 or not boss:
            return

        pct = max(0.0, min(1.0, boss.current_hp / max(1, boss.max_hp)))
        if pct < self._last_pct:
            self._ghost_hold = GHOST_DELAY
        self._last_pct = pct
        if self._ghost_hold > 0:
            self._ghost_hold -= dt
        else:
            self._ghost = max(pct, self._ghost - GHOST_SPEED * dt)
        self._ghost = max(self._ghost, pct)

        panel_rect = pygame.Rect(0, 0, BAR_W + 28, 62)
        layer = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        draw_panel(layer, layer.get_rect(), alpha=225, border=(150, 52, 44), accent=(214, 70, 58))

        draw_text(layer, self.font_name, boss.name, ACCENT, (panel_rect.centerx, 8), anchor="midtop")
        draw_pill(layer, self.font_phase, f"PHASE {boss.phase}", (240, 110, 100), (panel_rect.right - 12, 8), anchor="topright")

        bar = pygame.Rect(14, 34, BAR_W, 18)
        draw_bar(layer, bar, pct, (214, 48, 48), font=self.font_phase,
                 label=f"{boss.current_hp:,} / {boss.max_hp:,}", ghost_pct=self._ghost, bg=shade((214, 48, 48), 0.22))

        layer.set_alpha(int(255 * self._alpha))
        surface.blit(layer, ((SCREEN_WIDTH - panel_rect.width) // 2, 12))
