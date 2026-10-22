"""Relic effects match their descriptions and never stack up / ramp up (headless)."""
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
from entities.player import BASE_DASH_SPEED, BASE_DASH_TIME, MAX_DASH_SPEED_BONUS
from items.relic import FlameCore, ThunderRing, FrostHeart, BloodCharm, IronShell, VoidCrystal, Relic
from settings import STAMINA_DASH_COST

fails = []
def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        fails.append(name)

def fresh():
    game = Game()
    game.menu_manager.selected_class_idx = 0
    game.start_new_game(11)
    p = game.player
    p.max_hp = p.current_hp = 10 ** 6
    p.relics.clear()
    p.stamina = p.max_stamina = 10 ** 6
    return game, p

def dash(game, p):
    p.dash_cooldown = 0.0
    p.is_dashing = False
    p.trigger_dash(move_dir=(1.0, 0.0), game=game)

# ---------------------------------------------------------------- Thunder Ring
game, p = fresh()
dash(game, p)
check("Không có relic: dash tốc độ gốc", p.dash_speed == BASE_DASH_SPEED)
p.add_relic(ThunderRing())
speeds = []
for _ in range(25):
    dash(game, p)
    speeds.append(p.dash_speed)
expected = BASE_DASH_SPEED * 1.18
check("Thunder Ring: mỗi lần dash đều +18% (không tăng dần)", all(abs(s - expected) < 1e-6 for s in speeds),
      f"min={min(speeds):.1f} max={max(speeds):.1f}")
check("Thunder Ring: nằm trong trần +15..20%", 1.15 <= p.dash_speed / BASE_DASH_SPEED <= 1.20)

check("Nhặt Thunder Ring lần 2 -> không cộng dồn", p.add_relic(ThunderRing()) is False
      and p.dash_speed_multiplier == 1.18 and len(p.relics) == 1)

class FastRelic(Relic):
    dash_speed_bonus = 0.5
p.relics.append(FastRelic("fast", "Fast", "", "Rare", "", (1, 1, 1), ""))
check("Nhiều nguồn tăng tốc dash bị chặn ở +20%", abs(p.dash_speed_multiplier - (1 + MAX_DASH_SPEED_BONUS)) < 1e-9,
      f"x{p.dash_speed_multiplier:.2f}")

# Shockwave
game, p = fresh()
p.add_relic(ThunderRing())
near = Goblin(p.grid_x + 1, p.grid_y)
far = Goblin(p.grid_x + 6, p.grid_y)
for e in (near, far):
    e.max_hp = e.current_hp = 500
game.enemies = [near, far]
near.pos_x, near.pos_y = p.pos_x + 30, p.pos_y
far.pos_x, far.pos_y = p.pos_x + 200, p.pos_y
dash(game, p)
check("Thunder Ring: sóng điện gây sát thương quái ở gần", near.current_hp < 500, f"hp={near.current_hp}")
check("Thunder Ring: quái ở xa không bị", far.current_hp == 500)

# ---------------------------------------------------------------- Void Crystal
game, p = fresh()
p.add_relic(VoidCrystal())
p.stamina = 100.0
dash(game, p)
check("Void Crystal: +25% quãng dash", abs(p.dash_timer - BASE_DASH_TIME * 1.25) < 1e-9, f"{p.dash_timer:.4f}s")
check("Void Crystal: dash rẻ hơn 5 stamina", abs((100.0 - p.stamina) - (STAMINA_DASH_COST - 5)) < 1e-9,
      f"cost={100.0 - p.stamina}")
check("Void Crystal: không tăng tốc độ dash", p.dash_speed == BASE_DASH_SPEED)
p.add_relic(VoidCrystal())
check("Void Crystal nhặt lần 2 không cộng dồn", abs(p.dash_distance_multiplier - 1.25) < 1e-9)

# ---------------------------------------------------------------- Frost Heart
game, p = fresh()
p.add_relic(FrostHeart())
goblin = Goblin(p.grid_x + 3, p.grid_y)
base = goblin.speed
for _ in range(10):
    game.combat_system._apply_damage_to_enemy(p, goblin, 1, False, game.tilemap, game.obstacles)
check("Frost Heart: 10 đòn vẫn chỉ chậm 25% (không cộng dồn)", abs(goblin.speed - base * 0.75) < 1e-6,
      f"{goblin.speed:.1f}/{base:.1f}")
for _ in range(200):
    goblin._tick_slow(1 / 60)
check("Frost Heart: hết 3s trả lại tốc độ gốc", abs(goblin.speed - base) < 1e-6, f"{goblin.speed:.1f}")

# ---------------------------------------------------------------- Blood Charm / Flame Core / Iron Shell
game, p = fresh()
p.add_relic(BloodCharm())
dummy = Goblin(p.grid_x + 3, p.grid_y)
p.current_hp = p.max_hp
full = p.relics[0].on_hit_enemy(p, dummy, 100)
p.current_hp = 1
low = p.relics[0].on_hit_enemy(p, dummy, 100)
p.current_hp = p.max_hp // 2
half = p.relics[0].on_hit_enemy(p, dummy, 100)
check("Blood Charm: đầy máu +0%, nửa máu +25%, gần 0 máu ~+50%", full == 100 and half == 125 and 148 <= low <= 150,
      f"{full}/{half}/{low}")

check("Flame Core: +8 sát thương", FlameCore().on_hit_enemy(p, dummy, 20) == 28)

game, p = fresh()
d0, s0 = p.defense, p.speed
p.add_relic(IronShell())
p.add_relic(IronShell())
check("Iron Shell: +4 Defense, -10 Speed (một lần)", p.defense == d0 + 4 and abs(p.speed - max(90.0, s0 - 10.0)) < 1e-9,
      f"def {d0}->{p.defense}, spd {s0}->{p.speed}")

gold = p.gold
p.add_relic(FlameCore())
p.add_relic(FlameCore())
check("Relic trùng đổi thành vàng", p.gold == gold + 60 and len([r for r in p.relics if r.relic_id == "flame_core"]) == 1)

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
