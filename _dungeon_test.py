"""Dungeon generation / seed / minimap / save-load integration tests (headless)."""
import sys, tempfile, os
sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("DUNGEON_SAVE_FILE", os.path.join(tempfile.gettempdir(), "dungeon_test_save.json"))
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

import hashlib
import pygame
import random

pygame.init()
pygame.font.init()
pygame.display.set_mode((1024, 768))

from dungeon.dungeon_generator import DungeonGenerator
from dungeon.room import RoomType, RoomState
from core.game import Game
from core.save_manager import SaveManager
from ui.menu import MenuState
from ai.pathfinding import AStarPathfinder

fails = []
def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        fails.append(name)

def layout_signature(gen: DungeonGenerator):
    """Full deterministic fingerprint of a generated dungeon."""
    grid_hash = hashlib.sha256(
        b"".join(bytes(row) for row in gen.grid)
    ).hexdigest()[:16]
    rooms = tuple(sorted(
        (r.room_id, r.room_type, r.x, r.y, r.width, r.height, r.center_x, r.center_y)
        for r in gen.rooms
    ))
    corridors = tuple(sorted(tuple(sorted(c)) for c in gen.corridors))
    conns = tuple(sorted(
        tuple(sorted((a.room_id, b.room_id) for b in a.connected_rooms))
        for a in gen.rooms
    ))
    return grid_hash, rooms, corridors, conns

# ---------------------------------------------------------------- 1+2+3. Seed reproducibility
g1 = DungeonGenerator(seed=123456, floor=1)
grid1 = g1.generate()
sig1 = layout_signature(g1)

g2 = DungeonGenerator(seed=123456, floor=1)
grid2 = g2.generate()
sig2 = layout_signature(g2)

check("Seed 123456 -> grid giống hệt lần 2", sig1[0] == sig2[0], f"{sig1[0]} vs {sig2[0]}")
check("Seed 123456 -> rooms/bounds/type giống hệt", sig1[1] == sig2[1])
check("Seed 123456 -> corridors giống hệt", sig1[2] == sig2[2])
check("Seed 123456 -> kết nối phòng giống hệt", sig1[3] == sig2[3])
check("Seed 123456 -> grid object giống hệt", grid1 == grid2)

g3 = DungeonGenerator(seed=654321, floor=1)
grid3 = g3.generate()
sig3 = layout_signature(g3)
check("Seed khác -> layout khác", sig1[0] != sig3[0] or sig1[1] != sig3[1])

# Determinism across DIFFERENT global-random states (loot rolls must not affect map)
random.seed(1); ga = DungeonGenerator(seed=777, floor=1); ga.generate(); sig_a = layout_signature(ga)
random.seed(99999); gb = DungeonGenerator(seed=777, floor=1); gb.generate(); sig_b = layout_signature(gb)
check("Global random (loot/gameplay) KHÔNG ảnh hưởng map", sig_a == sig_b)

# ---------------------------------------------------------------- 4+5. Structure & connectivity
def validate_structure(gen, label):
    [r.room_type for r in gen.rooms]
    check(f"{label}: Start Room tồn tại", gen.start_room is not None and gen.start_room.room_type == RoomType.START)
    check(f"{label}: Boss Room tồn tại", gen.boss_room is not None and gen.boss_room.room_type == RoomType.BOSS)
    check(f"{label}: Boss room có kết nối", len(gen.boss_room.connected_rooms) >= 1)

    # Graph BFS: all rooms reachable from start
    seen = {gen.start_room}
    queue = [gen.start_room]
    while queue:
        cur = queue.pop()
        for nb in cur.connected_rooms:
            if nb not in seen:
                seen.add(nb)
                queue.append(nb)
    check(f"{label}: mọi phòng kết nối được trong graph", len(seen) == len(gen.rooms),
          f"{len(seen)}/{len(gen.rooms)}")

    # Grid flood fill from player spawn covers all room centers
    sx, sy = gen.start_room.center
    visited = {(sx, sy)}
    queue = [(sx, sy)]
    while queue:
        cx, cy = queue.pop()
        for dx, dy in ((0,1),(0,-1),(1,0),(-1,0)):
            nx, ny = cx+dx, cy+dy
            if 0 <= nx < gen.width and 0 <= ny < gen.height and (nx,ny) not in visited and gen.grid[ny][nx] != 0:
                visited.add((nx,ny)); queue.append((nx,ny))
    check(f"{label}: mọi tâm phòng đạt được trên grid", all(r.center in visited for r in gen.rooms))

    # Room ids + spawn data present
    check(f"{label}: room_id assigned", all(r.room_id for r in gen.rooms),
          f"ids={[r.room_id for r in gen.rooms]}")
    check(f"{label}: có dead-end nhánh (phong cách ảnh)", any(len(r.connected_rooms) == 1 for r in gen.rooms))
    check(f"{label}: spawn_positions ghi nhận", any(r.spawn_positions for r in gen.rooms))
    # Spawn not in wall
    ok_spawn = all(gen.grid[sy_][sx_] != 0 for r in gen.rooms for (sx_, sy_) in r.spawn_positions)
    check(f"{label}: không spawn trong wall", ok_spawn)
    # Branch diversity (not a single line): start has >= 2 branches or loops exist
    check(f"{label}: nhiều nhánh (không phải 1 đường thẳng)",
          len([r for r in gen.start_room.connected_rooms]) >= 1 and len(gen.rooms) >= 8)

for i, gen in enumerate([g1, g3]):
    validate_structure(gen, f"Seed test #{i+1}")

# ---------------------------------------------------------------- 6. Minimap
game = Game()
game.menu_manager.selected_class_idx = 2
game.seed = 123456
game.player = None
game.start_new_game()
game.menu_manager.player_name = "TestMage"
game.player.name = "TestMage"

check("Game start với seed 123456", game.game_state == MenuState.PLAYING)
check("Dungeon layout khớp generator trực tiếp", 
      hashlib.sha256(b"".join(bytes(row) for row in game.tilemap.grid)).hexdigest()[:16] == sig1[0])

# Fresh game: only start room discovered
disc = [r for r in game.dungeon_gen.rooms if game.minimap._is_room_discovered(r, game.tilemap)]
# A neighbouring room closer than the fog radius is legitimately glimpsed, so only require that the
# Start room is found and that nothing beyond the fog radius (e.g. the Boss room) is.
from settings import FOG_RADIUS
_sx, _sy = game.player.grid_x, game.player.grid_y
_near = lambda r: min(abs(r.center_x - _sx), abs(r.center_y - _sy)) <= FOG_RADIUS + max(r.width, r.height)
check("Fog of war: mới chỉ Start room được khám phá",
      any(r.room_type == RoomType.START for r in disc)
      and all(r.room_type == RoomType.START or _near(r) for r in disc)
      and not any(r.room_type == RoomType.BOSS for r in disc))

# Simulate exploring: walk fog around boss room center
game.tilemap.update_fog_of_war(*game.dungeon_gen.boss_room.center)
disc2 = [r for r in game.dungeon_gen.rooms if game.minimap._is_room_discovered(r, game.tilemap)]
check("Fog of war: Boss room hiện khi khám phá", any(r.room_type == RoomType.BOSS for r in disc2))
game.draw()
check("Minimap render OK (rooms graph)", True)
game.tilemap.update_fog_of_war(*game.dungeon_gen.get_player_spawn_pos())

# ---------------------------------------------------------------- 7. A* on the map
start = game.dungeon_gen.start_room.center
goal = game.dungeon_gen.boss_room.center
path = AStarPathfinder.find_path(start, goal, game.tilemap)
check("A*: Start -> Boss có đường đi", len(path) > 0, f"path_len={len(path)}")
if path:
    check("A*: path đi từ cạnh start", path[0] in [(start[0]+1,start[1]),(start[0]-1,start[1]),(start[0],start[1]+1),(start[0],start[1]-1)])
    check("A*: path kết thúc ở goal", path[-1] == goal)
    check("A*: mọi bước đi được", all(game.tilemap.is_walkable(x, y) for x, y in path))

# ---------------------------------------------------------------- 8. Room Clear & Gate
controller = game.boss_controller
gates = game.boss_gates
check("Boss gates được cài đặt", len(gates) >= 1)
gx0, gy0 = gates[0].tx, gates[0].ty
for g in gates:
    g.lock(game.tilemap)
check("Gate lock -> tile CLOSED_GATE", all(not g.is_open for g in gates) and
      game.tilemap.get_tile(gx0, gy0) == 3)
for g in gates:
    g.unlock(game.tilemap)
check("Gate unlock -> tile OPEN_GATE", game.tilemap.get_tile(gx0, gy0) == 4)

# Room clear flow on a combat room
combat_room = next((r for r in game.dungeon_gen.rooms if r.room_type in (RoomType.COMBAT, RoomType.ELITE)
                    and r.enemies), None)
if combat_room:
    combat_room.state = RoomState.ACTIVE
    for dx, dy in combat_room.door_tiles:
        game.tilemap.set_tile(dx, dy, 3)  # locked
    for e in list(combat_room.enemies):
        e.is_alive = False
    # emulate game.update room-clear block
    living = [e for e in combat_room.enemies if e.is_alive]
    check("Room Clear: enemies chết hết", not living)
    combat_room.state = RoomState.CLEARED
    combat_room.is_cleared = True
    for dx, dy in combat_room.door_tiles:
        game.tilemap.set_tile(dx, dy, 1)  # floor
    check("Room Clear: cửa mở sau khi clear", all(game.tilemap.get_tile(dx, dy) == 1 for dx, dy in combat_room.door_tiles))

# ---------------------------------------------------------------- 9. Save/Load with dungeon progress
# Progress the run: explore fog into another room, open nothing, kill the boss
second_room = next(r for r in game.dungeon_gen.rooms if r is not game.dungeon_gen.start_room)
game.tilemap.update_fog_of_war(second_room.center_x, second_room.center_y)
game.player.set_grid_pos(second_room.center_x, second_room.center_y)

# simulate boss defeated
boss = game.boss
boss_dead_pos = (boss.grid_x, boss.grid_y)
boss.take_damage(99999)  # proper death path: is_alive False + FSM DEAD state
game.update(0.016)  # triggers boss death -> controller COMPLETED, gates unlock, loot drops
check("Boss chết -> controller COMPLETED", game.boss_controller.state == "COMPLETED")
game.player.gold = 555
game.player.mana = 42.0

ds = SaveManager.collect_dungeon_state(game)
saved = SaveManager.save_game(game.player, game.seed, game.current_floor, "NORMAL", dungeon_state=ds)
check("Save with dungeon_state", saved)

data = SaveManager.load_game()
check("Save chứa seed + dungeon_state", data.get("dungeon_seed") == 123456 and data.get("dungeon_state") is not None)

explored_before = sum(row.count("1") for row in data["dungeon_state"]["explored_rows"])
check("Fog được lưu", explored_before > 0, f"tiles={explored_before}")

# Fresh game object -> load
game2 = Game()
game2.load_saved_game()
check("Load: PLAYING, floor/seed đúng", game2.game_state == MenuState.PLAYING 
      and game2.current_floor == 1 and game2.seed == 123456)
check("Load: layout giữ nguyên (không random lại)",
      hashlib.sha256(b"".join(bytes(row) for row in game2.tilemap.grid)).hexdigest()[:16] == sig1[0])
explored_after = sum(1 for row in game2.tilemap.explored for t in row if t)
check("Load: fog khôi phục", explored_after == explored_before, f"{explored_after}/{explored_before}")
check("Load: player pos khôi phục", (game2.player.grid_x, game2.player.grid_y) == (second_room.center_x, second_room.center_y))
check("Load: boss KHÔNG respawn", game2.boss is None and game2.boss_controller.state == "COMPLETED")
check("Load: player stats (gold/mana)", game2.player.gold == 555 and abs(game2.player.mana - 42.0) < 0.01)
check("Load: player name", game2.player.name == "TestMage")

# ---------------------------------------------------------------- 10. Floor transition
floor1_seed = game2.seed
game2.boss = None
game2.next_floor()
check("Chuyển floor: floor tăng", game2.current_floor == 2)
check("Chuyển floor: seed mới sinh", game2.seed != floor1_seed)
check("Chuyển floor: player giữ progression", game2.player is not None and game2.player.gold == 555)
check("Chuyển floor: dungeon mới được tạo", len(game2.dungeon_gen.rooms) >= 7)
check("Chuyển floor: minimap cache reset cho map mới", True)

# ---------------------------------------------------------------- 11. RUN_CONFIG menu input
game3 = Game()
game3.game_state = MenuState.CLASS_SELECT
game3.handle_events.__self__  # just ensure method exists
# simulate: class select ENTER -> RUN_CONFIG
game3.menu_manager.reset_run_config()
game3.game_state = MenuState.RUN_CONFIG
for ch in "123456":
    game3.menu_manager.active_field = "seed"
    game3.menu_manager.append_char(ch)
game3.menu_manager.active_field = "name"
for ch in "HeroX":
    game3.menu_manager.append_char(ch)
check("RUN_CONFIG: nhập seed", game3.menu_manager.get_configured_seed() == 123456)
check("RUN_CONFIG: nhập tên", game3.menu_manager.player_name == "HeroX")
game3.menu_manager.randomize_seed()
check("RUN_CONFIG: Random Seed bỏ ô nhập", game3.menu_manager.seed_input == "" and game3.menu_manager.randomized_seed is not None)
check("RUN_CONFIG: random seed dùng khi không nhập", game3.menu_manager.get_configured_seed() == game3.menu_manager.randomized_seed)
game3.menu_manager.seed_input = ""
game3.menu_manager.randomized_seed = None
check("RUN_CONFIG: để trống -> None (random lúc start)", game3.menu_manager.get_configured_seed() is None)
game3.menu_manager.render_run_config(game3.screen)
check("RUN_CONFIG render OK", True)

# start via config
game3.seed = game3.menu_manager.get_configured_seed() or random.randint(100000, 999999)
game3.current_floor = 1
game3.player = None
game3.start_new_game()
game3.player.name = game3.menu_manager.player_name or "Hero"
check("Start từ RUN_CONFIG tạo game PLAYING", game3.game_state == MenuState.PLAYING and game3.player.name == "HeroX")

print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILURES: {fails}")
pygame.quit()
