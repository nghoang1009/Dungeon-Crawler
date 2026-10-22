"""Auto-Hit Left Mouse Button Hold Integration Test."""
import sys, tempfile, os
sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("DUNGEON_SAVE_FILE", os.path.join(tempfile.gettempdir(), "dungeon_test_save.json"))
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import pygame

pygame.init()
pygame.font.init()
pygame.display.set_mode((1024, 768))

from core.game import Game
from ui.menu import MenuState
from combat.weapon import create_wooden_sword, create_great_sword, create_hunting_bow, create_apprentice_staff
from entities.class_data import MAGE_CLASS

fails = []
def check(name, cond, extra=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name} {extra}")
    if not cond:
        fails.append(name)

# 1. Setup game
game = Game()
game.menu_manager.selected_class_idx = 0  # Knight
game.seed = 99999
game.player = None
game.start_new_game(game.seed)

check("Game start PLAYING", game.game_state == MenuState.PLAYING and game.player is not None)

# 2. Test Single Click LMB
wp_sword = create_wooden_sword()
game.player.inventory.weapons = [wp_sword]
game.player.current_weapon_idx = 0
wp_sword.cooldown = 0.0

# Simulate 1 frame with MOUSEBUTTONDOWN
mx, my = 600, 384
ev = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (mx, my), "button": 1})
pygame.event.post(ev)
game.handle_events()
check("Single Click LMB -> 1 đòn đánh", wp_sword.cooldown > 0.0, f"cooldown={wp_sword.cooldown:.3f}")
cd_initial = wp_sword.cooldown

# 3. Simulate mouse NOT held (mouse_pressed[0] is False) -> cooldown decreases, no extra attack
for _ in range(10):
    game.update(0.016)
check("Thả chuột -> cooldown giảm dần, không tự đánh", wp_sword.cooldown < cd_initial, f"cooldown={wp_sword.cooldown:.3f}")

# 4. Test Hold Mouse Button with Mock / get_pressed
# Mock pygame.mouse.get_pressed and get_pos
def mock_mouse(pressed=(True, False, False), pos=(800, 384)):
    pygame.mouse.get_pressed = lambda: pressed
    pygame.mouse.get_pos = lambda: pos

# With weapon attack_speed = 2.0 (cooldown = 0.5s): in 1.0s, exactly 2 attacks should happen!
wp_test = create_wooden_sword()
wp_test.attack_speed = 2.0  # exactly 2 attacks per sec (0.5s per attack)
wp_test.cooldown = 0.0
game.player.inventory.weapons = [wp_test]
game.player.current_weapon_idx = 0

attack_count = 0
orig_player_attack = game.combat_system.player_attack
def tracked_attack(player, enemies, obstacles, tilemap, direction=None):
    global attack_count
    attack_count += 1
    return orig_player_attack(player, enemies, obstacles, tilemap, direction=direction)
game.combat_system.player_attack = tracked_attack

mock_mouse(pressed=(True, False, False), pos=(800, 384))
attack_count = 0

# Simulate 60 frames at 60 FPS (dt = 0.01666s -> total 1.0s)
for i in range(60):
    game.update(0.01666)

# Frame 0: attack 1 (cooldown = 0.5s)
# At frame 30 (0.5s): attack 2 (cooldown = 0.5s)
# At frame 60 (1.0s): attack 3
check("Giữ chuột 1.0s với attack_speed=2.0 -> 2-3 đòn (t=0s, 0.5s, 1.0s)",
      attack_count in (2, 3), f"attack_count={attack_count}")
check("Không tạo attack mỗi frame (attack_count < 10)", attack_count <= 4, f"attack_count={attack_count}")

# 5. Test Mouse Movement while holding (direction updates continuously)
mock_mouse(pressed=(True, False, False), pos=(200, 384)) # Move to left side
game.update(0.016)
check("Di chuyển chuột sang trái -> facing_dir hướng sang trái", game.player.facing_dir[0] < 0 and game.player.flip_x is False)  # sprites face left natively

mock_mouse(pressed=(True, False, False), pos=(900, 384)) # Move to right side
game.update(0.016)
check("Di chuyển chuột sang phải -> facing_dir hướng sang phải", game.player.facing_dir[0] > 0 and game.player.flip_x is True)

# 6. Test Great Sword (slower attack_speed = 1.3 -> cooldown ~0.77s)
wp_gs = create_great_sword()
game.player.inventory.weapons = [wp_gs]
game.player.current_weapon_idx = 0
wp_gs.cooldown = 0.0
attack_count = 0

mock_mouse(pressed=(True, False, False), pos=(800, 384))
for _ in range(60): # 1.0s
    game.update(0.01666)

check("Great Sword (chậm hơn) -> đúng 2 đòn trong 1.0s", attack_count == 2, f"attack_count={attack_count}")

# 7. Test Ranged (Bow) -> spawns projectiles properly
wp_bow = create_hunting_bow()
game.player.inventory.weapons = [wp_bow]
game.player.current_weapon_idx = 0
wp_bow.cooldown = 0.0
game.combat_system.projectiles.clear()

mock_mouse(pressed=(True, False, False), pos=(800, 384))
game.update(0.016)
check("Bow giữ chuột -> sinh Projectile độc lập", len(game.combat_system.projectiles) == 1)
check("Projectile có vận tốc và owner player", game.combat_system.projectiles[0].owner == "player")

# 8. Test Mage Staff with Mana
game.player.class_data = MAGE_CLASS
game.player.uses_mana = True
game.player.mana = 100.0
game.player.max_mana = 100.0
wp_staff = create_apprentice_staff()
game.player.inventory.weapons = [wp_staff]
game.player.current_weapon_idx = 0
wp_staff.cooldown = 0.0
game.combat_system.projectiles.clear()

mock_mouse(pressed=(True, False, False), pos=(800, 384))
game.update(0.016)
check("Staff giữ chuột có mana -> trừ mana và sinh magic bolt",
      game.player.mana < 100.0 and len(game.combat_system.projectiles) == 1,
      f"mana={game.player.mana}")

# 9. Test Mage Staff with 0 Mana -> no crash, no projectile spam
game.player.mana = 1.0
wp_staff.cooldown = 0.0
proj_count_before = len(game.combat_system.projectiles)
dmg_nums_before = len(game.combat_system.damage_numbers)

mock_mouse(pressed=(True, False, False), pos=(800, 384))
for _ in range(30):
    game.player.mana = 1.0  # keep mana depleted
    game.update(0.016)

check("Staff hết mana -> không bắn thêm projectile", len(game.combat_system.projectiles) == proj_count_before)
# Damage numbers should be throttled by weapon cooldown, not 30 separate texts
new_dmg_nums = len(game.combat_system.damage_numbers) - dmg_nums_before
check("Staff hết mana -> không spam 60 text/giây (bị cooldown throttle)", new_dmg_nums <= 3, f"new_dmg_nums={new_dmg_nums}")

# 10. Test Key K Attack still works
wp_sword.cooldown = 0.0
game.player.inventory.weapons = [wp_sword]
game.player.current_weapon_idx = 0
mock_mouse(pressed=(False, False, False), pos=(800, 384)) # Mouse released

k_event = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_k})
pygame.event.post(k_event)
game.handle_events()
check("Phím K vẫn đánh bình thường", wp_sword.cooldown > 0.0)

# 11. Test Modals block auto-attack
# A. Inventory open
wp_sword.cooldown = 0.0
attack_count = 0
game.inventory_ui.open_ui()
mock_mouse(pressed=(True, False, False), pos=(800, 384))
game.update(0.016)
check("Inventory mở -> không auto attack", attack_count == 0 and wp_sword.cooldown == 0.0)
game.inventory_ui.close()

# B. Pause state
game.game_state = MenuState.PAUSED
attack_count = 0
game.update(0.016)
check("Game Pause -> không auto attack", attack_count == 0)
game.game_state = MenuState.PLAYING

# C. Level Up modal active
game.level_up_modal.is_active = True
attack_count = 0
game.update(0.016)
check("Level Up modal active -> không auto attack", attack_count == 0)
game.level_up_modal.is_active = False

# D. NPC modal active
game.npc_modal.is_active = True
attack_count = 0
game.update(0.016)
check("NPC modal active -> không auto attack", attack_count == 0)
game.npc_modal.is_active = False

# 12. Test Animation reset on each attack
wp_sword.cooldown = 0.0
game.player.animator.change_state("idle")
mock_mouse(pressed=(True, False, False), pos=(800, 384))
game.update(0.016)
check("Đòn đánh -> animator chuyển sang state attack", game.player.animator.current_state == "attack")

print()
print("FINAL TEST RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILURES: {fails}")
pygame.quit()
