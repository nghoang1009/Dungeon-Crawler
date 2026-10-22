"""UI regression: minimap fades behind the player, boss bar only shows during the fight, M toggles (headless)."""
import sys, tempfile, os, time
sys.stdout.reconfigure(encoding="utf-8")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("DUNGEON_SAVE_FILE", os.path.join(tempfile.gettempdir(), "dungeon_test_save.json"))

import pygame

pygame.init()
pygame.display.set_mode((1024, 768))

from core.game import Game
from world.gate import BossRoomState
from ui.minimap import FADE_NEAR, FADE_FAR

fails = []
def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        fails.append(name)

game = Game()
game.menu_manager.selected_class_idx = 0
game.start_new_game(11)
game.player.max_hp = game.player.current_hp = 10 ** 9
screen = pygame.display.get_surface()

def frames(n, dt=1 / 60):
    for _ in range(n):
        game.update(dt)
        game.draw()
        time.sleep(0.004)

# --- Minimap fades when the player is behind it, and recovers afterwards
frames(30)
check("Minimap rõ khi player ở xa", game.minimap._alpha > FADE_FAR - 0.05, f"alpha={game.minimap._alpha:.2f}")

game.camera.max_x = game.camera.max_y = 10 ** 6   # let the camera follow into the corner
game.camera.offset_x, game.camera.offset_y = 0.0, 0.0
orig_apply = game.camera.apply_pos
game.camera.apply_pos = lambda x, y: (900, 100)    # player drawn inside the minimap area
for _ in range(60):
    game.draw()
    time.sleep(0.01)
check("Minimap mờ đi khi che player", game.minimap._alpha < FADE_NEAR + 0.05, f"alpha={game.minimap._alpha:.2f}")
game.camera.apply_pos = orig_apply
for _ in range(120):
    game.draw()
    time.sleep(0.01)
check("Minimap rõ lại khi player rời đi", game.minimap._alpha > FADE_FAR - 0.05, f"alpha={game.minimap._alpha:.2f}")

# --- Toggle
game.minimap.toggle()
check("M ẩn minimap", game.minimap.visible is False)
game.minimap.toggle()

# --- Boss bar: hidden while passing by, visible during the fight, fades out after
boss = game.boss
ctrl = game.boss_controller
ctrl.state = BossRoomState.INACTIVE
for _ in range(30):
    game.draw()
    time.sleep(0.01)
check("Thanh HP boss ẩn khi đi ngang qua", game.boss_bar._alpha == 0.0, f"alpha={game.boss_bar._alpha:.2f}")

ctrl.state = BossRoomState.FIGHTING
for _ in range(60):
    game.draw()
    time.sleep(0.01)
check("Thanh HP boss hiện khi đánh boss", game.boss_bar._alpha > 0.95, f"alpha={game.boss_bar._alpha:.2f}")

ctrl.state = BossRoomState.BOSS_DEFEATED
for _ in range(80):
    game.draw()
    time.sleep(0.01)
check("Thanh HP boss tắt sau khi hết giao tranh", game.boss_bar._alpha == 0.0, f"alpha={game.boss_bar._alpha:.2f}")

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
