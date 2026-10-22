import pygame
from settings import (
    COLOR_HP_RED, COLOR_XP_CYAN, COLOR_STAMINA_GREEN, COLOR_MANA_BLUE,
    COLOR_GOLD, SCREEN_WIDTH, SCREEN_HEIGHT
)
from core.sprite_loader import SpriteSheetLoader
from progression.level_system import LevelSystem
from ui.widgets import Button, button_at
from ui.theme import (
    draw_panel, draw_bar, draw_text, draw_pill, shade,
    TEXT, TEXT_DIM, ACCENT, PANEL_BORDER
)

PANEL_X, PANEL_Y, PANEL_W = 12, 12, 292
HINT = "LMB Attack   SPACE Dash   F Skill   Q Potion   E Use   N Music"


class HUD:
    """
    Player HUD: portrait, name/level/floor, HP / MP / stamina / EXP bars, gold, score, weapon and potion
    slots, status effects, relic icons with hover tooltips and a controls hint along the bottom.
    The Mana bar is only drawn for classes that use mana (e.g. Mage).
    """
    def __init__(self, font_small: pygame.font.Font, font_medium: pygame.font.Font):
        self.font_small = font_small
        self.font_medium = font_medium
        self.relic_icon_rects = []
        self.loader = SpriteSheetLoader()
        self.loader.initialize()
        self._icon_cache: dict[tuple[str, int], pygame.Surface] = {}

    # ------------------------------------------------------------ toolbar (mouse)
    def toolbar_buttons(self) -> list[Button]:
        y = SCREEN_HEIGHT - 42
        return [
            Button("inventory", pygame.Rect(12, y, 66, 30), "BAG", "I"),
            Button("map", pygame.Rect(84, y, 66, 30), "MAP", "M"),
            Button("pause", pygame.Rect(156, y, 74, 30), "PAUSE", "P"),
        ]

    def toolbar_action(self, pos) -> str | None:
        hit = button_at(self.toolbar_buttons(), pos)
        return hit.action if hit else None

    def is_over_ui(self, pos) -> bool:
        return any(b.rect.collidepoint(pos) for b in self.toolbar_buttons())

    def _icon(self, name: str, size: int) -> pygame.Surface:
        key = (name, size)
        if key not in self._icon_cache:
            self._icon_cache[key] = self.loader.get_sprite(name, dest_size=size)
        return self._icon_cache[key]

    def render(self, surface: pygame.Surface, player, dungeon_level: int = 1):
        self.relic_icon_rects.clear()
        uses_mana = getattr(player, "uses_mana", False)

        status_items = []
        if "slow" in player.status_effects:
            status_items.append(("SLOW", (120, 180, 255)))
        if "poison" in player.status_effects:
            status_items.append(("POISON", (90, 230, 100)))
        if "burn" in player.status_effects:
            status_items.append(("BURN", (255, 130, 50)))

        panel_h = 156 + (16 if uses_mana else 0) + (26 if status_items else 0)
        panel = pygame.Rect(PANEL_X, PANEL_Y, PANEL_W, panel_h)
        draw_panel(surface, panel, alpha=222, accent=ACCENT)

        # Portrait + identity
        cls_name = getattr(player, "class_name", "Hero")
        hero_name = getattr(player, "name", "")
        port = pygame.Rect(panel.x + 10, panel.y + 10, 44, 44)
        pygame.draw.rect(surface, shade((30, 26, 44), 1.0), port, border_radius=6)
        pygame.draw.rect(surface, PANEL_BORDER, port, width=2, border_radius=6)
        surface.blit(self._icon(cls_name, 36), (port.x + 4, port.y + 4))

        title = hero_name if hero_name and hero_name != "Hero" else cls_name
        draw_text(surface, self.font_medium, title, TEXT, (port.right + 10, port.y - 1))
        draw_text(surface, self.font_small, f"Lv {player.level}  {cls_name}", TEXT_DIM, (port.right + 10, port.y + 22))
        draw_pill(surface, self.font_small, f"F {dungeon_level}/10", (190, 170, 240),
                  (panel.right - 10, panel.y + 12), anchor="topright")

        # Bars
        bx, bw = panel.x + 10, panel.width - 20
        y = port.bottom + 8
        draw_bar(surface, pygame.Rect(bx, y, bw, 16), player.current_hp / max(1, player.max_hp), COLOR_HP_RED,
                 font=self.font_small, label=f"{player.current_hp} / {player.max_hp}")
        y += 20
        if uses_mana:
            mana_val = max(0, min(int(player.mana), int(player.max_mana)))
            draw_bar(surface, pygame.Rect(bx, y, bw, 12), mana_val / max(1, player.max_mana), COLOR_MANA_BLUE,
                     font=self.font_small, label=f"{mana_val} / {int(player.max_mana)}")
            y += 16
        draw_bar(surface, pygame.Rect(bx, y, bw, 7), player.stamina / max(1, player.max_stamina), COLOR_STAMINA_GREEN)
        y += 11
        req_exp = LevelSystem.get_required_exp(player.level)
        draw_bar(surface, pygame.Rect(bx, y, bw, 7), player.exp / max(1, req_exp), COLOR_XP_CYAN)
        y += 14

        # Gold / score
        surface.blit(self._icon("coin", 16), (bx, y))
        draw_text(surface, self.font_small, f"{player.gold}", COLOR_GOLD, (bx + 20, y))
        draw_text(surface, self.font_small, f"{getattr(player, 'score', 0):06d}", (255, 230, 120),
                  (panel.right - 10, y), anchor="topright")
        y += 22

        # Weapon + potions
        wp = player.current_weapon
        wp_name = wp.display_name if wp else "Fists"
        wp_col = wp.rarity_color if wp else TEXT
        if wp:
            surface.blit(self._icon(wp.name, 22), (bx, y - 4))
        draw_text(surface, self.font_small, wp_name, wp_col, (bx + 26, y))

        slot_x = panel.right - 10
        if uses_mana:
            mp_pots = player.inventory.get_potion_count("MANA")
            draw_text(surface, self.font_small, f"2 x{mp_pots}", (130, 170, 250), (slot_x, y), anchor="topright")
            slot_x -= 46
        hp_pots = player.inventory.get_potion_count("HEALTH")
        draw_text(surface, self.font_small, f"Q x{hp_pots}", (240, 130, 130), (slot_x, y), anchor="topright")
        y += 22

        # Status effects
        if status_items:
            sx = bx
            for tag, col in status_items:
                r = draw_pill(surface, self.font_small, tag, col, (sx, y))
                sx = r.right + 6

        # Relics
        relics = getattr(player, "relics", [])
        if relics:
            ry = panel.bottom + 8
            rw = len(relics) * 34 + 14
            r_panel = pygame.Rect(PANEL_X, ry, rw, 44)
            draw_panel(surface, r_panel, alpha=215, border=(110, 78, 150))
            ix = r_panel.x + 8
            for relic in relics:
                slot = pygame.Rect(ix, r_panel.y + 7, 30, 30)
                pygame.draw.rect(surface, shade(relic.color, 0.22), slot, border_radius=5)
                pygame.draw.rect(surface, relic.color, slot, width=2, border_radius=5)
                surface.blit(self._icon(relic.name, 24), (slot.x + 3, slot.y + 3))
                self.relic_icon_rects.append((slot, relic))
                ix += 34

        mouse = pygame.mouse.get_pos()
        for b in self.toolbar_buttons():
            b.draw(surface, self.font_small, mouse)

        # Controls hint (bottom centre, unobtrusive)
        hint = self.font_small.render(HINT, True, TEXT_DIM)
        hint_rect = hint.get_rect(midbottom=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 8))
        bg = pygame.Surface(hint_rect.inflate(20, 8).size, pygame.SRCALPHA)
        pygame.draw.rect(bg, (12, 10, 18, 140), bg.get_rect(), border_radius=8)
        surface.blit(bg, hint_rect.inflate(20, 8).topleft)
        surface.blit(hint, hint_rect)

    def render_relic_tooltips(self, surface: pygame.Surface, mouse_pos: tuple[int, int]):
        for slot_rect, relic in self.relic_icon_rects:
            if slot_rect.collidepoint(mouse_pos):
                self._draw_tooltip(surface, mouse_pos, relic)
                break

    def _draw_tooltip(self, surface: pygame.Surface, mouse_pos: tuple[int, int], relic):
        mx, my = mouse_pos
        tt_w = 300
        text_w = tt_w - 24
        desc_lines = self._wrap(relic.description, text_w)
        effect_lines = self._wrap(relic.effect_text, text_w)
        tt_h = 50 + len(desc_lines) * 18 + 26 + len(effect_lines) * 18 + 10
        rect = pygame.Rect(min(SCREEN_WIDTH - tt_w - 10, mx + 14), min(surface.get_height() - tt_h - 10, my + 14),
                           tt_w, tt_h)
        draw_panel(surface, rect, alpha=240, border=relic.color)

        surface.blit(self._icon(relic.name, 24), (rect.x + 10, rect.y + 9))
        draw_text(surface, self.font_medium, relic.name, relic.color, (rect.x + 40, rect.y + 8))
        draw_text(surface, self.font_small, f"[{relic.rarity}]", TEXT_DIM, (rect.right - 10, rect.y + 12), anchor="topright")

        y = rect.y + 42
        for line in desc_lines:
            draw_text(surface, self.font_small, line, TEXT, (rect.x + 12, y))
            y += 18
        y += 8
        draw_text(surface, self.font_small, "Effect", COLOR_GOLD, (rect.x + 12, y))
        y += 18
        for line in effect_lines:
            draw_text(surface, self.font_small, line, (130, 240, 170), (rect.x + 12, y))
            y += 18

    def _wrap(self, text: str, max_width: int) -> list[str]:
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if line and self.font_small.size(trial)[0] > max_width:
                lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
        return lines
