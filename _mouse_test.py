"""Mouse-driven menus: every screen can be operated by clicking (headless, synthetic mouse events)."""
import sys, tempfile, os
sys.stdout.reconfigure(encoding="utf-8")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
SAVE = os.path.join(tempfile.gettempdir(), "dungeon_mouse_test_save.json")
os.environ["DUNGEON_SAVE_FILE"] = SAVE
if os.path.exists(SAVE):
    os.remove(SAVE)

import pygame

pygame.init()
pygame.display.set_mode((1024, 768))

from core.game import Game
from ui.menu import MenuState

fails = []
def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        fails.append(name)

game = Game()
mm = game.menu_manager

def click(pos):
    pygame.event.clear()
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1))
    game.handle_events()
    game.draw()

def click_button(action, state=None, floor=1):
    state = state or game.game_state
    for b in mm.buttons_for(state, floor):
        if b.action == action:
            click(b.rect.center)
            return
    raise AssertionError(f"no button {action} on {state}")

# ---- main menu -> class select -> run config -> play
game.draw()
check("Bắt đầu ở menu chính", game.game_state == MenuState.MAIN_MENU)
d0 = mm.selected_difficulty
click_button("difficulty")
check("Click Difficulty đổi độ khó", mm.selected_difficulty != d0)
click_button("play")
check("Click PLAY -> chọn hero", game.game_state == MenuState.CLASS_SELECT)

click(mm.card_rect(2).center)
check("Click thẻ Mage chọn Mage", mm.selected_class_idx == 2 and game.game_state == MenuState.CLASS_SELECT)
click(mm.card_rect(0).center)
check("Click thẻ Knight chọn Knight", mm.selected_class_idx == 0)
click_button("back")
check("Click BACK về menu chính", game.game_state == MenuState.MAIN_MENU)
click_button("play")
click(mm.card_rect(1).center)
click(mm.card_rect(1).center)   # double-click
check("Double-click thẻ -> màn tạo run", game.game_state == MenuState.RUN_CONFIG and mm.selected_class_idx == 1)

click(mm.seed_box.center)
check("Click ô Seed focus seed", mm.active_field == "seed")
click(mm.name_box.center)
check("Click ô Name focus name", mm.active_field == "name")
click_button("random")
check("Click Random tạo seed", mm.get_configured_seed() is not None)
click_button("start_run")
check("Click START RUN vào game", game.game_state == MenuState.PLAYING and game.player is not None)

# ---- toolbar + pause menu
game.player.max_hp = game.player.current_hp = 10 ** 9
tb = {b.action: b for b in game.hud.toolbar_buttons()}
click(tb["inventory"].rect.center)
check("Click BAG mở túi đồ", game.inventory_ui.is_open)
game.inventory_ui.close()
vis = game.minimap.visible
click(tb["map"].rect.center)
check("Click MAP ẩn/hiện minimap", game.minimap.visible != vis)
count_before = game.player.current_weapon.cooldown
click(tb["pause"].rect.center)
check("Click PAUSE tạm dừng", game.game_state == MenuState.PAUSED)
click_button("save")
check("Click SAVE ghi file", os.path.exists(SAVE))
click_button("resume")
check("Click RESUME chơi tiếp", game.game_state == MenuState.PLAYING)
game.game_state = MenuState.PAUSED
click_button("main_menu")
check("Click MAIN MENU từ pause", game.game_state == MenuState.MAIN_MENU)
click_button("load")
check("Click LOAD GAME tải save", game.game_state == MenuState.PLAYING and game.player is not None)

# ---- inventory: select, double-click to use, close with X
from items.potion import Potion, PotionType
game.player.inventory.add_item(Potion(PotionType.HEALTH))
game.player.current_hp = 10
hp_idx = next(i for i, it in enumerate(game.player.inventory.items)
              if isinstance(it, Potion) and it.potion_type == PotionType.HEALTH)
game.inventory_ui.open_ui()
game.draw()
click(game.inventory_ui.slot_rects[hp_idx].center)
check("Click ô đồ để chọn", game.inventory_ui.selected_index == hp_idx)
pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, pos=game.inventory_ui.slot_rects[hp_idx].center, button=1))
game.handle_events()
hp_before = game.player.current_hp
click(game.inventory_ui.slot_rects[hp_idx].center)
check("Double-click bình thuốc để dùng", game.player.current_hp > hp_before)
game.inventory_ui.drag_index = None
click(game.inventory_ui.btn_x.center)
check("Click X đóng túi đồ", not game.inventory_ui.is_open)

# ---- level up modal
game.player.max_hp = game.player.current_hp = 10 ** 9
atk = game.player.attack_power
game.level_up_modal.trigger_level_up(1)
game.draw()
click(game.level_up_modal.option_rect(1).center)
check("Click lựa chọn level up (+2 Attack)", game.player.attack_power == atk + 2 and not game.level_up_modal.is_active)

# ---- NPC modal
from entities.npc import NPC, NPCStyle
npc = NPC(game.player.grid_x, game.player.grid_y, npc_type=NPCStyle.MERCHANT)
game.npc_modal.open_npc(npc)
game.player.gold = 500
game.draw()
gold = game.player.gold
click(game.npc_modal.trade_rect(0).center)
check("Click món hàng để mua", game.player.gold != gold or "" != game.npc_modal.status_msg, game.npc_modal.status_msg)
click(game.npc_modal.close_button().rect.center)
check("Click X đóng cửa hàng", not game.npc_modal.is_active)

# ---- game over / victory
game.game_state = MenuState.GAME_OVER
game.draw()
click_button("restart")
check("Click RESTART chơi lại", game.game_state == MenuState.PLAYING and game.current_floor == 1)

game.game_state = MenuState.VICTORY
game.current_floor = 3
game.draw()
click_button("next_floor", floor=3)
check("Click GO TO FLOOR sang tầng sau", game.game_state == MenuState.PLAYING and game.current_floor == 4)

game.game_state = MenuState.VICTORY
game.current_floor = 10
game.draw()
click_button("main_menu", floor=10)
check("Click MAIN MENU sau khi thắng", game.game_state == MenuState.MAIN_MENU)

click_button("quit")
check("Click QUIT thoát game", game.is_running is False)

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
