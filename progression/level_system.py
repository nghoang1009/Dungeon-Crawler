import pygame
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_GOLD, COLOR_WHITE

class LevelSystem:
    """
    Action Roguelike Level Progression System:
    Level 1 -> 100 EXP
    Level 2 -> 250 EXP (150 diff)
    Level 3 -> 450 EXP (200 diff)
    Level 4 -> 700 EXP (250 diff)
    Supports safe carryover of excess EXP and multiple consecutive level ups.
    """
    LEVEL_THRESHOLDS = {
        1: 100,
        2: 250,
        3: 450,
        4: 700,
        5: 1000,
        6: 1350,
        7: 1750,
        8: 2200,
        9: 2700,
        10: 3300
    }

    @classmethod
    def get_required_exp(cls, level: int) -> int:
        if level in cls.LEVEL_THRESHOLDS:
            return cls.LEVEL_THRESHOLDS[level]
        # Formula beyond level 10: 3300 + (level - 10) * 700
        return 3300 + (level - 10) * 700

    @classmethod
    def add_exp(cls, player, amount: int) -> int:
        player.exp += amount
        level_ups = 0

        while True:
            req = cls.get_required_exp(player.level)
            if player.exp >= req:
                player.exp -= req
                player.level += 1
                level_ups += 1
            else:
                break

        return level_ups


class LevelUpModal:
    """
    Modal dialog overlay shown when Player levels up in Real-Time.
    Pauses gameplay (enemies don't move, no damage, no attacks) and prompts 4 stat choices:
    [1] +5 Max HP
    [2] +2 Attack
    [3] +1 Defense
    [4] +1 Speed
    """
    def __init__(self, font_huge: pygame.font.Font, font_title: pygame.font.Font, font_body: pygame.font.Font):
        self.font_huge = font_huge
        self.font_title = font_title
        self.font_body = font_body
        self.is_active = False
        self.pending_level_ups = 0
        self.selected_option = 0

        self.options = [
            ("[1] +5 Max HP", "Increases maximum health pool and heals +5 HP immediately."),
            ("[2] +2 Attack", "Increases weapon damage and special skill damage."),
            ("[3] +1 Defense", "Reduces all incoming enemy damage."),
            ("[4] +1 Speed", "Increases movement velocity and dash response.")
        ]

    def trigger_level_up(self, count: int = 1):
        self.pending_level_ups += count
        self.is_active = True
        self.selected_option = 0

    def option_rect(self, i: int) -> pygame.Rect:
        w, h = 560, 390
        x = (SCREEN_WIDTH - w) // 2
        y = (SCREEN_HEIGHT - h) // 2
        return pygame.Rect(x + 30, y + 145 + i * 50, w - 60, 42)

    def handle_input(self, event, player) -> bool:
        if not self.is_active:
            return False

        if event.type == pygame.MOUSEMOTION:
            for i in range(len(self.options)):
                if self.option_rect(i).collidepoint(event.pos):
                    self.selected_option = i
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i in range(len(self.options)):
                if self.option_rect(i).collidepoint(event.pos):
                    self.apply_upgrade(i, player)
                    break
            return True

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_w, pygame.K_UP):
                self.selected_option = (self.selected_option - 1) % len(self.options)
                return True
            elif event.key in (pygame.K_s, pygame.K_DOWN):
                self.selected_option = (self.selected_option + 1) % len(self.options)
                return True
            elif event.key == pygame.K_1:
                self.apply_upgrade(0, player)
                return True
            elif event.key == pygame.K_2:
                self.apply_upgrade(1, player)
                return True
            elif event.key == pygame.K_3:
                self.apply_upgrade(2, player)
                return True
            elif event.key == pygame.K_4:
                self.apply_upgrade(3, player)
                return True
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_e):
                self.apply_upgrade(self.selected_option, player)
                return True

        return True

    def apply_upgrade(self, option_idx: int, player):
        if option_idx == 0:
            player.max_hp += 5
            player.current_hp += 5
        elif option_idx == 1:
            player.attack_power += 2
        elif option_idx == 2:
            player.defense += 1
        elif option_idx == 3:
            player.speed += 8.0

        self.pending_level_ups -= 1
        if self.pending_level_ups <= 0:
            self.is_active = False

    def render(self, surface: pygame.Surface, player):
        if not self.is_active:
            return

        dim_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim_surf.fill((10, 8, 16, 215))
        surface.blit(dim_surf, (0, 0))

        w, h = 560, 390
        x = (SCREEN_WIDTH - w) // 2
        y = (SCREEN_HEIGHT - h) // 2

        pygame.draw.rect(surface, (25, 22, 35), (x, y, w, h), border_radius=8)
        pygame.draw.rect(surface, COLOR_GOLD, (x, y, w, h), width=2, border_radius=8)

        t_lvl = self.font_huge.render("LEVEL UP!", True, (255, 220, 80))
        surface.blit(t_lvl, (x + (w - t_lvl.get_width()) // 2, y + 20))

        sub_txt = self.font_title.render(f"Hero Reached Level {player.level}", True, (200, 200, 240))
        surface.blit(sub_txt, (x + (w - sub_txt.get_width()) // 2, y + 75))

        inst_txt = self.font_body.render("Choose an upgrade:", True, (180, 180, 200))
        surface.blit(inst_txt, (x + (w - inst_txt.get_width()) // 2, y + 110))

        opt_y = y + 145
        mouse = pygame.mouse.get_pos()
        for i, (title, desc) in enumerate(self.options):
            if self.option_rect(i).collidepoint(mouse):
                self.selected_option = i
            is_sel = (i == self.selected_option)
            bg_col = (45, 40, 65) if is_sel else (32, 28, 44)
            border_col = COLOR_GOLD if is_sel else (70, 65, 85)

            opt_rect = pygame.Rect(x + 30, opt_y, w - 60, 42)
            pygame.draw.rect(surface, bg_col, opt_rect, border_radius=4)
            pygame.draw.rect(surface, border_col, opt_rect, width=2 if is_sel else 1, border_radius=4)

            t_col = (255, 255, 120) if is_sel else COLOR_WHITE
            t_txt = self.font_title.render(title, True, t_col)
            surface.blit(t_txt, (x + 45, opt_y + 8))

            opt_y += 50

        footer_txt = self.font_body.render("Click an upgrade, or [1-4] / [W/S] + [ENTER]", True, (160, 160, 180))
        surface.blit(footer_txt, (x + (w - footer_txt.get_width()) // 2, y + h - 28))
