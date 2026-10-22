import time
import pygame
from items.potion import Potion, PotionType
from combat.weapon import Weapon, WeaponCategory
from core.sprite_loader import SpriteSheetLoader
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    COLOR_COMMON, COLOR_UNCOMMON, COLOR_RARE, COLOR_EPIC, COLOR_LEGENDARY,
    COLOR_GOLD, COLOR_HP_RED, COLOR_MANA_BLUE, MANA_STAFF_COST
)
from ui.theme import draw_panel, draw_text, draw_bar, draw_pill, shade, TEXT, TEXT_DIM, ACCENT
from ui.widgets import Button

RARITY_COLORS = {
    "COMMON": COLOR_COMMON,
    "UNCOMMON": COLOR_UNCOMMON,
    "RARE": COLOR_RARE,
    "EPIC": COLOR_EPIC,
    "LEGENDARY": COLOR_LEGENDARY,
}

GRID_COLS = 5
GRID_ROWS = 5
SLOT_SIZE = 56
SLOT_GAP = 8
WEAPON_STRIP_SLOTS = 8
WEAPON_SLOT_SIZE = 36
WEAPON_SLOT_GAP = 5

SLOT_BG = (22, 19, 32)
SLOT_BORDER = (62, 55, 84)
EQUIPPED_GREEN = (120, 240, 130)
DOUBLE_CLICK_SECONDS = 0.35

# Maxima used to scale the weapon stat bars
STAT_MAX = {"DMG": 80.0, "SPD": 3.0, "RNG": 260.0, "CRIT": 0.5}


class InventoryUI:
    """
    Modal 5x5 grid Inventory window rendered over paused gameplay.
    Layout: backpack grid (left) with the weapon strip below it, and a detail panel with action buttons
    (right). Real item sprites come from the PNG/TXT mapping via SpriteSheetLoader. While open, gameplay
    simulation is frozen by Game.update() and all mouse events are consumed here (no click-through).

    Mouse: click to select, drag to swap slots, double-click to use / equip, buttons for Use / Equip /
    Drop / Close. Keys: [U] use, [G] drop, [I] / [ESC] close.
    """
    def __init__(self, font_title: pygame.font.Font, font_medium: pygame.font.Font):
        self.font_title = font_title
        self.font_medium = font_medium
        self.font_small = pygame.font.SysFont("consolas", 14)
        self.font_tiny = pygame.font.SysFont("consolas", 12)

        self.is_open = False
        self.sprite_loader = SpriteSheetLoader()
        self._sprite_cache: dict[tuple[str, int], pygame.Surface] = {}

        # Window geometry (centered)
        self.win_w = 800
        self.win_h = 568
        self.win_x = (SCREEN_WIDTH - self.win_w) // 2
        self.win_y = (SCREEN_HEIGHT - self.win_h) // 2
        self.win_rect = pygame.Rect(self.win_x, self.win_y, self.win_w, self.win_h)

        self.grid_x = self.win_x + 28
        self.grid_y = self.win_y + 112
        self.slot_rects: list[pygame.Rect] = []
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                self.slot_rects.append(pygame.Rect(
                    self.grid_x + col * (SLOT_SIZE + SLOT_GAP),
                    self.grid_y + row * (SLOT_SIZE + SLOT_GAP),
                    SLOT_SIZE, SLOT_SIZE
                ))
        grid_w = GRID_COLS * SLOT_SIZE + (GRID_COLS - 1) * SLOT_GAP
        grid_h = GRID_ROWS * SLOT_SIZE + (GRID_ROWS - 1) * SLOT_GAP
        self.grid_panel = pygame.Rect(self.grid_x - 12, self.grid_y - 34, grid_w + 24, grid_h + 46)

        strip_y = self.grid_panel.bottom + 26
        self.weapon_slot_rects: list[pygame.Rect] = []
        for i in range(WEAPON_STRIP_SLOTS):
            self.weapon_slot_rects.append(pygame.Rect(
                self.grid_x + i * (WEAPON_SLOT_SIZE + WEAPON_SLOT_GAP), strip_y,
                WEAPON_SLOT_SIZE, WEAPON_SLOT_SIZE
            ))
        strip_w = WEAPON_STRIP_SLOTS * WEAPON_SLOT_SIZE + (WEAPON_STRIP_SLOTS - 1) * WEAPON_SLOT_GAP
        self.strip_panel = pygame.Rect(self.grid_x - 12, strip_y - 30, max(strip_w, grid_w) + 24, WEAPON_SLOT_SIZE + 42)

        info_x = self.grid_panel.right + 18
        info_w = self.win_rect.right - 24 - info_x
        self.info_rect = pygame.Rect(info_x, self.grid_panel.y, info_w, 262)

        # Action buttons (2 x 2 under the detail panel)
        btn_w = (info_w - 12) // 2
        btn_h = 40
        by = self.info_rect.bottom + 14
        self.btn_use = pygame.Rect(info_x, by, btn_w, btn_h)
        self.btn_equip = pygame.Rect(info_x + btn_w + 12, by, btn_w, btn_h)
        self.btn_drop = pygame.Rect(info_x, by + btn_h + 10, btn_w, btn_h)
        self.btn_close = pygame.Rect(info_x + btn_w + 12, by + btn_h + 10, btn_w, btn_h)
        self.btn_x = pygame.Rect(self.win_rect.right - 44, self.win_y + 14, 30, 30)

        # Selection / interaction state
        self.selected_kind = "item"   # "item" | "weapon"
        self.selected_index = 0
        self.hover_slot = None        # (kind, index)
        self.drag_index = None        # grid index currently being dragged
        self.drag_pos = (0, 0)
        self.drop_mode = False        # stack quantity selector active
        self.drop_amount = 1
        self.message = ""
        self.message_until = 0.0
        self._last_click = (None, 0.0)

    # ------------------------------------------------------------------ state
    def open_ui(self):
        self.is_open = True
        self.selected_kind = "item"
        self.selected_index = 0
        self.drop_mode = False
        self.drag_index = None
        self.message = ""

    def close(self):
        self.is_open = False
        self.drop_mode = False
        self.drag_index = None

    def toggle(self):
        if self.is_open:
            self.close()
        else:
            self.open_ui()

    def set_message(self, text: str):
        self.message = text
        self.message_until = time.perf_counter() + 3.0

    # -------------------------------------------------------------- helpers
    def _get_selected_item(self, player):
        """Returns the currently selected stackable item, or None if selection invalid."""
        if self.selected_kind != "item":
            return None
        if 0 <= self.selected_index < len(player.inventory.items):
            return player.inventory.items[self.selected_index]
        return None

    def _get_selected_weapon(self, player):
        if self.selected_kind != "weapon":
            return None
        if 0 <= self.selected_index < len(player.inventory.weapons):
            return player.inventory.weapons[self.selected_index]
        return None

    def _get_sprite(self, obj, size: int) -> pygame.Surface:
        name = getattr(obj, "sprite_name", None) or getattr(obj, "name", "")
        key = (name, size)
        if key not in self._sprite_cache:
            self._sprite_cache[key] = self.sprite_loader.get_item_sprite(name, size)
        return self._sprite_cache[key]

    def _get_rarity(self, obj) -> str:
        return getattr(obj, "rarity", "COMMON")

    def _get_rarity_color(self, obj) -> tuple[int, int, int]:
        return RARITY_COLORS.get(self._get_rarity(obj), COLOR_COMMON)

    def _mana_cost_text(self, player, obj) -> str | None:
        """Condition / mana cost line shown in tooltip & detail panel."""
        if isinstance(obj, Potion):
            if obj.potion_type == PotionType.MANA:
                if not player.uses_mana:
                    return "Requires a class that uses Mana"
                return f"Restores {obj.potency} MP (not usable at full MP)"
            if obj.potion_type == PotionType.HEALTH:
                return f"Restores {obj.potency} HP (not usable at full HP)"
            return None
        if isinstance(obj, Weapon) and obj.weapon_category == WeaponCategory.STAFF and player.uses_mana:
            return f"Mana cost: {MANA_STAFF_COST} per cast"
        return None

    def _clamp_selection(self, player):
        if self.selected_kind == "item" and self.selected_index >= len(player.inventory.items):
            self.selected_index = max(0, len(player.inventory.items) - 1)
        if self.selected_kind == "weapon" and self.selected_index >= len(player.inventory.weapons):
            self.selected_index = max(0, len(player.inventory.weapons) - 1)
            if not player.inventory.weapons:
                self.selected_kind = "item"

    # ------------------------------------------------------------- actions
    def _use_selected(self, player):
        if self.drop_mode:
            return
        item = self._get_selected_item(player)
        if item is None:
            self.set_message("Select an item first.")
            return

        # Precondition feedback (inventory.use_item_at re-checks via item.use)
        if isinstance(item, Potion) and item.potion_type == PotionType.MANA:
            if not player.uses_mana:
                self.set_message("This class does not use Mana!")
                return
            if player.mana >= player.max_mana:
                self.set_message("Mana is already full.")
                return
        elif isinstance(item, Potion) and item.potion_type == PotionType.HEALTH:
            if player.current_hp >= player.max_hp:
                self.set_message("HP is already full.")
                return

        idx = self.selected_index
        consumed = player.inventory.use_item_at(idx, player)
        if consumed:
            self.set_message(f"Used {item.name}.")
        else:
            self.set_message("Cannot use this item right now.")
        self._clamp_selection(player)

    def _equip_selected(self, player):
        if self.drop_mode:
            return
        weapon = self._get_selected_weapon(player)
        if weapon is None:
            self.set_message("Only weapons can be equipped.")
            return
        player.switch_weapon(self.selected_index)
        self.set_message(f"Equipped {weapon.display_name}.")

    def _drop_selected(self, player):
        if not self.drop_mode:
            # Entering drop mode: stack > 1 lets the player pick an amount
            item = self._get_selected_item(player)
            weapon = self._get_selected_weapon(player)
            if item is None and weapon is None:
                self.set_message("Select an item first.")
                return
            if item is not None and item.quantity > 1:
                self.drop_mode = True
                self.drop_amount = 1
                self.set_message("Choose how many to drop, then confirm.")
            else:
                self._do_drop(player, 1)
            return
        self._do_drop(player, self.drop_amount)

    def _do_drop(self, player, quantity: int):
        self.drop_mode = False
        if self.selected_kind == "item":
            item = self._get_selected_item(player)
            if item is None:
                return
            name = item.name
            removed = player.inventory.remove_quantity(self.selected_index, quantity)
            self.set_message(f"Dropped {name} x{removed}.")
        else:
            weapon = self._get_selected_weapon(player)
            if weapon is None:
                return
            name = weapon.display_name
            player.inventory.remove_weapon(self.selected_index)
            if player.current_weapon_idx >= len(player.inventory.weapons):
                player.current_weapon_idx = max(0, len(player.inventory.weapons) - 1)
            self.set_message(f"Dropped {name}.")
        self._clamp_selection(player)

    def _swap_slots(self, player, a: int, b: int):
        items = player.inventory.items
        if 0 <= a < len(items) and 0 <= b < len(items) and a != b:
            items[a], items[b] = items[b], items[a]
            self.selected_index = b

    def _quick_action(self, player):
        """Double-click: use the item, or equip the weapon."""
        if self.selected_kind == "item":
            self._use_selected(player)
        else:
            self._equip_selected(player)

    # -------------------------------------------------------------- input
    def handle_input(self, event: pygame.event.Event, player) -> bool:
        """
        Returns True if the event was consumed by the Inventory UI
        (preventing gameplay actions underneath).
        """
        if not self.is_open:
            return False

        if event.type == pygame.KEYDOWN:
            if self.drop_mode:
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    self.drop_amount = max(1, self.drop_amount - 1)
                    return True
                if event.key in (pygame.K_RIGHT, pygame.K_d):
                    item = self._get_selected_item(player)
                    max_q = item.quantity if item else 1
                    self.drop_amount = min(max_q, self.drop_amount + 1)
                    return True
                if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    self._do_drop(player, self.drop_amount)
                    return True
                if event.key == pygame.K_ESCAPE:
                    self.drop_mode = False
                    return True
                return True  # block other keys while confirming drop

            if event.key in (pygame.K_i, pygame.K_ESCAPE):
                return False  # let Game close the inventory
            if event.key == pygame.K_u:
                self._use_selected(player)
                return True
            if event.key == pygame.K_g:
                self._drop_selected(player)
                return True
            return True  # swallow gameplay hotkeys while inventory is open

        if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            self._update_hover(event.pos)

            if event.type == pygame.MOUSEMOTION:
                if self.drag_index is not None:
                    self.drag_pos = event.pos
                return True

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Any click is consumed (no click-through to gameplay)
                if self.drop_mode:
                    self._handle_drop_mode_click(event.pos, player)
                    return True

                if self.btn_x.collidepoint(event.pos) or self.btn_close.collidepoint(event.pos):
                    self.close()
                    return True
                if self.btn_use.collidepoint(event.pos):
                    self._use_selected(player)
                    return True
                if self.btn_equip.collidepoint(event.pos):
                    self._equip_selected(player)
                    return True
                if self.btn_drop.collidepoint(event.pos):
                    self._drop_selected(player)
                    return True

                if self.win_rect.collidepoint(event.pos):
                    # Select item slot / weapon slot; start drag on item slots
                    for i, rect in enumerate(self.weapon_slot_rects):
                        if rect.collidepoint(event.pos) and i < len(player.inventory.weapons):
                            self.selected_kind = "weapon"
                            self.selected_index = i
                            self._register_click(("weapon", i), player)
                            return True
                    for i, rect in enumerate(self.slot_rects):
                        if rect.collidepoint(event.pos):
                            if i < len(player.inventory.items):
                                self.selected_kind = "item"
                                self.selected_index = i
                                self.drag_index = i
                                self.drag_pos = event.pos
                                self._register_click(("item", i), player)
                            return True
                return True

            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.drag_index is not None:
                    for i, rect in enumerate(self.slot_rects):
                        if rect.collidepoint(event.pos):
                            self._swap_slots(player, self.drag_index, i)
                            break
                    self.drag_index = None
                return True

        return False

    def _register_click(self, slot, player):
        """Double-click on the same slot triggers the quick action."""
        now = time.perf_counter()
        last_slot, last_time = self._last_click
        if slot == last_slot and now - last_time < DOUBLE_CLICK_SECONDS:
            self.drag_index = None
            self._quick_action(player)
            self._last_click = (None, 0.0)
        else:
            self._last_click = (slot, now)

    def _handle_drop_mode_click(self, pos, player):
        item = self._get_selected_item(player)
        max_q = item.quantity if item else 1
        for action, rect in self._drop_selector_rects():
            if rect.collidepoint(pos):
                if action == "minus":
                    self.drop_amount = max(1, self.drop_amount - 1)
                elif action == "plus":
                    self.drop_amount = min(max_q, self.drop_amount + 1)
                elif action == "confirm":
                    self._do_drop(player, self.drop_amount)
                elif action == "cancel":
                    self.drop_mode = False
                return

    def _drop_selector_panel(self) -> pygame.Rect:
        return pygame.Rect(self.info_rect.x, self.btn_use.y - 4, self.info_rect.width, 100)

    def _drop_selector_rects(self):
        """Button rects for the stack quantity selector (must match render)."""
        panel = self._drop_selector_panel()
        cx = panel.centerx
        return [
            ("minus", pygame.Rect(cx - 110, panel.y + 10, 46, 34)),
            ("plus", pygame.Rect(cx + 64, panel.y + 10, 46, 34)),
            ("confirm", pygame.Rect(panel.x + 10, panel.y + 54, (panel.width - 30) // 2, 36)),
            ("cancel", pygame.Rect(panel.centerx + 5, panel.y + 54, (panel.width - 30) // 2, 36)),
        ]

    def _update_hover(self, pos):
        self.hover_slot = None
        for i, rect in enumerate(self.slot_rects):
            if rect.collidepoint(pos):
                self.hover_slot = ("item", i)
                return
        for i, rect in enumerate(self.weapon_slot_rects):
            if rect.collidepoint(pos):
                self.hover_slot = ("weapon", i)
                return

    # -------------------------------------------------------------- render
    def render(self, surface: pygame.Surface, player):
        if self.message and time.perf_counter() > self.message_until:
            self.message = ""
        mouse = pygame.mouse.get_pos()
        self._update_hover(mouse)

        # Dim gameplay behind the window
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((6, 4, 12, 170))
        surface.blit(dim, (0, 0))

        draw_panel(surface, self.win_rect, alpha=246, accent=ACCENT, radius=10)
        self._render_header(surface, player, mouse)
        self._render_grid(surface, player)
        self._render_weapon_strip(surface, player)
        self._render_info_panel(surface, player)

        if self.drop_mode:
            self._render_drop_selector(surface, player)
        else:
            self._render_buttons(surface, player, mouse)

        # Footer: feedback message / hints
        footer_y = self.win_rect.bottom - 26
        if self.message:
            draw_text(surface, self.font_small, self.message, (150, 240, 160), (self.win_x + 28, footer_y))
        else:
            draw_text(surface, self.font_tiny,
                      "Click: select   Drag: swap   Double-click: use / equip   [U] Use   [G] Drop   [I] Close",
                      TEXT_DIM, (self.win_x + 28, footer_y + 2))

        # Hover tooltip (topmost)
        if self.hover_slot and not self.drop_mode and self.drag_index is None:
            self._render_hover_tooltip(surface, player, mouse)

        # Dragged item ghost following the cursor
        if self.drag_index is not None and self.drag_index < len(player.inventory.items):
            ghost = self._get_sprite(player.inventory.items[self.drag_index], 40).copy()
            ghost.set_alpha(200)
            surface.blit(ghost, (self.drag_pos[0] - 20, self.drag_pos[1] - 20))

    def _render_header(self, surface, player, mouse):
        draw_text(surface, self.font_title, "INVENTORY", ACCENT, (self.win_x + 28, self.win_y + 16))

        x = self.win_x + 28
        y = self.win_y + 58
        chips = [
            (f"Lv {player.level} {player.class_name}", (190, 170, 240)),
            (f"HP {player.current_hp}/{player.max_hp}", COLOR_HP_RED),
        ]
        if player.uses_mana:
            chips.append((f"MP {int(player.mana)}/{int(player.max_mana)}", COLOR_MANA_BLUE))
        chips.append((f"{player.gold} G", COLOR_GOLD))
        for text, color in chips:
            rect = draw_pill(surface, self.font_small, text, color, (x, y))
            x = rect.right + 8

        Button("close", self.btn_x, "X", style="danger").draw(surface, self.font_medium, mouse)

    def _draw_slot(self, surface, rect, color=None, hovered=False, selected=False, equipped=False):
        pygame.draw.rect(surface, SLOT_BG, rect, border_radius=6)
        if color:
            glow = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(glow, (*color, 38), glow.get_rect(), border_radius=6)
            surface.blit(glow, rect.topleft)
        if hovered:
            veil = pygame.Surface(rect.size, pygame.SRCALPHA)
            veil.fill((255, 255, 255, 22))
            surface.blit(veil, rect.topleft)

        border = shade(color, 0.8) if color else SLOT_BORDER
        width = 2
        if hovered:
            border, width = (190, 182, 220), 2
        if equipped:
            border = EQUIPPED_GREEN
        if selected:
            border, width = (255, 224, 120), 3
        pygame.draw.rect(surface, border, rect, width=width, border_radius=6)

    def _render_grid(self, surface, player):
        items = player.inventory.items
        draw_panel(surface, self.grid_panel, alpha=200, radius=8)
        draw_text(surface, self.font_small, "BACKPACK", TEXT, (self.grid_panel.x + 12, self.grid_panel.y + 8))
        draw_text(surface, self.font_small, f"{len(items)}/{GRID_COLS * GRID_ROWS}", TEXT_DIM,
                  (self.grid_panel.right - 12, self.grid_panel.y + 8), anchor="topright")

        for i, rect in enumerate(self.slot_rects):
            if i >= len(items):
                self._draw_slot(surface, rect)
                continue

            item = items[i]
            rarity = self._get_rarity(item)
            color = self._get_rarity_color(item) if rarity != "COMMON" else None
            self._draw_slot(surface, rect, color,
                            hovered=self.hover_slot == ("item", i),
                            selected=self.selected_kind == "item" and self.selected_index == i)
            if i == self.drag_index:
                continue

            surface.blit(self._get_sprite(item, 40), (rect.centerx - 20, rect.centery - 20))
            if item.quantity > 1:
                draw_text(surface, self.font_tiny, f"x{item.quantity}", TEXT, (rect.right - 5, rect.bottom - 4),
                          anchor="bottomright")

    def _render_weapon_strip(self, surface, player):
        draw_panel(surface, self.strip_panel, alpha=200, radius=8)
        draw_text(surface, self.font_small, "WEAPONS", TEXT, (self.strip_panel.x + 12, self.strip_panel.y + 8))
        draw_text(surface, self.font_tiny, "[TAB] quick swap", TEXT_DIM,
                  (self.strip_panel.right - 12, self.strip_panel.y + 10), anchor="topright")

        weapons = player.inventory.weapons
        for i, rect in enumerate(self.weapon_slot_rects):
            if i >= len(weapons):
                self._draw_slot(surface, rect)
                continue

            weapon = weapons[i]
            rarity = self._get_rarity(weapon)
            color = self._get_rarity_color(weapon) if rarity != "COMMON" else None
            equipped = i == player.current_weapon_idx
            self._draw_slot(surface, rect, color,
                            hovered=self.hover_slot == ("weapon", i),
                            selected=self.selected_kind == "weapon" and self.selected_index == i,
                            equipped=equipped)
            surface.blit(self._get_sprite(weapon, 28), (rect.centerx - 14, rect.centery - 14))
            if equipped:
                badge = pygame.Rect(rect.right - 12, rect.y - 3, 15, 15)
                pygame.draw.circle(surface, EQUIPPED_GREEN, badge.center, 7)
                draw_text(surface, self.font_tiny, "E", (10, 40, 16), badge.center, anchor="center", shadow=False)

    def _stat_row(self, surface, x, y, w, label, value_text, pct, color):
        draw_text(surface, self.font_tiny, label, TEXT_DIM, (x, y))
        draw_bar(surface, pygame.Rect(x + 44, y + 2, w - 130, 9), pct, color, radius=3)
        draw_text(surface, self.font_tiny, value_text, TEXT, (x + w, y), anchor="topright")

    def _render_info_panel(self, surface, player):
        draw_panel(surface, self.info_rect, alpha=205, radius=8)
        obj = self._get_selected_item(player) or self._get_selected_weapon(player)
        if obj is None:
            draw_text(surface, self.font_small, "Select an item to see its details.", TEXT_DIM,
                      self.info_rect.center, anchor="center")
            return

        x = self.info_rect.x + 16
        y = self.info_rect.y + 14
        color = self._get_rarity_color(obj)

        frame = pygame.Rect(x, y, 70, 70)
        pygame.draw.rect(surface, SLOT_BG, frame, border_radius=8)
        glow = pygame.Surface(frame.size, pygame.SRCALPHA)
        pygame.draw.rect(glow, (*color, 60), glow.get_rect(), border_radius=8)
        surface.blit(glow, frame.topleft)
        pygame.draw.rect(surface, color, frame, width=2, border_radius=8)
        surface.blit(self._get_sprite(obj, 54), (frame.centerx - 27, frame.centery - 27))

        name = obj.display_name if isinstance(obj, Weapon) else obj.name
        draw_text(surface, self.font_medium, name, color, (frame.right + 14, y + 2))
        draw_pill(surface, self.font_tiny, self._get_rarity(obj), color, (frame.right + 14, y + 32))
        if isinstance(obj, Potion):
            draw_text(surface, self.font_small, f"x{obj.quantity}", TEXT_DIM,
                      (self.info_rect.right - 16, y + 4), anchor="topright")

        y = frame.bottom + 14
        inner_w = self.info_rect.width - 32
        if isinstance(obj, Potion):
            lines = [(obj.description, TEXT)]
            if obj.effect_text and obj.effect_text != obj.description:
                lines.append((obj.effect_text, (130, 235, 160)))
            cond = self._mana_cost_text(player, obj)
            if cond:
                lines.append((cond, (130, 180, 250)))
            for line, col in lines:
                for wrapped in self._wrap(line, inner_w):
                    draw_text(surface, self.font_small, wrapped, col, (x, y))
                    y += 19
        else:
            wp = obj
            self._stat_row(surface, x, y, inner_w, "DMG", str(wp.total_damage),
                           wp.total_damage / STAT_MAX["DMG"], (230, 80, 70))
            self._stat_row(surface, x, y + 20, inner_w, "SPD", f"{wp.attack_speed:.1f}/s",
                           wp.attack_speed / STAT_MAX["SPD"], (240, 190, 70))
            self._stat_row(surface, x, y + 40, inner_w, "RNG", f"{int(wp.range_px)}px",
                           wp.range_px / STAT_MAX["RNG"], (90, 190, 240))
            self._stat_row(surface, x, y + 60, inner_w, "CRIT", f"{int(wp.crit_chance * 100)}%",
                           wp.crit_chance / STAT_MAX["CRIT"], (200, 120, 240))
            y += 86
            extra = f"{wp.weapon_category}" + ("  (AoE)" if wp.area_radius > 0 else "")
            if wp.upgrade_level > 0:
                extra += f"   Upgrade +{wp.upgrade_level}"
            draw_text(surface, self.font_small, extra, TEXT_DIM, (x, y))
            y += 19
            cond = self._mana_cost_text(player, wp)
            if cond:
                draw_text(surface, self.font_small, cond, (130, 180, 250), (x, y))
                y += 19
            if self.selected_index == player.current_weapon_idx:
                draw_pill(surface, self.font_tiny, "EQUIPPED", EQUIPPED_GREEN,
                          (self.info_rect.right - 16, self.info_rect.y + 18), anchor="topright")

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

    def _render_buttons(self, surface, player, mouse):
        has_item = self._get_selected_item(player) is not None
        weapon = self._get_selected_weapon(player)
        can_equip = weapon is not None and self.selected_index != player.current_weapon_idx
        buttons = [
            Button("use", self.btn_use, "USE", "U", "good", enabled=has_item),
            Button("equip", self.btn_equip, "EQUIP", "", "primary", enabled=can_equip),
            Button("drop", self.btn_drop, "DROP", "G", "danger", enabled=has_item or weapon is not None),
            Button("close", self.btn_close, "CLOSE", "I"),
        ]
        pressed = pygame.mouse.get_pressed()[0]
        for b in buttons:
            b.draw(surface, self.font_medium, mouse, self.font_small, pressed)

    def _render_drop_selector(self, surface, player):
        item = self._get_selected_item(player)
        max_q = item.quantity if item else 1
        panel = self._drop_selector_panel().inflate(0, 12)
        draw_panel(surface, panel, alpha=250, border=(220, 120, 90), radius=8)

        mouse = pygame.mouse.get_pos()
        labels = {"minus": ("-", "normal"), "plus": ("+", "normal"),
                  "confirm": ("CONFIRM", "danger"), "cancel": ("CANCEL", "normal")}
        for action, rect in self._drop_selector_rects():
            label, style = labels[action]
            Button(action, rect, label, style=style).draw(surface, self.font_medium, mouse)

        cx = panel.centerx
        draw_text(surface, self.font_title, str(self.drop_amount), ACCENT, (cx, panel.y + 26), anchor="center")
        draw_text(surface, self.font_tiny, f"of {max_q}", TEXT_DIM, (cx, panel.y + 48), anchor="center")

    def _render_hover_tooltip(self, surface, player, mouse):
        kind, index = self.hover_slot
        obj = None
        if kind == "item" and index < len(player.inventory.items):
            obj = player.inventory.items[index]
        elif kind == "weapon" and index < len(player.inventory.weapons):
            obj = player.inventory.weapons[index]
        if obj is None:
            return

        color = self._get_rarity_color(obj)
        name = obj.display_name if isinstance(obj, Weapon) else obj.name
        lines: list[tuple[str, tuple]] = []
        desc = getattr(obj, "description", "")
        if desc:
            lines.append((desc[:42], TEXT))
        cond = self._mana_cost_text(player, obj)
        if isinstance(obj, Weapon):
            lines.append((f"DMG {obj.total_damage}   Range {int(obj.range_px)}px", (130, 235, 160)))
        elif getattr(obj, "effect_text", None) and obj.effect_text != desc and not cond:
            lines.append((obj.effect_text[:42], (130, 235, 160)))
        if cond:
            lines.append((cond[:42], (130, 180, 250)))
        lines.append(("Click to select, double-click to " + ("use" if kind == "item" else "equip"), TEXT_DIM))

        tt_w = 300
        tt_h = 40 + len(lines) * 18
        rect = pygame.Rect(min(SCREEN_WIDTH - tt_w - 8, mouse[0] + 16), min(SCREEN_HEIGHT - tt_h - 8, mouse[1] + 16),
                           tt_w, tt_h)
        draw_panel(surface, rect, alpha=245, border=color, radius=8)
        draw_text(surface, self.font_medium, name, color, (rect.x + 12, rect.y + 8))
        qty = getattr(obj, "quantity", 1)
        tag = self._get_rarity(obj) + (f"  x{qty}" if qty > 1 else "")
        draw_text(surface, self.font_tiny, tag, TEXT_DIM, (rect.right - 12, rect.y + 12), anchor="topright")
        y = rect.y + 36
        for text, col in lines:
            draw_text(surface, self.font_tiny, text, col, (rect.x + 12, y))
            y += 18
