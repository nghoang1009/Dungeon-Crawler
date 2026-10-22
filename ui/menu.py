import os
import random
import time
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_WHITE, COLOR_GOLD, DIFFICULTY_EASY,
    DIFFICULTY_NORMAL, DIFFICULTY_HARD
)
from entities.class_data import AVAILABLE_CLASSES, ClassData
from core.save_manager import SaveManager
from ui.widgets import Button, button_at
from ui.theme import draw_text

CX = SCREEN_WIDTH // 2
CARD_W, CARD_H, CARD_GAP, CARD_Y = 260, 380, 30, 190

class MenuState:
    MAIN_MENU = "MAIN_MENU"
    CLASS_SELECT = "CLASS_SELECT"
    RUN_CONFIG = "RUN_CONFIG"
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    GAME_OVER = "GAME_OVER"
    VICTORY = "VICTORY"
    RUN_COMPLETE = "RUN_COMPLETE"


class MenuManager:
    """
    Renders Main Menu, Class Selection, Pause Menu, Game Over, Floor Victory, and Run Complete screens.
    """
    def __init__(self, font_huge: pygame.font.Font, font_title: pygame.font.Font, font_body: pygame.font.Font):
        self.font_huge = font_huge
        self.font_title = font_title
        self.font_body = font_body

        self.selected_difficulty = DIFFICULTY_NORMAL
        self.difficulties = [DIFFICULTY_EASY, DIFFICULTY_NORMAL, DIFFICULTY_HARD]
        self.diff_idx = 1

        self.selected_class_idx = 0

        # Run configuration (character creation): name + dungeon seed
        self.player_name = ""
        self.seed_input = ""          # Typed seed (digits), empty = random
        self.active_field = "name"    # "name" | "seed"
        self.randomized_seed = None   # Preview seed produced by [R] Random Seed

        self.music_on = True          # Mirrors MusicManager.enabled (for the pause-menu label)
        self.notice = ""              # Short feedback line (e.g. "Game saved")
        self._notice_until = 0.0

    # ----------------------------------------------------------- mouse layout
    def show_notice(self, text: str, seconds: float = 2.0):
        self.notice = text
        self._notice_until = time.perf_counter() + seconds

    def card_rect(self, idx: int) -> pygame.Rect:
        total_w = len(AVAILABLE_CLASSES) * CARD_W + (len(AVAILABLE_CLASSES) - 1) * CARD_GAP
        return pygame.Rect((SCREEN_WIDTH - total_w) // 2 + idx * (CARD_W + CARD_GAP), CARD_Y, CARD_W, CARD_H)

    @property
    def name_box(self) -> pygame.Rect:
        return pygame.Rect(CX - 220, 266, 440, 44)

    @property
    def seed_box(self) -> pygame.Rect:
        return pygame.Rect(CX - 220, 356, 300, 44)

    def buttons_for(self, state: str, floor: int = 1) -> list[Button]:
        """Clickable buttons of a screen. `action` strings are handled by Game._menu_action."""
        def btn(action, y, label, hint="", style="normal", w=320, x=None, enabled=True, h=46):
            return Button(action, pygame.Rect((CX - w // 2) if x is None else x, y, w, h), label, hint, style, enabled)

        if state == MenuState.MAIN_MENU:
            return [
                btn("play", 285, "PLAY", "ENTER", "primary"),
                btn("load", 341, "LOAD GAME", "L", enabled=os.path.exists(SaveManager.SAVE_FILE)),
                btn("difficulty", 397, f"Difficulty: {self.selected_difficulty}", "T"),
                btn("quit", 453, "QUIT", style="danger"),
            ]
        if state == MenuState.CLASS_SELECT:
            return [
                btn("back", 650, "BACK", "ESC", w=170, x=CX - 180),
                btn("confirm_class", 650, f"START AS {self.current_class.name.upper()}", "ENTER", "primary", w=300, x=CX + 10),
            ]
        if state == MenuState.RUN_CONFIG:
            return [
                Button("random", pygame.Rect(self.seed_box.right + 14, self.seed_box.y, 126, 44), "Random", "R", "good"),
                btn("back", 455, "BACK", "ESC", w=170, x=CX - 190),
                btn("start_run", 455, "START RUN", "ENTER", "primary", w=260, x=CX + 0),
            ]
        if state == MenuState.PAUSED:
            y = SCREEN_HEIGHT // 2 - 20
            return [
                btn("resume", y, "RESUME", "P", "primary"),
                btn("save", y + 58, "SAVE GAME", "S"),
                btn("music", y + 116, f"MUSIC: {'ON' if self.music_on else 'OFF'}", "N"),
                btn("main_menu", y + 174, "MAIN MENU", "M", "danger"),
            ]
        if state == MenuState.GAME_OVER:
            y = SCREEN_HEIGHT // 2 + 70
            return [
                btn("restart", y, "RESTART DUNGEON", "R", "primary"),
                btn("main_menu", y + 58, "MAIN MENU", "M"),
            ]
        if state == MenuState.VICTORY:
            if floor >= 10:
                return [btn("main_menu", SCREEN_HEIGHT // 2 + 150, "MAIN MENU", "ENTER", "primary")]
            y = SCREEN_HEIGHT // 2 + 70
            return [
                btn("next_floor", y, f"GO TO FLOOR {floor + 1}", "ENTER", "primary"),
                btn("main_menu", y + 58, "MAIN MENU", "M"),
            ]
        return []

    def hotspots_for(self, state: str) -> list[tuple[str, pygame.Rect]]:
        """Clickable areas that are not buttons (class cards, text fields)."""
        if state == MenuState.CLASS_SELECT:
            return [(f"class:{i}", self.card_rect(i)) for i in range(len(AVAILABLE_CLASSES))]
        if state == MenuState.RUN_CONFIG:
            return [("field:name", self.name_box), ("field:seed", self.seed_box)]
        return []

    def click(self, state: str, pos, floor: int = 1) -> str | None:
        """Returns the action under `pos` (buttons first, then hotspots) or None."""
        hit = button_at(self.buttons_for(state, floor), pos)
        if hit:
            return hit.action
        for action, rect in self.hotspots_for(state):
            if rect.collidepoint(pos):
                return action
        return None

    def _draw_buttons(self, surface: pygame.Surface, state: str, floor: int = 1):
        mouse = pygame.mouse.get_pos()
        pressed = pygame.mouse.get_pressed()[0]
        for b in self.buttons_for(state, floor):
            b.draw(surface, self.font_title if b.rect.height >= 44 and b.rect.width > 150 else self.font_body,
                   mouse, self.font_body, pressed)

    def _wrap(self, text: str, max_width: int) -> list[str]:
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if line and self.font_body.size(trial)[0] > max_width:
                lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
        return lines

    def _draw_notice(self, surface: pygame.Surface, y: int):
        if self.notice and time.perf_counter() < self._notice_until:
            draw_text(surface, self.font_body, self.notice, (120, 240, 160), (CX, y), anchor="midtop")

    def cycle_difficulty(self):
        self.diff_idx = (self.diff_idx + 1) % len(self.difficulties)
        self.selected_difficulty = self.difficulties[self.diff_idx]

    def cycle_class(self, direction: int = 1):
        self.selected_class_idx = (self.selected_class_idx + direction) % len(AVAILABLE_CLASSES)

    @property
    def current_class(self) -> ClassData:
        return AVAILABLE_CLASSES[self.selected_class_idx]

    # ------------------------------------------------------------ run config
    def reset_run_config(self):
        self.player_name = ""
        self.seed_input = ""
        self.active_field = "name"
        self.randomized_seed = None

    def get_configured_seed(self) -> int | None:
        """Typed seed wins; otherwise the [R] random preview; None = fully random."""
        if self.seed_input.strip().isdigit():
            return int(self.seed_input.strip())
        return self.randomized_seed

    def randomize_seed(self):
        self.randomized_seed = random.randint(100000, 999999)
        self.seed_input = ""

    def append_char(self, ch: str):
        if self.active_field == "name" and len(self.player_name) < 14 and (ch.isalnum() or ch in " _-"):
            self.player_name += ch
        elif self.active_field == "seed" and ch.isdigit() and len(self.seed_input) < 9:
            self.seed_input += ch

    def backspace(self):
        if self.active_field == "name" and self.player_name:
            self.player_name = self.player_name[:-1]
        elif self.active_field == "seed" and self.seed_input:
            self.seed_input = self.seed_input[:-1]

    def render_run_config(self, surface: pygame.Surface):
        surface.fill((15, 12, 22))

        cls = self.current_class
        header = self.font_huge.render("NEW RUN SETUP", True, COLOR_GOLD)
        surface.blit(header, ((SCREEN_WIDTH - header.get_width()) // 2, 70))

        sub = self.font_title.render(f"Class: {cls.name}  (ESC to re-pick)", True, cls.color)
        surface.blit(sub, ((SCREEN_WIDTH - sub.get_width()) // 2, 140))

        # Name field
        name_active = self.active_field == "name"
        name_label = self.font_body.render("Character Name:", True, (190, 190, 205))
        surface.blit(name_label, (SCREEN_WIDTH // 2 - 220, 240))
        name_box = self.name_box
        pygame.draw.rect(surface, (28, 25, 40), name_box, border_radius=6)
        pygame.draw.rect(surface, cls.color if name_active else (80, 75, 100),
                         name_box, width=2 if name_active else 1, border_radius=6)
        name_txt = self.font_title.render(self.player_name + ("_" if name_active else ""), True, COLOR_WHITE)
        surface.blit(name_txt, (name_box.x + 12, name_box.y + 8))
        if not self.player_name and not name_active:
            hint = self.font_body.render("(empty = Hero)", True, (110, 105, 130))
            surface.blit(hint, (name_box.x + 12, name_box.y + 12))

        # Seed field
        seed_active = self.active_field == "seed"
        seed_label = self.font_body.render("Dungeon Seed:", True, (190, 190, 205))
        surface.blit(seed_label, (SCREEN_WIDTH // 2 - 220, 330))
        seed_box = self.seed_box
        pygame.draw.rect(surface, (28, 25, 40), seed_box, border_radius=6)
        pygame.draw.rect(surface, (250, 210, 90) if seed_active else (80, 75, 100),
                         seed_box, width=2 if seed_active else 1, border_radius=6)
        seed_txt = self.font_title.render(self.seed_input + ("_" if seed_active else ""), True, (250, 220, 120))
        surface.blit(seed_txt, (seed_box.x + 12, seed_box.y + 8))

        # Effective seed preview
        configured = self.get_configured_seed()
        if configured is not None:
            preview = self.font_body.render(f"Seed to use: {configured}  (same seed = same dungeon)",
                                            True, (120, 220, 250))
        else:
            preview = self.font_body.render("Seed to use: RANDOM (generated at start)", True, (150, 150, 175))
        surface.blit(preview, (SCREEN_WIDTH // 2 - 220, 414))

        instr = self.font_body.render("Click a field to type   [TAB] Switch Field", True, (190, 190, 210))
        surface.blit(instr, ((SCREEN_WIDTH - instr.get_width()) // 2, 525))
        tip = self.font_body.render("Tip: leave Seed empty for a fresh random dungeon each run", True, (130, 130, 150))
        surface.blit(tip, ((SCREEN_WIDTH - tip.get_width()) // 2, 555))

        self._draw_buttons(surface, MenuState.RUN_CONFIG)

    def render_main_menu(self, surface: pygame.Surface, seed: int):
        surface.fill((15, 12, 22))

        # Title
        title_txt = self.font_huge.render("DUNGEON CRAWLER", True, (240, 70, 60))
        surface.blit(title_txt, ((SCREEN_WIDTH - title_txt.get_width()) // 2, 130))

        sub_txt = self.font_title.render("10 Floors of Roguelike Peril", True, (200, 190, 220))
        surface.blit(sub_txt, ((SCREEN_WIDTH - sub_txt.get_width()) // 2, 205))

        seed_str = f"Dungeon Seed: {seed}"
        seed_txt = self.font_body.render(seed_str, True, (160, 160, 180))
        surface.blit(seed_txt, ((SCREEN_WIDTH - seed_txt.get_width()) // 2, 245))

        self._draw_buttons(surface, MenuState.MAIN_MENU)

        # Controls list
        ctrls = [
            "WASD / Arrows : Move & Slide",
            "Left Click / K : Attack (Melee Cleave / Ranged Projectile)",
            "SPACE : Dash Dodge (Invulnerability i-frames)",
            "Q or 1 : Quick Health Potion",
            "I : Inventory & Equipment",
            "E : Interact (Chests, NPCs, Gates)",
            "F : Class Special Ability",
            "N : Toggle Music",
            "F3 : Algorithm Debug Overlay"
        ]
        y_c = 530
        for c in ctrls:
            t = self.font_body.render(c, True, (140, 140, 160))
            surface.blit(t, ((SCREEN_WIDTH - t.get_width()) // 2, y_c))
            y_c += 22

    def render_class_select(self, surface: pygame.Surface):
        surface.fill((15, 12, 22))

        header = self.font_huge.render("CHOOSE YOUR HERO", True, COLOR_GOLD)
        surface.blit(header, ((SCREEN_WIDTH - header.get_width()) // 2, 60))

        sub = self.font_title.render("Select class to enter the 10-Floor Dungeon", True, (180, 180, 200))
        surface.blit(sub, ((SCREEN_WIDTH - sub.get_width()) // 2, 125))

        card_w, card_h, card_y = CARD_W, CARD_H, CARD_Y
        mouse = pygame.mouse.get_pos()

        for idx, c_data in enumerate(AVAILABLE_CLASSES):
            card_rect = self.card_rect(idx)
            x = card_rect.x
            is_selected = (idx == self.selected_class_idx)
            hovered = card_rect.collidepoint(mouse)

            bg_col = (30, 28, 42) if not is_selected else (45, 40, 65)
            if hovered and not is_selected:
                bg_col = (38, 35, 54)
            border_col = c_data.color if is_selected else ((110, 100, 140) if hovered else (70, 65, 85))
            border_w = 3 if is_selected else (2 if hovered else 1)

            pygame.draw.rect(surface, bg_col, card_rect, border_radius=8)
            pygame.draw.rect(surface, border_col, card_rect, width=border_w, border_radius=8)

            # Class Name
            name_txt = self.font_title.render(c_data.name.upper(), True, c_data.color)
            surface.blit(name_txt, (x + (card_w - name_txt.get_width()) // 2, card_y + 20))

            # Stat Bars
            stats = [
                ("HP", c_data.max_hp, 160, (230, 50, 50)),
                ("ATTACK", c_data.attack, 30, (255, 180, 50)),
                ("DEFENSE", c_data.defense, 10, (100, 180, 255)),
                ("SPEED", int(c_data.speed), 180, (50, 220, 100))
            ]

            sy = card_y + 75
            for label, val, max_val, bar_col in stats:
                lbl_t = self.font_body.render(label, True, (190, 190, 200))
                surface.blit(lbl_t, (x + 20, sy))

                bar_x = x + 100
                bar_w = 135
                bar_h = 10
                pct = max(0.0, min(1.0, val / max_val))
                pygame.draw.rect(surface, (20, 20, 25), (bar_x, sy + 3, bar_w, bar_h), border_radius=2)
                pygame.draw.rect(surface, bar_col, (bar_x, sy + 3, int(bar_w * pct), bar_h), border_radius=2)
                sy += 28

            # Starter Weapon
            starter_wp = c_data.create_starter_weapon()
            wp_tag = self.font_body.render(f"Wpn: {starter_wp.name}", True, COLOR_WHITE)
            surface.blit(wp_tag, (x + 20, sy + 15))

            # Description
            dy = sy + 48
            for line in self._wrap(c_data.description, card_w - 40):
                dt = self.font_body.render(line, True, (160, 160, 180))
                surface.blit(dt, (x + 20, dy))
                dy += 18

            if is_selected:
                sel_tag = self.font_title.render("SELECTED", True, (255, 230, 80))
                surface.blit(sel_tag, (x + (card_w - sel_tag.get_width()) // 2, card_y + card_h - 40))

        instr = self.font_body.render("Click a hero to choose   [A/D] or [Left/Right]   Double-click to start", True, (200, 200, 220))
        surface.blit(instr, ((SCREEN_WIDTH - instr.get_width()) // 2, 600))

        self._draw_buttons(surface, MenuState.CLASS_SELECT)

    def render_pause_menu(self, surface: pygame.Surface):
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 180))
        surface.blit(dim, (0, 0))

        t = self.font_huge.render("GAME PAUSED", True, COLOR_WHITE)
        surface.blit(t, ((SCREEN_WIDTH - t.get_width()) // 2, SCREEN_HEIGHT // 2 - 130))

        self._draw_buttons(surface, MenuState.PAUSED)
        self._draw_notice(surface, SCREEN_HEIGHT // 2 + 238)

    def render_game_over(self, surface: pygame.Surface, player=None, floor: int = 1):
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((40, 5, 5, 225))
        surface.blit(dim, (0, 0))

        t = self.font_huge.render("YOU DIED", True, (240, 40, 40))
        surface.blit(t, ((SCREEN_WIDTH - t.get_width()) // 2, SCREEN_HEIGHT // 2 - 120))

        f_txt = self.font_title.render(f"Fell on Floor {floor} / 10", True, (220, 180, 180))
        surface.blit(f_txt, ((SCREEN_WIDTH - f_txt.get_width()) // 2, SCREEN_HEIGHT // 2 - 50))

        if player:
            s_txt = self.font_body.render(f"Final Score: {player.score}   |   Enemies Defeated: {player.enemies_killed}", True, COLOR_GOLD)
            surface.blit(s_txt, ((SCREEN_WIDTH - s_txt.get_width()) // 2, SCREEN_HEIGHT // 2 - 10))

        self._draw_buttons(surface, MenuState.GAME_OVER)

    def render_victory(self, surface: pygame.Surface, dungeon_level: int, player=None):
        dim = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim.fill((5, 30, 20, 225))
        surface.blit(dim, (0, 0))

        if dungeon_level >= 10:
            # RUN COMPLETE - FINAL VICTORY SCREEN
            t = self.font_huge.render("RUN COMPLETED - VICTORY!", True, (60, 255, 140))
            surface.blit(t, ((SCREEN_WIDTH - t.get_width()) // 2, SCREEN_HEIGHT // 2 - 150))

            sub = self.font_title.render("You have conquered all 10 Floors of the Dungeon!", True, COLOR_GOLD)
            surface.blit(sub, ((SCREEN_WIDTH - sub.get_width()) // 2, SCREEN_HEIGHT // 2 - 85))

            if player:
                mins = int(player.run_time // 60)
                secs = int(player.run_time % 60)
                stats = [
                    f"FINAL SCORE: {player.score:06d}",
                    "FLOORS REACHED: 10 / 10",
                    f"ENEMIES DEFEATED: {player.enemies_killed}",
                    f"BOSSES DEFEATED: {player.bosses_killed}",
                    f"TOTAL TIME: {mins:02d}:{secs:02d}"
                ]
                sy = SCREEN_HEIGHT // 2 - 30
                for s in stats:
                    st = self.font_body.render(s, True, COLOR_WHITE)
                    surface.blit(st, ((SCREEN_WIDTH - st.get_width()) // 2, sy))
                    sy += 26

            self._draw_buttons(surface, MenuState.VICTORY, dungeon_level)

        else:
            # INTERMEDIATE FLOOR TRANSITION
            t = self.font_huge.render("FLOOR CLEARED!", True, (60, 240, 140))
            surface.blit(t, ((SCREEN_WIDTH - t.get_width()) // 2, SCREEN_HEIGHT // 2 - 90))

            info = self.font_title.render(f"Floor {dungeon_level} Boss Defeated!", True, COLOR_GOLD)
            surface.blit(info, ((SCREEN_WIDTH - info.get_width()) // 2, SCREEN_HEIGHT // 2 - 10))

            self._draw_buttons(surface, MenuState.VICTORY, dungeon_level)
