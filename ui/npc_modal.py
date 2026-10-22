import pygame
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, COLOR_GOLD, COLOR_WHITE
from ui.widgets import Button

class NPCModal:
    """
    Interactive Trading UI Modal opened when pressing [E] near Blacksmith, Merchant, Healer, Relic Trader, or Rescued NPC.
    Displays stock quantities, handles SOLD OUT state, and enforces gold transactions.
    """
    def __init__(self, font_huge: pygame.font.Font, font_title: pygame.font.Font, font_body: pygame.font.Font):
        self.font_huge = font_huge
        self.font_title = font_title
        self.font_body = font_body
        self.is_active = False
        self.current_npc = None
        self.selected_idx = 0
        self.status_msg = ""
        self.status_timer = 0.0

    def open_npc(self, npc):
        self.current_npc = npc
        self.is_active = True
        self.selected_idx = 0
        self.status_msg = ""

    def close(self):
        self.is_active = False
        self.current_npc = None

    # ------------------------------------------------------------------ mouse layout
    MODAL_W, MODAL_H = 600, 440

    def _origin(self) -> tuple[int, int]:
        return (SCREEN_WIDTH - self.MODAL_W) // 2, (SCREEN_HEIGHT - self.MODAL_H) // 2

    def trade_rect(self, i: int) -> pygame.Rect:
        x, y = self._origin()
        return pygame.Rect(x + 25, y + 95 + i * 54, self.MODAL_W - 50, 42)

    def close_button(self) -> Button:
        x, y = self._origin()
        return Button("close", pygame.Rect(x + self.MODAL_W - 40, y + 14, 28, 28), "X", style="danger")

    def _do_trade(self, choice: int, player, sound_manager=None):
        success, msg = self.current_npc.execute_trade(choice, player)
        self.status_msg = msg
        self.status_timer = 2.0
        if success and sound_manager:
            sound_manager.play("potion")

    def handle_input(self, event, player, sound_manager=None) -> bool:
        if not self.is_active or not self.current_npc:
            return False

        if event.type == pygame.MOUSEMOTION:
            for i in range(len(self.current_npc.trades)):
                if self.trade_rect(i).collidepoint(event.pos):
                    self.selected_idx = i
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.close_button().hovered(event.pos):
                self.close()
                return True
            for i in range(len(self.current_npc.trades)):
                if self.trade_rect(i).collidepoint(event.pos):
                    self.selected_idx = i
                    self._do_trade(i, player, sound_manager)
                    break
            return True

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_e):
                self.close()
                return True
            elif event.key in (pygame.K_w, pygame.K_UP):
                self.selected_idx = (self.selected_idx - 1) % len(self.current_npc.trades)
                return True
            elif event.key in (pygame.K_s, pygame.K_DOWN):
                self.selected_idx = (self.selected_idx + 1) % len(self.current_npc.trades)
                return True
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                choice = self.selected_idx
                if event.key == pygame.K_1: choice = 0
                elif event.key == pygame.K_2: choice = 1
                elif event.key == pygame.K_3: choice = 2
                elif event.key == pygame.K_4: choice = 3

                self._do_trade(choice, player, sound_manager)
                return True

        return True

    def render(self, surface: pygame.Surface, player):
        if not self.is_active or not self.current_npc:
            return

        dim_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        dim_surf.fill((10, 8, 16, 215))
        surface.blit(dim_surf, (0, 0))

        w, h = 600, 440
        x = (SCREEN_WIDTH - w) // 2
        y = (SCREEN_HEIGHT - h) // 2

        pygame.draw.rect(surface, (25, 22, 35), (x, y, w, h), border_radius=8)
        pygame.draw.rect(surface, self.current_npc.color, (x, y, w, h), width=2, border_radius=8)

        # Header NPC Name
        t_name = self.font_title.render(self.current_npc.name.upper(), True, self.current_npc.color)
        surface.blit(t_name, (x + 25, y + 20))

        gold_t = self.font_title.render(f"Your Gold: {player.gold} G", True, COLOR_GOLD)
        surface.blit(gold_t, (x + w - gold_t.get_width() - 60, y + 20))
        self.close_button().draw(surface, self.font_body, pygame.mouse.get_pos())
        mouse = pygame.mouse.get_pos()

        # Dialogue
        d_txt = self.font_body.render(f'"{self.current_npc.dialogue}"', True, (190, 190, 210))
        surface.blit(d_txt, (x + 25, y + 55))

        # Trades list
        ty = y + 95
        for i, trade in enumerate(self.current_npc.trades):
            if self.trade_rect(i).collidepoint(mouse):
                self.selected_idx = i
            is_sel = (i == self.selected_idx)
            is_sold = trade.is_sold_out
            bg_col = (45, 40, 65) if is_sel else (32, 28, 44)
            border_col = COLOR_GOLD if is_sel else (70, 65, 85)

            opt_rect = pygame.Rect(x + 25, ty, w - 50, 42)
            pygame.draw.rect(surface, bg_col, opt_rect, border_radius=4)
            pygame.draw.rect(surface, border_col, opt_rect, width=2 if is_sel else 1, border_radius=4)

            # Left Label & Stock
            if is_sold:
                lbl_t = self.font_body.render(f"[{i+1}] {trade.text} (SOLD OUT)", True, (120, 120, 130))
            else:
                stock_tag = f" (x{trade.stock})" if trade.cost_gold > 0 else ""
                txt_col = (255, 255, 120) if is_sel else COLOR_WHITE
                lbl_t = self.font_body.render(f"[{i+1}] {trade.text}{stock_tag}", True, txt_col)
            surface.blit(lbl_t, (x + 38, ty + 10))

            # Right Cost
            if is_sold:
                cost_t = self.font_title.render("SOLD OUT", True, (140, 80, 80))
            else:
                cost_col = COLOR_GOLD if player.gold >= trade.cost_gold else (220, 50, 50)
                cost_label = f"{trade.cost_gold} G" if trade.cost_gold > 0 else "FREE"
                cost_t = self.font_title.render(cost_label, True, cost_col)
            surface.blit(cost_t, (x + w - cost_t.get_width() - 40, ty + 8))

            ty += 54

        # Status feedback message
        if self.status_msg:
            msg_col = (100, 240, 140) if "successful" in self.status_msg.lower() or "restor" in self.status_msg.lower() or "free" in self.status_msg.lower() else (240, 90, 90)
            st_t = self.font_body.render(self.status_msg, True, msg_col)
            surface.blit(st_t, (x + (w - st_t.get_width()) // 2, y + h - 50))

        foot_t = self.font_body.render("Click an offer to trade   [1-4] / [ENTER]   [E/ESC] Close", True, (160, 160, 180))
        surface.blit(foot_t, (x + (w - foot_t.get_width()) // 2, y + h - 25))
