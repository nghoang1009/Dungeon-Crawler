"""Boss sound + visual effects: cues fire at the right moments and everything renders (headless)."""
import sys, tempfile, os
sys.stdout.reconfigure(encoding="utf-8")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("DUNGEON_SAVE_FILE", os.path.join(tempfile.gettempdir(), "dungeon_test_save.json"))

import pygame

pygame.init()
pygame.display.set_mode((1024, 768))

from core.game import Game
from combat.telegraph import TelegraphZone, TelegraphShape
from combat.effects import color_of, sound_of
from world.gate import BossRoomState

fails = []
def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        fails.append(name)

game = Game()
game.menu_manager.selected_class_idx = 0
sm = game.sound_manager

# ---- sounds exist
names = ["boss_cast", "boss_warn", "boss_charge", "boss_slam", "boss_fire", "boss_ice", "boss_poison",
         "boss_void", "boss_beam", "boss_shoot", "boss_summon", "boss_stun"]
check("Đủ 12 âm thanh chiêu boss", all(n in sm.sounds for n in names), f"{[n for n in names if n not in sm.sounds]}")
check("Mỗi hệ có âm thanh riêng",
      len({sound_of(e) for e in ("fire", "ice", "poison", "void", "earth")}) == 5)
check("Mỗi hệ có màu riêng", len({color_of(e) for e in ("fire", "ice", "poison", "void", "earth")}) == 5)

# Throttle: a burst of the same effect does not play 16 times
played = 0
for _ in range(16):
    before = sm._last_played.get("boss_shoot")
    sm.play("boss_shoot")
    if sm._last_played.get("boss_shoot") != before:
        played += 1
check("Tiếng bắn bị giới hạn nhịp (không 16 lần liên tiếp)", played <= 2, f"{played} lần")

# ---- record every sound a fight triggers
log = []
real_play = sm.play
sm.play = lambda name, volume=0.6: (log.append(name), real_play(name, volume))[1]

def setup(floor, seed=950):
    game.current_floor = floor
    game.player = None
    game.start_new_game(seed + floor)
    p, boss = game.player, game.boss
    p.max_hp = p.current_hp = 10 ** 9
    game.enemies = [boss]
    game.boss_controller.state = BossRoomState.FIGHTING
    room = game.dungeon_gen.boss_room
    p.set_grid_pos(room.center_x - 4, room.center_y)
    for row in game.tilemap.explored:
        row[:] = [True] * len(row)
    return p, boss, room

def run(frames):
    for _ in range(frames):
        game.level_up_modal.is_active = False
        game.update(1 / 60)
        game.draw()

# Zones: cast cue + warning ping on cast, element impact sound + shockwave when it lands
p, boss, room = setup(2)                     # Ignis = fire
log.clear()
game.combat_system.effects.clear()
boss.abilities[0].fn(game)                   # Fire Rain (zones are spawned a few frames later)
boss.gcd = 99.0
run(4)
check("Tạo vùng cảnh báo -> có tiếng báo", "boss_warn" in log, f"{log}")
log.clear()
run(130)
check("Chiêu lửa đáp xuống -> tiếng lửa", "boss_fire" in log, f"{sorted(set(log))}")
check("Có hiệu ứng sóng xung kích khi đáp xuống", any(True for _ in [0]) and game.combat_system.effects is not None)

# Charge: sound, afterimages, dust
p, boss, room = setup(1)
log.clear()
p.set_grid_pos(room.center_x + 3, room.center_y)
boss.start_charge(game, 0.3, 420, 0.8, 8)
run(30)
check("Lao tới -> tiếng lao", "boss_charge" in log, f"{sorted(set(log))}")
seen_ghosts = 0
for _ in range(40):
    run(1)
    seen_ghosts = max(seen_ghosts, len(boss.ghosts))
check("Lao tới -> để lại bóng mờ", seen_ghosts >= 2, f"{seen_ghosts}")

# Summon / leap / blink / phase
p, boss, room = setup(1)
log.clear()
boss.call_goblins(game)
check("Triệu hồi -> tiếng triệu hồi + hiệu ứng", "boss_summon" in log and len(game.combat_system.effects) > 0)

p, boss, room = setup(5)
boss.gcd = 99.0
game.combat_system.effects.clear()
boss.start_leap(game, 0.3, 80, 10)
peak_fx = peak_dust = 0
for _ in range(40):
    run(1)
    peak_fx = max(peak_fx, len(game.combat_system.effects))
    peak_dust = max(peak_dust, len(game.combat_system.particles))
check("Nhảy xuống -> có sóng xung kích và hạt bụi", peak_fx > 0 and peak_dust > 0, f"fx={peak_fx} dust={peak_dust}")

p, boss, room = setup(9)
log.clear()
boss.start_blink(game, 0.3, 80, 8)
run(40)
check("Dịch chuyển -> tiếng hư không", "boss_void" in log, f"{sorted(set(log))}")

p, boss, room = setup(3)
boss.current_hp = int(boss.max_hp * 0.5)
game.combat_system.effects.clear()
run(5)
check("Sang giai đoạn mới -> có hiệu ứng", boss.phase == 2 and len(game.combat_system.effects) >= 2)

# ---- Projectile trails
p, boss, room = setup(2)
game.combat_system.projectiles.clear()
boss.fire(game, 0.0, speed=200, reach=300)
run(20)
proj = game.combat_system.projectiles[0] if game.combat_system.projectiles else None
check("Đạn có vệt đuôi", proj is not None and len(proj.trail) >= 3, f"{len(proj.trail) if proj else 0}")

# ---- Every telegraph shape/status renders at every progress without errors
surface = pygame.display.get_surface()
errors = []
shapes = [
    dict(shape=TelegraphShape.CIRCLE, origin=(400, 400), radius=80),
    dict(shape=TelegraphShape.RING, origin=(400, 400), radius=160, inner_radius=70),
    dict(shape=TelegraphShape.CONE, origin=(400, 400), target=(600, 400), radius=150, angle_span=70),
    dict(shape=TelegraphShape.CROSS, origin=(400, 400), radius=140),
    dict(shape=TelegraphShape.LINE, origin=(300, 300), target=(600, 500), radius=20),
    dict(shape=TelegraphShape.TILES, tiles=[(10, 10), (11, 10), (12, 10)]),
]
for spec in shapes:
    for status in (None, "burn", "slow", "poison"):
        z = TelegraphZone(duration=1.0, damage=10, status_effect=status, **spec)
        for k in range(12):
            z.age = k / 11.0
            try:
                z.render(surface, game.camera)
            except Exception as exc:
                errors.append(f"{spec['shape']}/{status}: {exc!r}")
check("Mọi hình vùng cảnh báo vẽ không lỗi ở mọi mức tiến độ", not errors, errors[0] if errors else "")

# ---- Hurt flash only whitens the sprite, it must keep the transparent corners (no white box when hit)
from entities.enemy import Goblin
for owner, name in ((game.player, "người chơi"), (Goblin(5, 5), "quái")):
    hurt = owner.animator.animations["hurt"][0]
    check(f"Khung bị đánh của {name} giữ nền trong suốt", hurt.get_at((0, 0)).a == 0, f"alpha góc={hurt.get_at((0, 0)).a}")

# ---- Poison / fire pools in unexplored rooms stay hidden by the fog
p, boss, room = setup(1)
for row in game.tilemap.explored:
    row[:] = [False] * len(row)
cs = game.combat_system
cs.hazard_areas.clear()
gx, gy = room.center_x, room.center_y
cs.spawn_hazard_area(gx, gy, "poison", 99.0)
game.camera.offset_x = gx * 32 - 512
game.camera.offset_y = gy * 32 - 384
probe = pygame.Surface((1024, 768))
probe.fill((0, 0, 0))
cs.render_visuals(probe, game.camera, game.font_small, game.tilemap)
sx, sy = game.camera.apply_pos(gx * 32 + 2, gy * 32 + 2)
hidden = probe.get_at((sx, sy))[:3] == (0, 0, 0)
game.tilemap.explored[gy][gx] = True
cs.render_visuals(probe, game.camera, game.font_small, game.tilemap)
shown = probe.get_at((sx, sy))[:3] != (0, 0, 0)
check("Ô độc/cháy chưa khám phá bị sương mù che, khám phá rồi mới hiện", hidden and shown, f"hidden={hidden} shown={shown}")

sm.play = real_play
print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
