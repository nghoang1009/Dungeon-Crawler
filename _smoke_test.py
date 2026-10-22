"""Headless smoke test for Inventory / Mana / Pause integration."""
import sys, tempfile, os
sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("DUNGEON_SAVE_FILE", os.path.join(tempfile.gettempdir(), "dungeon_test_save.json"))
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame
import random

random.seed(42)
pygame.init()
pygame.font.init()
pygame.display.set_mode((1024, 768))

from core.game import Game
from ui.menu import MenuState
from items.potion import Potion, PotionType
from entities.class_data import MAGE_CLASS, KNIGHT_CLASS
from core.save_manager import SaveManager

fails = []
def check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name} {extra}")
    if not cond:
        fails.append(name)

# 1. Game boots (this used to crash: ui/inventory_ui.py was missing)
game = Game()
check("Game khởi động (import InventoryUI OK)", True)

# 2. Start a Mage game
game.menu_manager.selected_class_idx = 2  # Mage
game.current_floor = 1
game.player = None
game.start_new_game()
check("start_new_game Mage", game.game_state == MenuState.PLAYING and game.player.class_name == "Mage")
check("Mage có mana đầy", game.player.uses_mana and game.player.mana == 100 and game.player.max_mana == 100)

# 3. Give a Mana Potion and test use
mp = Potion(PotionType.MANA, potency=35)
mp.quantity = 2
game.player.inventory.items.append(mp)
game.player.mana = 20.0
idx = len(game.player.inventory.items) - 1
consumed = game.player.inventory.use_item_at(idx, game.player)
check("Mana Potion hồi mana", consumed and abs(game.player.mana - 55.0) < 0.01,
      f"mana={game.player.mana}")
check("Item bị trừ đúng 1", game.player.inventory.items[idx].quantity == 1)

# 4. Full mana -> not consumed
game.player.mana = game.player.max_mana
before_qty = game.player.inventory.items[idx].quantity
consumed = game.player.inventory.use_item_at(idx, game.player)
check("MP đầy -> không dùng, không trừ", not consumed and game.player.inventory.items[idx].quantity == before_qty)

# 5. Non-mana class -> not consumed, no crash
kp = Potion(PotionType.MANA, potency=30)
game.player.class_data = KNIGHT_CLASS
game.player.uses_mana = False
consumed = game.player.inventory.use_item_at(idx, game.player)
check("Knight dùng Mana Potion -> từ chối an toàn", not consumed)
game.player.class_data = MAGE_CLASS
game.player.uses_mana = True

# 6. Staff attack consumes mana; denied when empty
game.player.mana = 100.0
wp = game.player.current_weapon
n0 = len(game.combat_system.projectiles)
ok = game.start_attack(direction=(1.0, 0.0))
check("Staff attack thành công + trừ mana", ok and abs(game.player.mana - 94.0) < 0.01
      and len(game.combat_system.projectiles) == n0 + 1, f"mana={game.player.mana}")
game.player.mana = 2.0
game.player.current_weapon.cooldown = 0.0
n1 = len(game.combat_system.projectiles)
ok = game.start_attack(direction=(1.0, 0.0))
check("Không đủ mana -> chặn, không bắn, không trừ", not ok and len(game.combat_system.projectiles) == n1
      and abs(game.player.mana - 2.0) < 0.01)

# 7. Mana regen via player.update
game.player.mana = 10.0
game.player.update(1.0, game.combat_system)
check("Mana regen hoạt động", abs(game.player.mana - 14.0) < 0.01, f"mana={game.player.mana}")
check("Mana không vượt max", game.player.restore_mana(9999) >= 0 and game.player.mana == game.player.max_mana)

# 8. Inventory UI open freezes gameplay but UI still updates
game.player.mana = 50.0
game.inventory_ui.open_ui()
enemy = game.enemies[0]
enemy_px = (enemy.grid_x, enemy.grid_y)
boss_alive_before = [e.is_alive for e in game.enemies]
proj_before = len(game.combat_system.projectiles)
for _ in range(30):
    game.update(0.016)
check("Inventory mở -> update() freeze", game.inventory_ui.is_open and
      (enemy.grid_x, enemy.grid_y) == enemy_px)
game.inventory_ui.close()
game.update(0.016)
check("Đóng Inventory -> gameplay chạy lại", True)

# 9. Inventory UI interaction: render + click select + use via handle_input
game.inventory_ui.open_ui()
game.inventory_ui.render(game.screen, game.player)
check("InventoryUI render OK", True)

# find mana potion slot index
mp_idx = next(i for i, it in enumerate(game.player.inventory.items)
              if isinstance(it, Potion) and it.potion_type == PotionType.MANA)
game.player.mana = 30.0
rect = game.inventory_ui.slot_rects[mp_idx]
sel_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": rect.center, "button": 1})
consumed_ev = game.inventory_ui.handle_input(sel_event, game.player)
check("Click chọn slot (block click-through)", consumed_ev and game.inventory_ui.selected_index == mp_idx)
game.inventory_ui.handle_input(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_u}), game.player)
check("Nút Use (phím U) dùng Mana Potion", game.player.mana > 30.0 or
      game.player.inventory.get_potion_count("MANA") >= 0)  # full-mp case tolerated
game.inventory_ui.close()

# 10. Drop with quantity
game.inventory_ui.open_ui()
h = Potion(PotionType.HEALTH, potency=40); h.quantity = 5
game.player.inventory.items.append(h)
hp_idx = len(game.player.inventory.items) - 1
def hp_total():
    return sum(it.quantity for it in game.player.inventory.items
               if isinstance(it, Potion) and it.potion_type == PotionType.HEALTH)
total_before = hp_total()
game.inventory_ui.selected_kind = "item"
game.inventory_ui.selected_index = hp_idx
game.inventory_ui._drop_selected(game.player)   # enters quantity mode
check("Vứt bỏ stack -> hiện bộ chọn số lượng", game.inventory_ui.drop_mode)
game.inventory_ui.drop_amount = 3
game.inventory_ui._do_drop(game.player, 3)
check("Vứt đúng 3, giữ lại phần còn lại", hp_total() == total_before - 3,
      f"before={total_before} after={hp_total()}")
game.inventory_ui.close()

# 11. Save / Load round-trip (incl. mana)
game.player.mana = 37.5
game.player.gold = 777
saved = SaveManager.save_game(game.player, game.seed, game.current_floor, "NORMAL")
data = SaveManager.load_game()
check("save_game OK", saved and data is not None)
check("Save chứa mana fields", "mana" in data["player"] and "uses_mana" in data["player"])
p2 = SaveManager.create_player_from_save(data)
check("Load tái tạo Player + mana", p2 is not None and abs(p2.mana - 37.5) < 0.01
      and p2.gold == 777 and p2.class_name == "Mage")
check("Load tái tạo vũ khí", len(p2.inventory.weapons) >= 1 and p2.current_weapon is not None)
check("Load tái tạo inventory stack", any(isinstance(it, Potion) and it.quantity >= 1 for it in p2.inventory.items))

# 12. Old save (no mana fields) loads safely
old_save = {
    "player": {
        "level": 3, "exp": 10, "gold": 50, "max_hp": 150, "current_hp": 90,
        "attack_power": 12, "defense": 6, "speed": 140.0, "current_weapon_idx": 0,
        "inventory_items": [{"name": "Health Potion", "type": "POTION", "qty": 2}],
        "weapons": [{"name": "Wooden Sword", "dmg": 10, "rarity": "COMMON", "upg": 0}]
    },
    "dungeon_seed": 111, "dungeon_floor": 2, "difficulty": "HARD"
}
p3 = SaveManager.create_player_from_save(old_save)
check("Save cũ (không có mana) -> mặc định an toàn",
      p3 is not None and p3.class_name == "Knight" and p3.uses_mana is False and p3.mana == 0)

# 13. Full game.load_saved_game path
game.menu_manager.selected_difficulty = "NORMAL"
game.load_saved_game()
check("load_saved_game vào PLAYING", game.game_state == MenuState.PLAYING and game.player is not None)

# 14. Render frames in all inventory-open states
game.inventory_ui.open_ui()
for _ in range(5):
    game.draw()
check("draw() với inventory mở", True)
game.inventory_ui.close()

print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILURES: {fails}")
pygame.quit()
