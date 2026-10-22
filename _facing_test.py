"""Facing / walk animation: sprites face LEFT natively, so they mirror when moving right (no moonwalk)."""
import sys, tempfile, os
sys.stdout.reconfigure(encoding="utf-8")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("DUNGEON_SAVE_FILE", os.path.join(tempfile.gettempdir(), "dungeon_test_save.json"))

import collections
import pygame

pygame.init()
pygame.display.set_mode((1024, 768))

from core.game import Game

fails = []
def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        fails.append(name)

game = Game()
game.menu_manager.selected_class_idx = 0
game.start_new_game(11)
p = game.player

def press(*keys, frames=3):
    state = collections.defaultdict(bool)
    for k in keys:
        state[k] = True
    for _ in range(frames):
        p.handle_continuous_input(state, 1 / 60, game.tilemap, game.obstacles, game.boss_gates)

press(pygame.K_d)
check("Đi phải (D) -> lật sprite (mặt hướng phải)", p.flip_x is True)
press(pygame.K_a)
check("Đi trái (A) -> không lật (mặt hướng trái gốc)", p.flip_x is False)
press(pygame.K_d)
press(pygame.K_w)
check("Đi lên (W) sau khi đi phải -> giữ hướng phải", p.flip_x is True)
press(pygame.K_s)
check("Đi xuống (S) -> giữ hướng", p.flip_x is True)
press(pygame.K_a, pygame.K_w)
check("Chéo trái-lên -> mặt trái", p.flip_x is False)

# Walk animation: distinct frames, feet pinned to the ground
frames = p.animator.animations["walk"]
check("Walk có 4 frame khác nhau", len({pygame.image.tobytes(f, "RGBA") for f in frames}) == 4)
bottoms = [f.get_bounding_rect().bottom for f in frames]
check("Chân không lún/bay quá 2px", max(bottoms) - min(bottoms) <= 2, f"bottoms={bottoms}")
check("Walk nhanh hơn idle", p.animator.state_fps["walk"] > p.animator.fps)

# Enemies mirror toward their target as well
from entities.enemy import Goblin
g = Goblin(10, 10)
g.move_toward_world(g.pos_x + 100, g.pos_y, 60, 1 / 60, game.tilemap, [])
check("Quái đi sang phải -> lật", g.flip_x is True)
g.move_toward_world(g.pos_x - 100, g.pos_y, 60, 1 / 60, game.tilemap, [])
check("Quái đi sang trái -> không lật", g.flip_x is False)

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
