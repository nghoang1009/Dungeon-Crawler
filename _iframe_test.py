"""Post-hit invulnerability: one hit, then a grace period (headless)."""
import sys, tempfile, os
sys.stdout.reconfigure(encoding="utf-8")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("DUNGEON_SAVE_FILE", os.path.join(tempfile.gettempdir(), "dungeon_test_save.json"))

import pygame

pygame.init()
pygame.display.set_mode((1024, 768))

from core.game import Game
from entities.enemy import Goblin
from entities.player import HIT_INVULNERABILITY_SECONDS
from combat.projectile import Projectile
from world.door import Trap

fails = []
def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        fails.append(name)

game = Game()
game.menu_manager.selected_class_idx = 0
game.start_new_game(11)
p = game.player
cs = game.combat_system
p.defense = 0
p.max_hp = p.current_hp = 1000
goblin = Goblin(p.grid_x + 1, p.grid_y)
dmg = max(1, goblin.attack_power)

# ---- melee hits
cs.enemy_attack_player(goblin, p)
check("Bị đánh -> mất máu", p.current_hp == 1000 - dmg, f"hp={p.current_hp}")
check("Bị đánh -> có thời gian miễn thương", p.is_invulnerable and p.invuln_timer > 0)
for _ in range(5):
    cs.enemy_attack_player(goblin, p)
check("Trong thời gian miễn thương không mất thêm máu", p.current_hp == 1000 - dmg, f"hp={p.current_hp}")

# ---- grace period ends
for _ in range(int((HIT_INVULNERABILITY_SECONDS + 0.1) * 60)):
    p.update(1 / 60, cs)
check("Hết thời gian -> hết miễn thương", not p.is_invulnerable and p.invuln_timer == 0.0)
cs.enemy_attack_player(goblin, p)
check("Hết miễn thương -> bị đánh lại bình thường", p.current_hp == 1000 - 2 * dmg, f"hp={p.current_hp}")

# ---- projectiles pass through during the grace period (are not eaten)
p.invuln_timer = 0.0
p.current_hp = 1000
arrow = Projectile(p.pos_x - 40, p.pos_y, 1, 0, damage=20, speed=0.0, range_px=200.0, owner="enemy", proj_type="arrow")
p.start_hit_invulnerability()
cs.projectiles = [arrow]
arrow.pos_x, arrow.pos_y = p.pos_x, p.pos_y
hp = p.current_hp
for _ in range(3):
    cs.update(1 / 60, game.tilemap, game.enemies, p, game.obstacles)
check("Đạn đi xuyên khi đang miễn thương (không mất máu, không biến mất)", p.current_hp == hp and arrow.is_alive)
p.invuln_timer = 0.0
cs.update(1 / 60, game.tilemap, game.enemies, p, game.obstacles)
check("Hết miễn thương -> đạn trúng", p.current_hp < hp and not arrow.is_alive, f"hp={p.current_hp}")

# ---- spike trap respects it too
p.invuln_timer = 0.0
p.current_hp = 1000
trap = Trap(p.grid_x, p.grid_y, damage=15)
trap.update(0.0, p)
check("Bẫy gai gây sát thương rồi cho miễn thương", p.current_hp == 985 and p.invuln_timer > 0)
trap.cooldown = 0.0
trap.update(0.0, p)
check("Bẫy gai không gây thêm sát thương khi đang miễn thương", p.current_hp == 985)

# ---- poison / burn ticks are not blocked
p.invuln_timer = 5.0
p.current_hp = 1000
p.apply_status_effect("poison", duration=3.0, value=10)
for _ in range(90):
    p.update(1 / 60, cs)
check("Độc/cháy vẫn gây sát thương trong lúc miễn thương", p.current_hp < 1000, f"hp={p.current_hp}")

# ---- rendering while blinking
p.invuln_timer = 0.5
game.draw()
check("Vẽ nhân vật nhấp nháy không lỗi", True)

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
