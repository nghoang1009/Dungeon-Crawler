"""Dash / move_and_slide wall-stuck regression test (headless)."""
import sys, tempfile, os
sys.stdout.reconfigure(encoding="utf-8")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("DUNGEON_SAVE_FILE", os.path.join(tempfile.gettempdir(), "dungeon_test_save.json"))

import math
import random
import pygame

pygame.init()
pygame.display.set_mode((1024, 768))

from core.game import Game
from core.collision import CollisionSystem
from settings import TILE_SIZE

game = Game()
game.menu_manager.selected_class_idx = 0
game.start_new_game(777)
player, tilemap = game.player, game.tilemap
obstacles = getattr(game, "obstacles", [])

fails = []
def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        fails.append(name)

floor = [(x, y) for y in range(tilemap.height) for x in range(tilemap.width) if tilemap.is_walkable(x, y)]
rng = random.Random(1)

def overlaps_wall():
    return CollisionSystem.check_wall_collision(player.get_hitbox(), tilemap, obstacles)

penetrations = 0
stuck = 0
trials = 0
for dt in (1 / 60, 1 / 30, 1 / 15):
    for _ in range(400):
        gx, gy = rng.choice(floor)
        player.pos_x = gx * TILE_SIZE + rng.uniform(4, TILE_SIZE - 4)
        player.pos_y = gy * TILE_SIZE + rng.uniform(4, TILE_SIZE - 4)
        player.sync_rect()
        if overlaps_wall():
            continue
        trials += 1
        ang = rng.uniform(0, math.tau)
        player.dash_dir = (math.cos(ang), math.sin(ang))
        player.dash_speed = 440.0
        bad = False
        for _f in range(int(0.25 / dt) + 1):
            CollisionSystem.move_and_slide(player, player.dash_dir[0] * 440 * dt, player.dash_dir[1] * 440 * dt, tilemap, obstacles)
            if overlaps_wall():
                bad = True
        if bad:
            penetrations += 1
        # Can the player still walk away from where the dash ended?
        sx, sy = player.pos_x, player.pos_y
        moved = False
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            player.pos_x, player.pos_y = sx, sy
            player.sync_rect()
            CollisionSystem.move_and_slide(player, d[0] * 3, d[1] * 3, tilemap, obstacles)
            if (player.pos_x, player.pos_y) != (sx, sy):
                moved = True
        if not moved:
            stuck += 1

check("Dash không xuyên/kẹt vào tường", penetrations == 0, f"{penetrations}/{trials}")
check("Sau dash vẫn đi thoát được", stuck == 0, f"{stuck}/{trials}")

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
