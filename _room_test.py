"""Room lock regression: enemies stay in their room, doors sit in the doorway and re-open when cleared (headless)."""
import sys, tempfile, os
sys.stdout.reconfigure(encoding="utf-8")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("DUNGEON_SAVE_FILE", os.path.join(tempfile.gettempdir(), "dungeon_test_save.json"))

import pygame

pygame.init()
pygame.display.set_mode((1024, 768))

from core.game import Game
from dungeon.room import RoomType, RoomState
from settings import TILE_SIZE, TILE_CLOSED_GATE, TILE_FLOOR

fails = []
def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        fails.append(name)

LOCKABLE = (RoomType.COMBAT, RoomType.ELITE, RoomType.SURVIVAL)
escaped = outside_doors = rooms_tested = stranded = not_reopened = 0

for seed in (11, 222, 3333, 44444, 555555):
    game = Game()
    game.menu_manager.selected_class_idx = 0
    game.start_new_game(seed)
    gen = game.dungeon_gen

    for room in gen.rooms:
        if room.room_type not in LOCKABLE or not room.door_tiles or not room.enemies:
            continue
        rooms_tested += 1
        game.player.max_hp = game.player.current_hp = 10 ** 9  # keep the test running while enemies attack

        # Doors are doorway tiles: outside the room rectangle, never on its inner floor
        for dx, dy in room.door_tiles:
            if room.x <= dx < room.right and room.y <= dy < room.bottom:
                outside_doors += 1

        def step(frames):
            global escaped
            for _ in range(frames):
                game.level_up_modal.is_active = False  # kills grant EXP; do not let the modal freeze the sim
                game.update(1 / 60)
                for e in room.enemies:
                    if e.is_alive and not (room.x * TILE_SIZE <= e.pos_x <= room.right * TILE_SIZE
                                           and room.y * TILE_SIZE <= e.pos_y <= room.bottom * TILE_SIZE):
                        escaped += 1

        # Player stands in the corridor next to a door: enemies must not follow out of the room
        dx, dy = room.door_tiles[0]
        game.player.set_grid_pos(dx, dy)
        step(180)
        # then walks into the room and fights for a while
        game.player.set_grid_pos(room.center_x, room.center_y)
        step(240)

        check_locked = all(game.tilemap.get_tile(x, y) == TILE_CLOSED_GATE for x, y in room.door_tiles)
        if room.state == RoomState.ACTIVE and not check_locked:
            stranded += 1

        for e in room.enemies:
            e.take_damage(99999)
        step(5)
        if not (room.is_cleared and all(game.tilemap.get_tile(x, y) == TILE_FLOOR for x, y in room.door_tiles)):
            not_reopened += 1

check("Có phòng để test", rooms_tested > 0, f"{rooms_tested} phòng")
check("Cửa nằm ở lối vào (ngoài phòng)", outside_doors == 0, f"{outside_doors} sai")
check("Quái không chạy ra khỏi phòng", escaped == 0, f"{escaped} lần")
check("Phòng khóa đủ cửa khi giao tranh", stranded == 0, f"{stranded} phòng")
check("Hết quái -> mở cửa", not_reopened == 0, f"{not_reopened} phòng")

# ---- Boss never attacks a player who is outside its room
from world.gate import BossRoomState
game = Game()
game.menu_manager.selected_class_idx = 0
game.current_floor = 2   # Ignis: a stationary ranged boss with no range check of its own
game.player = None
game.start_new_game(557)
game.player.max_hp = game.player.current_hp = 10 ** 9
boss, ctrl, broom = game.boss, game.boss_controller, game.dungeon_gen.boss_room

# park the player in the nearest non-boss room, far from the arena
quiet = (RoomType.START, RoomType.SHOP, RoomType.TREASURE, RoomType.EVENT)   # rooms without shooting enemies
other = min((r for r in game.dungeon_gen.rooms if r is not broom and r.room_type in quiet),
            key=lambda r: abs(r.center_x - broom.center_x) + abs(r.center_y - broom.center_y))
game.player.set_grid_pos(other.center_x, other.center_y)
game.enemies = [boss]   # only the boss may attack, so anything that spawns comes from it
spawned = 0
for _ in range(600):
    game.level_up_modal.is_active = False
    game.update(1 / 60)
    spawned += len(game.combat_system.telegraph_zones) + len(game.combat_system.projectiles)
check("Boss không tung chiêu khi player ngoài phòng", spawned == 0,
      f"zones+projectiles={spawned}")

# once the fight really starts it does attack
game.player.set_grid_pos(broom.center_x - 3, broom.center_y)
ctrl.state = BossRoomState.FIGHTING
boss.skill_cooldown = 0.0
attacked = 0
for _ in range(240):
    game.level_up_modal.is_active = False
    game.update(1 / 60)
    attacked += len(game.combat_system.telegraph_zones) + len(game.combat_system.projectiles)
check("Boss tấn công khi đang đánh trong phòng", attacked > 0, f"count={attacked}")


# ---- No enemy spawns inside a wall / chest (e.g. the elite orc on a random chest at the room centre)
from core.collision import CollisionSystem
stuck = 0
spawned = 0
game = Game()
game.menu_manager.selected_class_idx = 0
for floor in range(1, 11):
    for seed in range(25):
        game.current_floor = floor
        game.player = None
        game.start_new_game(seed * 53 + floor)
        for e in game.enemies:
            spawned += 1
            if CollisionSystem.check_wall_collision(e.get_hitbox(), game.tilemap, game.obstacles):
                stuck += 1
check("Không quái nào spawn kẹt trong tường / rương", stuck == 0, f"{stuck}/{spawned}")

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
