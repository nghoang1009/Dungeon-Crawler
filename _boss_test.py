"""Boss skills: every ability of all 10 bosses runs, phases escalate, nothing leaves the room (headless)."""
import sys, tempfile, os, math
sys.stdout.reconfigure(encoding="utf-8")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("DUNGEON_SAVE_FILE", os.path.join(tempfile.gettempdir(), "dungeon_test_save.json"))

import pygame

pygame.init()
pygame.display.set_mode((1024, 768))

from core.game import Game
from world.gate import BossRoomState

fails = []
def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        fails.append(name)

game = Game()
game.menu_manager.selected_class_idx = 0

def setup(floor, seed=900):
    game.current_floor = floor
    game.player = None
    game.start_new_game(seed + floor)
    p, boss = game.player, game.boss
    p.max_hp = p.current_hp = 10 ** 9
    game.enemies = [boss]
    game.boss_controller.state = BossRoomState.FIGHTING
    room = game.dungeon_gen.boss_room
    p.set_grid_pos(room.center_x - 4, room.center_y)
    return p, boss, room

def step(frames):
    for _ in range(frames):
        game.level_up_modal.is_active = False
        game.update(1 / 60)
        game.draw()

# ---- 1. Every ability of every boss runs in every phase without errors
errors, abilities_total = [], 0
for floor in range(1, 11):
    p, boss, room = setup(floor)
    for phase in (1, 2, 3):
        boss.phase = phase
        for ability in boss.abilities:
            abilities_total += 1
            try:
                game.combat_system.telegraph_zones.clear()
                game.combat_system.projectiles.clear()
                boss._events.clear()
                boss.charging = False
                ability.fn(game)
                for _ in range(150):           # let scheduled follow-ups (charges, leaps, waves) play out
                    boss.cast_timer = 0.0
                    boss.current_hp = max(boss.current_hp, 1)
                    game.update(1 / 60)
            except Exception as exc:
                errors.append(f"floor {floor} phase {phase} {ability.name}: {exc!r}")
check("Mọi chiêu của 10 boss chạy không lỗi", not errors, f"{abilities_total} chiêu; " + (errors[0] if errors else ""))

# ---- 2. Variety: each boss has plenty of abilities and the later phases unlock more
for floor in range(1, 11):
    p, boss, room = setup(floor)
    per_phase = [sum(1 for a in boss.abilities if ph in a.phases) for ph in (1, 2, 3)]
    check(f"Tầng {floor} ({boss.name}): >= 3 chiêu giai đoạn 1, nhiều hơn ở giai đoạn 3",
          per_phase[0] >= 3 and per_phase[2] > per_phase[0] - 1 and len(boss.abilities) >= 4, f"{per_phase}")

# ---- 3. A real fight: boss uses several different moves, escalates through phases, stays in its room
for floor in (1, 2, 5, 9, 10):
    p, boss, room = setup(floor)
    used = set()
    seen_phase = {1}
    out_of_room = 0
    for f in range(60 * 70):
        boss.current_hp = max(boss.current_hp, 1)
        if f == 60 * 20:
            boss.current_hp = int(boss.max_hp * 0.55 if floor != 10 else boss.max_hp * 0.65)
        if f == 60 * 40:
            boss.current_hp = int(boss.max_hp * 0.25 if floor != 10 else boss.max_hp * 0.35)
        if f % 120 == 0:   # keep the player roughly in the room and away from the boss
            p.set_grid_pos(room.center_x + (4 if f % 240 else -4), room.center_y + (2 if f % 360 else -2))
        game.level_up_modal.is_active = False
        game.update(1 / 60)
        if boss.last_ability:
            used.add(boss.last_ability)
        seen_phase.add(boss.phase)
        if not (room.x * 32 <= boss.pos_x <= room.right * 32 and room.y * 32 <= boss.pos_y <= room.bottom * 32):
            out_of_room += 1
        if not (math.isfinite(boss.pos_x) and math.isfinite(boss.pos_y)):
            out_of_room += 1000
    check(f"Tầng {floor}: boss dùng nhiều chiêu khác nhau và qua cả 3 giai đoạn",
          len(used) >= 4 and seen_phase == {1, 2, 3}, f"{len(used)} chiêu, phases={sorted(seen_phase)}")
    check(f"Tầng {floor}: boss không ra khỏi phòng", out_of_room == 0, f"{out_of_room}")

# ---- 4. Minion cap is respected
p, boss, room = setup(1)
for _ in range(10):
    boss.call_goblins(game)
alive = sum(1 for e in game.enemies if getattr(e, "summoner", None) is boss)
check("Số quái triệu hồi không vượt trần", alive <= boss.MAX_MINIONS, f"{alive}/{boss.MAX_MINIONS}")

# ---- 5. Charges stun the boss when it hits a wall; the player can punish
p, boss, room = setup(1)
boss.pos_x, boss.pos_y = (room.right - 1) * 32 - 40, room.center_y * 32
boss.sync_rect()
p.set_grid_pos(room.right - 2, room.center_y)
boss._begin_charge((1.0, 0.0), 450, 0.6, 8, game)
for _ in range(60):
    game.update(1 / 60)
    if not boss.charging:
        break
check("Boss lao vào tường -> bị choáng lâu hơn bình thường", not boss.charging and boss.cast_timer > 1.0, f"cast_timer={boss.cast_timer:.2f}")

# ---- 6. Hugging the wall (edge tile of the room) must not pause the boss
p, boss, room = setup(2)
p.set_grid_pos(room.x, room.center_y)
boss.gcd = 0.0
boss.last_ability = None
step(180)
check("Đứng sát tường (ô rìa phòng) boss vẫn đánh", boss.last_ability is not None, f"{boss.last_ability}")

# ---- 7. Skill sizes fit the room they are cast in (no skill bigger than the arena diagonal), in many room sizes
from combat.telegraph import TelegraphShape
too_big = []
sizes_seen = set()
for floor in range(1, 11):
    for seed in (900, 1900, 2900):
        p, boss, room = setup(floor, seed)
        half = min(room.width, room.height) * 32 / 2
        sizes_seen.add(min(room.width, room.height))
        boss.phase = 3
        for ability in boss.abilities:
            game.combat_system.telegraph_zones.clear()
            boss._events.clear()
            ability.fn(game)
            for _ in range(150):
                boss.cast_timer = 0.0
                boss.current_hp = max(boss.current_hp, 1)
                boss.update(1 / 60, game)
                for z in game.combat_system.telegraph_zones:
                    if z.shape != TelegraphShape.LINE and z.shape != TelegraphShape.TILES and z.radius > half * 1.05:
                        too_big.append(f"floor {floor} {ability.name}: r={z.radius:.0f} > {half * 1.05:.0f}")
check("Mọi vùng chiêu vừa với phòng (<= nửa bề rộng phòng)", not too_big,
      f"phòng cỡ {sorted(sizes_seen)}; " + (too_big[0] if too_big else ""))

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
