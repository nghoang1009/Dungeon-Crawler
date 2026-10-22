import math
import random
import pygame
from entities.enemy import Enemy, Goblin, Skeleton, Orc, ArcherEnemy
from core.animation import Animator
from core.collision import CollisionSystem
from core.sprite_loader import SpriteSheetLoader
from settings import TILE_SIZE, ENEMY_EXP_REWARDS
from combat.telegraph import TelegraphZone, TelegraphShape
from combat.projectile import Projectile, HomingProjectile
from combat.damage import DamageNumber
from combat.combat_system import HitParticle
from combat.effects import GhostImage, color_of, pulse

# Skill sizes below are written for an arena whose half-width is ARENA_REF px (about a 20-tile room); in smaller
# or larger rooms every radius / reach / spread is scaled by Boss.fx so a skill always fits the room it is cast in.
ARENA_REF = 330.0
FX_MIN, FX_MAX = 0.5, 1.0

COLOR_CAST = (255, 190, 90)
COLOR_PHASE = (255, 90, 90)


class BossType:
    TYPE_A_STATIONARY = "TYPE_A_STATIONARY"  # Stationary / Ranged AoE Boss
    TYPE_B_MELEE_CHASER = "TYPE_B_MELEE_CHASER"  # Melee pursuit & charge Boss


class Ability:
    """
    One boss move. The boss picks among the abilities that are off cooldown, allowed in its current phase and
    in range, never the same one twice in a row. `commit` is how long the boss stands still casting it.
    """
    def __init__(self, name: str, fn, cooldown: float, phases=(1, 2, 3), min_range: float = 0.0,
                 max_range: float = 9999.0, weight: float = 1.0, commit: float = 0.8):
        self.name = name
        self.fn = fn
        self.cooldown = cooldown
        self.phases = phases
        self.min_range = min_range
        self.max_range = max_range
        self.weight = weight
        self.commit = commit


class Boss(Enemy):
    """
    Base Boss Entity strictly bounded within Boss Room.

    Fights are ability driven: every few seconds the boss picks a move (telegraphed areas, projectile patterns,
    charges, leaps, summons...), gets faster and meaner in phases 2 and 3, and is rooted while it casts so every
    move can be read and dodged ("Read -> Dodge -> Punish"). Subclasses only define their `build_abilities`.
    """
    ELEMENT = "dark"                          # fire / ice / poison / void / earth / dark: colours the aura, sounds, impacts
    PHASE_THRESHOLDS = (0.60, 0.30)           # hp ratio at which phase 2 and phase 3 begin
    SPEED_PER_PHASE = (1.0, 1.15, 1.30)
    GCD_PER_PHASE = (2.0, 1.5, 1.1)           # pause between two abilities
    MAX_MINIONS = 4

    def __init__(self, grid_x: int, grid_y: int, name: str, boss_type: str, sprite_name: str, width: int = 48, height: int = 48, difficulty_mod: dict = None, floor: int = 1):
        super().__init__(grid_x, grid_y, enemy_type="boss", width=width, height=height)
        self.name = name
        self.boss_type = boss_type
        self.sprite_name = sprite_name
        self.floor = floor

        hp_mult = difficulty_mod.get("boss_hp", 1.0) if difficulty_mod else 1.0
        dmg_mult = difficulty_mod.get("boss_dmg", 1.0) if difficulty_mod else 1.0
        floor_scale = 1.0 + (floor - 1) * 0.22

        base_hp = 300 + floor * 80
        self.max_hp = int(base_hp * hp_mult * floor_scale)
        self.current_hp = self.max_hp
        self.attack_power = int((16 + floor * 3) * dmg_mult)
        self.defense = 3 + floor // 2
        self.speed = 70.0 + min(35.0, floor * 3.5)
        self.detect_range = 500.0
        self.attack_range = max(60.0, width * 0.8)
        self.exp_reward = ENEMY_EXP_REWARDS.get("boss", 150) + floor * 40
        self.score_reward = 2000 if floor < 10 else 10000

        self.phase = 1
        self.skill_cooldown = 3.0      # kept for compatibility with older code / tests
        self.attack_cooldown = 1.5

        # Ability system state
        self.abilities: list[Ability] = []
        self.ability_cd: dict[str, float] = {}
        self.last_ability: str | None = None
        self.gcd = 1.6                 # first move comes a moment after the fight starts
        self.cast_timer = 0.0          # > 0: rooted, casting / recovering
        self._events: list[list] = []  # [seconds_left, callable]
        self.charging = False
        self.charge_dir = (1.0, 0.0)
        self.charge_speed = 0.0
        self.charge_timer = 0.0
        self.charge_damage = 0
        self.charge_hit = False
        self.ghosts: list[GhostImage] = []   # charge afterimages
        self._ghost_timer = 0.0

        # Entity.hitbox is sized for 32px sprites; scale it to the boss body so hits and walls match what is drawn.
        self.hitbox.size = (int(width * 0.6), int(height * 0.5))
        self.sync_rect()

        sprite_loader = SpriteSheetLoader()
        sprite_loader.initialize()
        boss_frames = sprite_loader.get_enemy_frames(sprite_name, width)
        self.animator = Animator(boss_frames, default_state="idle", fps=6.0)

    # ------------------------------------------------------------------ hooks for subclasses
    def build_abilities(self) -> list[Ability]:
        return []

    def on_phase_change(self, new_phase: int, game_context):
        """Optional extra changes when a phase starts."""

    def boss_behavior(self, dt: float, game_context):
        """Optional per-frame behaviour (the ability system already runs before this)."""

    # ------------------------------------------------------------------ core loop
    def take_damage(self, amount: int):
        super().take_damage(amount)
        if self.current_hp <= 0:
            self.is_alive = False
            self.state_machine.change_state("DEAD")

    def encounter_active(self, game_context) -> bool:
        """The boss only fights while the room is locked with the player inside it. Before that (player outside,
        entering, announcement) it idles, so no skill, projectile or minion ever reaches someone outside the room."""
        ctrl = game_context.boss_controller
        if ctrl is None:
            return True
        player = game_context.player
        # Whole room floor counts (edge tiles too), otherwise hugging a wall would freeze the boss
        if ctrl.state != "FIGHTING":
            return False
        room = self.home_room
        return room is None or room.is_pos_inside(player.grid_x, player.grid_y)

    def update(self, dt: float, game_context):
        for g in self.ghosts:
            g.update(dt)
        self.ghosts = [g for g in self.ghosts if g.is_alive]

        if not self.is_alive:
            self.animator.update(dt)
            return

        if not self.encounter_active(game_context):
            self.animator.update(dt)
            self.sync_rect()
            return

        self._update_phase(game_context)
        self._run_events(dt)

        if self.charging:
            self._update_charge(dt, game_context)
            self._finish_frame(dt, game_context)
            return

        self.gcd -= dt
        for key in self.ability_cd:
            self.ability_cd[key] -= dt

        if self.cast_timer > 0:
            self.cast_timer -= dt
            if self.animator.current_state != "telegraph":
                self.animator.change_state("telegraph")
            self._finish_frame(dt, game_context)
            return
        if self.animator.current_state == "telegraph":
            self.animator.change_state("idle")

        self._pick_ability(game_context)
        self.boss_behavior(dt, game_context)

        super().update(dt, game_context)

        # Strictly clamp inside Boss Room
        if game_context.boss_controller:
            game_context.boss_controller.clamp_boss_position(self)

    def _finish_frame(self, dt: float, game_context):
        self.animator.update(dt)
        self.sync_rect()
        if game_context.boss_controller:
            game_context.boss_controller.clamp_boss_position(self)

    # ------------------------------------------------------------------ phases
    def _update_phase(self, game_context):
        ratio = self.current_hp / max(1, self.max_hp)
        new_phase = 1 + sum(1 for t in self.PHASE_THRESHOLDS if ratio <= t)
        if new_phase <= self.phase:
            return
        old = self.phase
        self.phase = new_phase
        self.speed *= self.SPEED_PER_PHASE[new_phase - 1] / self.SPEED_PER_PHASE[old - 1]
        self.gcd = 1.0
        self.cast_timer = 0.0
        self._events.clear()
        self.charging = False
        self.say(game_context, f"PHASE {new_phase}!", COLOR_PHASE)
        color = color_of(self.ELEMENT)
        game_context.combat_system.spawn_shockwave(self.pos_x, self.pos_y, 150 * self.fx, color, 0.8)
        game_context.combat_system.spawn_shockwave(self.pos_x, self.pos_y, 90 * self.fx, (255, 255, 255), 0.5, filled=False)
        if game_context.sound_manager:
            game_context.sound_manager.play("boss_roar")
        if game_context.camera:
            game_context.camera.add_shake(duration=0.6, magnitude=10.0)
        self.on_phase_change(new_phase, game_context)

    def _pick_ability(self, game_context):
        if self.gcd > 0 or not self.abilities:
            return
        dist = self.get_distance_to(game_context.player)
        usable = [a for a in self.abilities
                  if self.phase in a.phases and self.ability_cd.get(a.name, 0.0) <= 0.0
                  and a.min_range <= dist <= a.max_range]
        if not usable:
            self.gcd = 0.3
            return
        pool = [a for a in usable if a.name != self.last_ability] or usable
        ability = random.choices(pool, weights=[a.weight for a in pool])[0]
        self.ability_cd[ability.name] = ability.cooldown
        self.last_ability = ability.name
        self.cast_timer = ability.commit
        self.gcd = ability.commit + self.GCD_PER_PHASE[self.phase - 1]
        self.say(game_context, ability.name.upper() + "!", COLOR_CAST)
        if game_context.sound_manager:
            game_context.sound_manager.play("boss_cast", 0.45)
        ability.fn(game_context)

    # ------------------------------------------------------------------ helpers for abilities
    @property
    def fx(self) -> float:
        """Skill size multiplier derived from the boss room, so big skills never outgrow a small arena."""
        room = self.home_room
        if room is None:
            return 1.0
        half = min(room.width, room.height) * TILE_SIZE / 2.0
        return max(FX_MIN, min(FX_MAX, half / ARENA_REF))

    def s(self, distance: float) -> float:
        return distance * self.fx

    def say(self, game_context, text: str, color=COLOR_CAST):
        game_context.combat_system.damage_numbers.append(
            DamageNumber(self.pos_x, self.rect.top - 28, text, color, is_crit=True))

    def schedule(self, delay: float, fn):
        self._events.append([delay, fn])

    def _run_events(self, dt: float):
        due = []
        for ev in self._events:
            ev[0] -= dt
            if ev[0] <= 0:
                due.append(ev)
        for ev in due:
            self._events.remove(ev)
            if self.is_alive:
                ev[1]()

    def dmg(self, bonus: int = 0) -> int:
        return int(self.attack_power + bonus)

    def aim(self, game_context) -> float:
        p = game_context.player
        return math.atan2(p.pos_y - self.pos_y, p.pos_x - self.pos_x)

    def zone(self, game_context, shape, duration: float, bonus: int | None, origin=None, target=None,
             radius: float = 48.0, status=None, **kwargs) -> TelegraphZone:
        """Adds a telegraph. `bonus=None` makes it a harmless warning (used by charges)."""
        if shape != TelegraphShape.LINE:       # a line's radius is its width; its length comes from `target`
            radius = self.s(radius)
            if "inner_radius" in kwargs:
                kwargs["inner_radius"] = self.s(kwargs["inner_radius"])
        z = TelegraphZone(duration=duration, damage=0 if bonus is None else self.dmg(bonus), shape=shape,
                          origin=origin, target=target, radius=radius, status_effect=status, **kwargs)
        z.element = self.ELEMENT
        game_context.combat_system.telegraph_zones.append(z)
        if game_context.sound_manager:
            game_context.sound_manager.play("boss_warn", 0.35)
        return z

    def circle_at_player(self, game_context, duration: float, bonus: int, radius: float, status=None):
        p = game_context.player
        return self.zone(game_context, TelegraphShape.CIRCLE, duration, bonus, origin=(p.pos_x, p.pos_y),
                         radius=radius, status=status)

    def fire(self, game_context, angle: float, speed: float = 240.0, reach: float = 320.0, scale: float = 0.9,
             kind: str = "enemy_magic", homing: bool = False, turn: float = 1.4):
        dx, dy = math.cos(angle), math.sin(angle)
        reach = self.s(reach)
        damage = max(1, int(self.attack_power * scale))
        if homing:
            proj = HomingProjectile(self.pos_x, self.pos_y, dx, dy, damage=damage, speed=speed, range_px=reach,
                                    owner="enemy", proj_type=kind, target=game_context.player, turn_rate=turn)
        else:
            proj = Projectile(self.pos_x, self.pos_y, dx, dy, damage=damage, speed=speed, range_px=reach,
                              owner="enemy", proj_type=kind)
        game_context.combat_system.projectiles.append(proj)
        if game_context.sound_manager:
            game_context.sound_manager.play("boss_beam" if kind == "fireball" else "boss_shoot", 0.3)

    def ring(self, game_context, count: int = 12, offset: float = 0.0, **kw):
        for i in range(count):
            self.fire(game_context, offset + i * 2 * math.pi / count, **kw)

    def fan(self, game_context, count: int, spread_deg: float, **kw):
        base = self.aim(game_context)
        for i in range(count):
            t = 0.0 if count == 1 else (i / (count - 1) - 0.5)
            self.fire(game_context, base + math.radians(spread_deg) * t, **kw)

    def spiral(self, game_context, shots: int, interval: float, step_deg: float = 22.0, arms: int = 1, **kw):
        base = self.aim(game_context)
        for i in range(shots):
            for arm in range(arms):
                ang = base + math.radians(step_deg) * i + arm * 2 * math.pi / arms
                self.schedule(i * interval, lambda a=ang: self.fire(game_context, a, **kw))

    def room_bounds(self) -> tuple[float, float, float, float]:
        r = self.home_room
        return ((r.x + 1) * TILE_SIZE + 24, (r.y + 1) * TILE_SIZE + 24,
                (r.right - 1) * TILE_SIZE - 24, (r.bottom - 1) * TILE_SIZE - 24)

    def random_point(self, around=None, spread: float = 0.0) -> tuple[float, float]:
        x0, y0, x1, y1 = self.room_bounds()
        if around is not None:
            spread = self.s(spread)
            x = around[0] + random.uniform(-spread, spread)
            y = around[1] + random.uniform(-spread, spread)
            return (min(max(x, x0), x1), min(max(y, y0), y1))
        return (random.uniform(x0, x1), random.uniform(y0, y1))

    def hazard_at(self, game_context, point, kind: str = "poison", duration: float = 7.0):
        game_context.combat_system.spawn_hazard_area(int(point[0] // TILE_SIZE), int(point[1] // TILE_SIZE), kind, duration)

    def summon(self, game_context, cls, count: int, radius: float = 80.0):
        alive = sum(1 for e in game_context.enemies if getattr(e, "summoner", None) is self and e.is_alive)
        n = min(count, self.MAX_MINIONS - alive)
        for k in range(max(0, n)):
            for attempt in range(8):
                ang = random.uniform(0, 2 * math.pi) if attempt else k * 2 * math.pi / max(1, n)
                tx = int((self.pos_x + math.cos(ang) * radius) // TILE_SIZE)
                ty = int((self.pos_y + math.sin(ang) * radius) // TILE_SIZE)
                if game_context.tilemap.is_walkable(tx, ty, game_context.obstacles, game_context.boss_gates):
                    minion = cls(tx, ty)
                    minion.home_room = self.home_room
                    minion.summoner = self
                    game_context.enemies.append(minion)
                    game_context.combat_system.spawn_shockwave(minion.pos_x, minion.pos_y, 36, color_of(self.ELEMENT), 0.5)
                    break
        if n > 0 and game_context.sound_manager:
            game_context.sound_manager.play("boss_summon", 0.5)

    def tile_rows(self, parity: int) -> list[tuple[int, int]]:
        r = self.home_room
        return [(tx, ty) for ty in range(r.y + 1, r.bottom - 1) if (ty + parity) % 2 == 0
                for tx in range(r.x + 1, r.right - 1)]

    def tile_columns(self, parity: int) -> list[tuple[int, int]]:
        r = self.home_room
        return [(tx, ty) for tx in range(r.x + 1, r.right - 1) if (tx + parity) % 2 == 0
                for ty in range(r.y + 1, r.bottom - 1)]

    def render(self, surface: pygame.Surface, camera):
        for g in self.ghosts:
            g.render(surface, camera)

        if self.is_alive and (self.cast_timer > 0 or self.charging):
            # Pulsing element-coloured aura while casting / rushing
            sx, sy = camera.apply_pos(self.pos_x, self.pos_y)
            color = color_of(self.ELEMENT)
            r = int(self.width * (0.62 + 0.12 * pulse(9.0)))
            aura = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            c = (r + 2, r + 2)
            pygame.draw.circle(aura, (*color, 55), c, r)
            pygame.draw.circle(aura, (*color, 140), c, r, 3)
            surface.blit(aura, (sx - c[0], sy - c[1]))

        super().render(surface, camera)

    # -- movement abilities ---------------------------------------------------------------
    def start_charge(self, game_context, windup: float = 0.8, speed: float = 430.0, duration: float = 0.6,
                     bonus: int = 8):
        """Telegraphs a straight line, then rushes along it. Hitting a wall stuns the boss (punish window)."""
        p = game_context.player
        dx, dy = p.pos_x - self.pos_x, p.pos_y - self.pos_y
        mag = math.hypot(dx, dy) or 1.0
        direction = (dx / mag, dy / mag)
        duration *= self.fx                      # shorter rush in a smaller room
        reach = speed * duration
        end = (self.pos_x + direction[0] * reach, self.pos_y + direction[1] * reach)
        self.zone(game_context, TelegraphShape.LINE, windup, None, origin=(self.pos_x, self.pos_y), target=end,
                  radius=18 + self.width * 0.25)
        self.cast_timer = max(self.cast_timer, windup)
        self.schedule(windup, lambda: self._begin_charge(direction, speed, duration, bonus, game_context))

    def _begin_charge(self, direction, speed, duration, bonus, game_context):
        self.charging = True
        self.charge_dir = direction
        self.charge_speed = speed
        self.charge_timer = duration
        self.charge_damage = self.dmg(bonus)
        self.charge_hit = False
        self.facing_dir = direction
        self.flip_x = direction[0] > 0
        game_context.combat_system.spawn_shockwave(self.pos_x, self.pos_y, 55, color_of(self.ELEMENT), 0.35, filled=False)
        if game_context.sound_manager:
            game_context.sound_manager.play("boss_charge", 0.6)

    def _update_charge(self, dt: float, game_context):
        player = game_context.player
        step = (self.charge_dir[0] * self.charge_speed * dt, self.charge_dir[1] * self.charge_speed * dt)
        before = (self.pos_x, self.pos_y)
        self._ghost_timer -= dt
        if self._ghost_timer <= 0:       # afterimage + dust kicked up behind the rush
            self._ghost_timer = 0.035
            self.ghosts.append(GhostImage(self.pos_x, self.pos_y,
                                          self.animator.get_current_frame(flip_x=self.flip_x), (255, 150, 120)))
            game_context.combat_system.particles.append(
                HitParticle(self.pos_x - self.charge_dir[0] * 18, self.pos_y + 14, color=(190, 175, 150)))
        CollisionSystem.move_and_slide(self, step[0], step[1], game_context.tilemap, game_context.obstacles)
        if game_context.boss_controller:
            game_context.boss_controller.clamp_boss_position(self)   # the arena edge counts as a wall
        self.charge_timer -= dt

        if not self.charge_hit and self.get_hitbox().colliderect(player.get_hitbox()):
            self.charge_hit = True
            game_context.combat_system._apply_damage_to_player(player, self.charge_damage)
            CollisionSystem.apply_knockback(player, self.charge_dir[0], self.charge_dir[1], 48.0,
                                            game_context.tilemap, game_context.obstacles)

        travelled = math.hypot(self.pos_x - before[0], self.pos_y - before[1])
        blocked = travelled < 0.3 * math.hypot(*step)
        if self.charge_timer <= 0 or blocked:
            self.charging = False
            self.cast_timer = 1.1 if blocked else 0.6      # slammed into a wall: dazed, free hits for the player
            if blocked:
                self.say(game_context, "STUNNED", (190, 230, 255))
                game_context.combat_system.spawn_shockwave(self.pos_x, self.pos_y, 80, (190, 230, 255), 0.5)
                for _ in range(10):
                    game_context.combat_system.particles.append(HitParticle(self.pos_x, self.pos_y, color=(255, 240, 150)))
                if game_context.sound_manager:
                    game_context.sound_manager.play("boss_stun", 0.6)
                if game_context.camera:
                    game_context.camera.add_shake(duration=0.25, magnitude=6.0)

    def start_leap(self, game_context, windup: float = 1.0, radius: float = 80.0, bonus: int = 10, status=None,
                   hazard: str | None = None):
        """Marks the player's position, then jumps there and slams."""
        p = game_context.player
        target = self.random_point(around=(p.pos_x, p.pos_y), spread=0.0)
        self.zone(game_context, TelegraphShape.CIRCLE, windup, bonus, origin=target, radius=radius, status=status)
        self.cast_timer = max(self.cast_timer, windup + 0.2)

        def land():
            self.pos_x, self.pos_y = target
            self.sync_rect()
            game_context.combat_system.spawn_shockwave(target[0], target[1], radius * self.fx * 1.1,
                                                       color_of(self.ELEMENT), 0.5)
            for _ in range(10):
                game_context.combat_system.particles.append(HitParticle(target[0], target[1] + 12, color=(190, 175, 150)))
            if game_context.camera:
                game_context.camera.add_shake(duration=0.3, magnitude=8.0)
            if hazard:
                self.hazard_at(game_context, target, hazard)
        self.schedule(windup, land)

    def start_blink(self, game_context, windup: float = 0.9, radius: float = 80.0, bonus: int = 8, after=None):
        """Teleports to a spot near the player, damaging whoever stands there when it arrives."""
        p = game_context.player
        for _ in range(12):
            angle = random.uniform(0, 2 * math.pi)
            target = self.random_point(around=(p.pos_x + math.cos(angle) * self.s(150),
                                               p.pos_y + math.sin(angle) * self.s(150)))
            if math.hypot(target[0] - p.pos_x, target[1] - p.pos_y) > radius + 40:
                break
        self.zone(game_context, TelegraphShape.CIRCLE, windup, bonus, origin=target, radius=radius)
        self.cast_timer = max(self.cast_timer, windup + 0.1)

        departure = (self.pos_x, self.pos_y)
        game_context.combat_system.spawn_shockwave(departure[0], departure[1], 50, color_of("void"), 0.5)

        def arrive():
            self.pos_x, self.pos_y = target
            self.sync_rect()
            game_context.combat_system.spawn_shockwave(target[0], target[1], radius * self.fx, color_of("void"), 0.5)
            if game_context.sound_manager:
                game_context.sound_manager.play("boss_void", 0.6)
            if after:
                after()
        self.schedule(windup, arrive)


# ==============================================================================
# FLOOR 1: GOBLIN KING (Type B - Melee Chaser)
# ==============================================================================
class GoblinKingBoss(Boss):
    ELEMENT = "earth"
    def __init__(self, gx: int, gy: int, diff_mod: dict = None):
        super().__init__(gx, gy, "Grak the Goblin King", BossType.TYPE_B_MELEE_CHASER, "goblin brute", width=44, height=44, difficulty_mod=diff_mod, floor=1)
        self.abilities = self.build_abilities()

    def build_abilities(self):
        return [
            Ability("Club Smash", self.club_smash, 2.5, max_range=130, weight=3, commit=0.9),
            Ability("Royal Rush", lambda c: self.start_charge(c, 0.8, 400, 0.6, 8), 6.0, min_range=130, max_range=380, weight=2, commit=0.8),
            Ability("Double Rush", self.double_rush, 11.0, phases=(3,), min_range=130, weight=2, commit=2.2),
            Ability("Dagger Toss", self.dagger_toss, 6.0, phases=(2, 3), min_range=120, max_range=420, commit=0.7),
            Ability("Call Goblins", self.call_goblins, 15.0, weight=1.5, commit=0.8),
        ]

    def club_smash(self, c):
        self.zone(c, TelegraphShape.CIRCLE, 0.85, 8, origin=(self.pos_x, self.pos_y), radius=78)

    def double_rush(self, c):
        self.start_charge(c, 0.8, 420, 0.55, 8)
        self.schedule(1.7, lambda: self.start_charge(c, 0.6, 440, 0.55, 8))

    def dagger_toss(self, c):
        self.fan(c, 3 + (self.phase - 2), 40.0, speed=300.0, reach=420.0, scale=0.7, kind="arrow")

    def call_goblins(self, c):
        self.summon(c, Goblin, 2 if self.phase == 1 else 3)


# ==============================================================================
# FLOOR 2: HIGH CULTIST IGNIS (Type A - Stationary Ranged)
# ==============================================================================
class HighCultistBoss(Boss):
    ELEMENT = "fire"
    def __init__(self, gx: int, gy: int, diff_mod: dict = None):
        super().__init__(gx, gy, "Ignis the Dark Cultist", BossType.TYPE_A_STATIONARY, "red_dragon", width=60, height=60, difficulty_mod=diff_mod, floor=2)
        self.speed = 25.0  # Hovers near center
        self.abilities = self.build_abilities()

    def build_abilities(self):
        return [
            Ability("Fire Rain", self.fire_rain, 7.0, weight=2, commit=1.4),
            Ability("Ember Ring", self.ember_ring, 5.5, weight=2, commit=0.8),
            Ability("Flame Breath", self.flame_breath, 6.0, max_range=280, commit=1.0),
            Ability("Inferno Cross", self.inferno_cross, 9.0, phases=(2, 3), commit=1.1),
            Ability("Meteor Barrage", self.meteors, 12.0, phases=(3,), commit=2.0),
        ]

    def fire_rain(self, c):
        for i in range(5 + self.phase - 1):
            self.schedule(i * 0.25, lambda: self.circle_at_player(c, 0.9, 8, 48, "burn"))

    def ember_ring(self, c):
        waves = self.phase
        for w in range(waves):
            self.schedule(w * 0.55, lambda w=w: self.ring(c, 12, offset=w * math.pi / 12, speed=230, reach=300, scale=0.8))

    def flame_breath(self, c):
        p = c.player
        self.zone(c, TelegraphShape.CONE, 0.95, 10, origin=(self.pos_x, self.pos_y), target=(p.pos_x, p.pos_y),
                  radius=180, angle_span=70, status="burn")

    def inferno_cross(self, c):
        p = c.player
        self.zone(c, TelegraphShape.CROSS, 1.0, 10, origin=(p.pos_x, p.pos_y), radius=130, status="burn")
        self.zone(c, TelegraphShape.CROSS, 1.4, 10, origin=(self.pos_x, self.pos_y), radius=230, status="burn")

    def meteors(self, c):
        for i in range(8):
            def drop():
                pt = self.random_point(around=(c.player.pos_x, c.player.pos_y), spread=170)
                self.zone(c, TelegraphShape.CIRCLE, 0.9, 10, origin=pt, radius=44, status="burn")
                self.schedule(0.9, lambda pt=pt: self.hazard_at(c, pt, "burn", 5.0))
            self.schedule(i * 0.2, drop)


# ==============================================================================
# FLOOR 3: SKELETAL WARLORD (Type B - Melee Chaser)
# ==============================================================================
class SkeletalWarlordBoss(Boss):
    ELEMENT = "dark"
    def __init__(self, gx: int, gy: int, diff_mod: dict = None):
        super().__init__(gx, gy, "General Moros", BossType.TYPE_B_MELEE_CHASER, "death knight", width=46, height=46, difficulty_mod=diff_mod, floor=3)
        self.abilities = self.build_abilities()

    def build_abilities(self):
        return [
            Ability("Whirlwind", self.whirlwind, 3.0, max_range=140, weight=3, commit=0.9),
            Ability("Triple Slash", self.triple_slash, 7.0, max_range=220, weight=2, commit=1.9),
            Ability("Shield Charge", lambda c: self.start_charge(c, 0.75, 440, 0.6, 10), 6.0, min_range=140, max_range=400, weight=2, commit=0.8),
            Ability("Raise Dead", lambda c: self.summon(c, Skeleton, 2), 18.0, phases=(2, 3), commit=0.9),
            Ability("Bone Storm", self.bone_storm, 9.0, phases=(3,), commit=1.8),
        ]

    def whirlwind(self, c):
        self.zone(c, TelegraphShape.CIRCLE, 0.75, 10, origin=(self.pos_x, self.pos_y), radius=72)

    def triple_slash(self, c):
        base = self.aim(c)
        for i, off in enumerate((-35, 0, 35)):
            def slash(off=off):
                ang = base + math.radians(off)
                tgt = (self.pos_x + math.cos(ang) * 100, self.pos_y + math.sin(ang) * 100)
                self.zone(c, TelegraphShape.CONE, 0.6, 9, origin=(self.pos_x, self.pos_y), target=tgt, radius=125, angle_span=55)
            self.schedule(i * 0.55, slash)

    def bone_storm(self, c):
        for w in range(3):
            self.schedule(w * 0.5, lambda w=w: self.ring(c, 10, offset=w * math.pi / 10, speed=220, reach=340, scale=0.8, kind="arrow"))


# ==============================================================================
# FLOOR 4: FOREST SPIRIT / TREANT (Type A - Stationary Ranged)
# ==============================================================================
class ForestSpiritBoss(Boss):
    ELEMENT = "poison"
    def __init__(self, gx: int, gy: int, diff_mod: dict = None):
        super().__init__(gx, gy, "Silvanus the Corrupted", BossType.TYPE_A_STATIONARY, "green_dragon", width=90, height=90, difficulty_mod=diff_mod, floor=4)
        self.speed = 10.0
        self.abilities = self.build_abilities()

    def build_abilities(self):
        return [
            Ability("Vine Snare", self.vine_snare, 7.0, weight=2, commit=1.6),
            Ability("Spore Spiral", self.spore_spiral, 6.5, weight=2, commit=1.4),
            Ability("Root Lash", self.root_lash, 4.5, max_range=420, weight=2, commit=0.9),
            Ability("Thorn Ring", self.thorn_ring, 8.0, phases=(2, 3), commit=1.2),
            Ability("Toxic Bloom", self.toxic_bloom, 12.0, phases=(3,), commit=1.6),
        ]

    def vine_snare(self, c):
        p = c.player
        center = (p.pos_x, p.pos_y)
        n = 6
        for k in range(n):
            ang = k * 2 * math.pi / n
            pt = self.random_point(around=(center[0] + math.cos(ang) * self.s(105), center[1] + math.sin(ang) * self.s(105)))
            self.schedule(k * 0.16, lambda pt=pt: self.zone(c, TelegraphShape.CIRCLE, 0.9, 5, origin=pt, radius=42, status="poison"))
        self.schedule(1.0, lambda: self.circle_at_player(c, 0.8, 5, 50, "poison"))

    def spore_spiral(self, c):
        self.spiral(c, shots=16, interval=0.09, step_deg=24, arms=2 if self.phase >= 3 else 1,
                    speed=170, reach=380, scale=0.7, kind="poison_spit")

    def root_lash(self, c):
        ang = self.aim(c)
        end = (self.pos_x + math.cos(ang) * self.s(430), self.pos_y + math.sin(ang) * self.s(430))
        self.zone(c, TelegraphShape.LINE, 0.9, 6, origin=(self.pos_x, self.pos_y), target=end, radius=24, status="poison")

    def thorn_ring(self, c):
        self.zone(c, TelegraphShape.RING, 1.0, 8, origin=(self.pos_x, self.pos_y), radius=200, inner_radius=95, status="poison")

    def toxic_bloom(self, c):
        for i in range(4):
            def bloom():
                pt = self.random_point(around=(c.player.pos_x, c.player.pos_y), spread=140)
                self.zone(c, TelegraphShape.CIRCLE, 0.9, 6, origin=pt, radius=52, status="poison")
                self.schedule(0.9, lambda pt=pt: self.hazard_at(c, pt, "poison", 8.0))
            self.schedule(i * 0.3, bloom)


# ==============================================================================
# FLOOR 5: ORC WARCHIEF (Type B - Melee Heavy Chaser)
# ==============================================================================
class OrcWarchiefBoss(Boss):
    ELEMENT = "earth"
    def __init__(self, gx: int, gy: int, diff_mod: dict = None):
        super().__init__(gx, gy, "Gorgar Skullcrusher", BossType.TYPE_B_MELEE_CHASER, "orc warchief", width=50, height=50, difficulty_mod=diff_mod, floor=5)
        self.abilities = self.build_abilities()

    def build_abilities(self):
        return [
            Ability("Ground Slam", self.ground_slam, 3.5, max_range=230, weight=3, commit=0.9),
            Ability("Skull Leap", lambda c: self.start_leap(c, 1.0, 85, 12, "slow"), 7.5, min_range=170, max_range=420, weight=2, commit=1.4),
            Ability("Axe Charge", lambda c: self.start_charge(c, 0.8, 450, 0.6, 12), 6.5, min_range=140, max_range=420, weight=2, commit=0.8),
            Ability("War Cry", self.war_cry, 20.0, phases=(2, 3), commit=1.0),
            Ability("Earthshatter", self.earthshatter, 10.0, phases=(3,), commit=1.8),
        ]

    def ground_slam(self, c):
        p = c.player
        self.zone(c, TelegraphShape.CONE, 0.8, 12, origin=(self.pos_x, self.pos_y), target=(p.pos_x, p.pos_y),
                  radius=150, angle_span=75, status="slow")

    def war_cry(self, c):
        self.summon(c, Orc, 2)
        if c.camera:
            c.camera.add_shake(duration=0.4, magnitude=6.0)

    def earthshatter(self, c):
        o = (self.pos_x, self.pos_y)
        self.zone(c, TelegraphShape.CIRCLE, 0.85, 12, origin=o, radius=85)
        self.zone(c, TelegraphShape.RING, 1.4, 12, origin=o, radius=190, inner_radius=85, status="slow")


# ==============================================================================
# FLOOR 6: LICH QUEEN (Type A - Stationary Ranged)
# ==============================================================================
class LichQueenBoss(Boss):
    ELEMENT = "ice"
    def __init__(self, gx: int, gy: int, diff_mod: dict = None):
        super().__init__(gx, gy, "Valaria the Lich Queen", BossType.TYPE_A_STATIONARY, "golden_angel", width=90, height=90, difficulty_mod=diff_mod, floor=6)
        self.speed = 30.0
        self.abilities = self.build_abilities()

    def build_abilities(self):
        return [
            Ability("Frost Cross", self.frost_cross, 6.0, weight=2, commit=1.2),
            Ability("Soul Orbs", self.soul_orbs, 8.0, weight=2, commit=1.2),
            Ability("Frost Nova", self.frost_nova, 6.0, commit=0.8),
            Ability("Ice Star", self.ice_star, 9.0, phases=(2, 3), commit=1.5),
            Ability("Raise Archers", lambda c: self.summon(c, ArcherEnemy, 2), 18.0, phases=(2, 3), commit=0.9),
            Ability("Blizzard", self.blizzard, 11.0, phases=(3,), commit=2.0),
        ]

    def frost_cross(self, c):
        p = c.player
        self.zone(c, TelegraphShape.CROSS, 0.95, 10, origin=(p.pos_x, p.pos_y), radius=135, status="slow")
        self.zone(c, TelegraphShape.CROSS, 1.45, 10, origin=(self.pos_x, self.pos_y), radius=190, status="slow")

    def frost_nova(self, c):
        self.ring(c, 10, offset=random.uniform(0, math.pi / 5), speed=200, reach=330, scale=0.7)

    def soul_orbs(self, c):
        for i in range(2 + self.phase):
            self.schedule(i * 0.35, lambda: self.fire(c, self.aim(c) + random.uniform(-0.5, 0.5), speed=150, reach=700,
                                                      scale=0.9, kind="enemy_magic", homing=True, turn=1.5))

    def ice_star(self, c):
        o = (self.pos_x, self.pos_y)
        twist = random.uniform(0, math.pi / 8)
        for k in range(8):
            ang = twist + k * math.pi / 4
            end = (o[0] + math.cos(ang) * self.s(320), o[1] + math.sin(ang) * self.s(320))
            self.schedule(k * 0.1, lambda end=end: self.zone(c, TelegraphShape.LINE, 0.85, 10, origin=o, target=end, radius=20, status="slow"))

    def blizzard(self, c):
        self.zone(c, TelegraphShape.TILES, 1.5, 10, status="slow", tiles=self.tile_rows(0))
        self.schedule(1.9, lambda: self.zone(c, TelegraphShape.TILES, 1.4, 10, status="slow", tiles=self.tile_rows(1)))


# ==============================================================================
# FLOOR 7: MANTICORE (Type B - Melee Pounce Chaser)
# ==============================================================================
class ManticoreBoss(Boss):
    ELEMENT = "poison"
    def __init__(self, gx: int, gy: int, diff_mod: dict = None):
        super().__init__(gx, gy, "Venomous Manticore", BossType.TYPE_B_MELEE_CHASER, "teal_dragon", width=60, height=60, difficulty_mod=diff_mod, floor=7)
        self.abilities = self.build_abilities()

    def build_abilities(self):
        return [
            Ability("Stinger Cone", self.stinger, 3.2, max_range=240, weight=3, commit=0.8),
            Ability("Pounce", self.pounce, 6.5, min_range=150, max_range=420, weight=2, commit=1.2),
            Ability("Tail Volley", self.tail_volley, 5.0, min_range=110, max_range=440, weight=2, commit=0.8),
            Ability("Venom Pools", self.venom_pools, 11.0, phases=(3,), commit=1.4),
        ]

    def stinger(self, c):
        p = c.player
        self.zone(c, TelegraphShape.CONE, 0.75, 10, origin=(self.pos_x, self.pos_y), target=(p.pos_x, p.pos_y),
                  radius=160, angle_span=70, status="poison")

    def pounce(self, c):
        self.start_leap(c, 0.9, 72, 10, "poison", hazard="poison" if self.phase >= 2 else None)

    def tail_volley(self, c):
        self.fan(c, 5, 55.0, speed=290, reach=440, scale=0.75, kind="poison_spit")

    def venom_pools(self, c):
        for i in range(3):
            def pool():
                pt = self.random_point(around=(c.player.pos_x, c.player.pos_y), spread=110)
                self.zone(c, TelegraphShape.CIRCLE, 0.9, 8, origin=pt, radius=55, status="poison")
                self.schedule(0.9, lambda pt=pt: self.hazard_at(c, pt, "poison", 8.0))
            self.schedule(i * 0.35, pool)


# ==============================================================================
# FLOOR 8: GOLEM OVERLORD (Type B - Heavy Stomp Melee)
# ==============================================================================
class GolemOverlordBoss(Boss):
    ELEMENT = "earth"
    def __init__(self, gx: int, gy: int, diff_mod: dict = None):
        super().__init__(gx, gy, "Titanus the Rock Golem", BossType.TYPE_B_MELEE_CHASER, "mech_crab", width=60, height=60, difficulty_mod=diff_mod, floor=8)
        self.speed = 60.0
        self.abilities = self.build_abilities()

    def build_abilities(self):
        return [
            Ability("Quake", self.quake, 4.0, max_range=160, weight=3, commit=1.0),
            Ability("Boulder Toss", self.boulder_toss, 7.0, weight=2, commit=1.6),
            Ability("Rock Volley", self.rock_volley, 5.5, min_range=120, max_range=440, commit=0.8),
            Ability("Shock Rings", self.shock_rings, 9.0, phases=(2, 3), commit=1.7),
            Ability("Laser Cross", self.laser_cross, 10.0, phases=(3,), commit=2.0),
        ]

    def quake(self, c):
        self.zone(c, TelegraphShape.CIRCLE, 0.95, 15, origin=(self.pos_x, self.pos_y), radius=108, status="slow")

    def rock_volley(self, c):
        self.fan(c, 3, 34.0, speed=250, reach=440, scale=0.9)

    def boulder_toss(self, c):
        for i in range(3):
            self.schedule(i * 0.45, lambda: self.circle_at_player(c, 0.95, 12, 56))

    def shock_rings(self, c):
        o = (self.pos_x, self.pos_y)
        self.zone(c, TelegraphShape.CIRCLE, 0.85, 12, origin=o, radius=78)
        self.zone(c, TelegraphShape.RING, 1.35, 12, origin=o, radius=170, inner_radius=78, status="slow")

    def laser_cross(self, c):
        o = (self.pos_x, self.pos_y)
        self.zone(c, TelegraphShape.CROSS, 0.95, 14, origin=o, radius=280)
        for k in range(4):
            ang = math.pi / 4 + k * math.pi / 2
            end = (o[0] + math.cos(ang) * self.s(380), o[1] + math.sin(ang) * self.s(380))
            self.schedule(0.9, lambda end=end: self.zone(c, TelegraphShape.LINE, 0.95, 14, origin=o, target=end, radius=22))


# ==============================================================================
# FLOOR 9: VOID ARCHMAGE (Type A - Stationary Ranged)
# ==============================================================================
class VoidArchmageBoss(Boss):
    ELEMENT = "void"
    def __init__(self, gx: int, gy: int, diff_mod: dict = None):
        super().__init__(gx, gy, "Xalthor the Voidcaller", BossType.TYPE_A_STATIONARY, "void_horror", width=60, height=60, difficulty_mod=diff_mod, floor=9)
        self.speed = 30.0
        self.abilities = self.build_abilities()

    def build_abilities(self):
        return [
            Ability("Void Spiral", self.void_spiral, 6.5, weight=2, commit=1.6),
            Ability("Void Rifts", self.void_rifts, 7.0, weight=2, commit=1.4),
            Ability("Seeker Orbs", self.seeker_orbs, 8.0, commit=1.0),
            Ability("Void Step", self.void_step, 9.0, phases=(2, 3), commit=1.0),
            Ability("Collapse", self.collapse, 12.0, phases=(3,), commit=1.8),
        ]

    def void_spiral(self, c):
        self.spiral(c, shots=18, interval=0.08, step_deg=21, arms=2 if self.phase >= 2 else 1,
                    speed=210, reach=420, scale=0.8)

    def void_rifts(self, c):
        self.circle_at_player(c, 0.9, 12, 56, "slow")
        for i in range(3):
            pt = self.random_point(around=(c.player.pos_x, c.player.pos_y), spread=170)
            self.schedule(0.2 + i * 0.2, lambda pt=pt: self.zone(c, TelegraphShape.CIRCLE, 0.9, 12, origin=pt, radius=56, status="slow"))

    def seeker_orbs(self, c):
        for i in range(2):
            self.schedule(i * 0.4, lambda: self.fire(c, self.aim(c) + random.uniform(-0.6, 0.6), speed=175, reach=650,
                                                     scale=0.9, kind="enemy_magic", homing=True, turn=1.7))

    def void_step(self, c):
        after = (lambda: self.ring(c, 12, speed=230, reach=320, scale=0.7)) if self.phase >= 3 else None
        self.start_blink(c, 0.9, 85, 10, after=after)

    def collapse(self, c):
        p = c.player
        self.zone(c, TelegraphShape.CROSS, 1.0, 14, origin=(p.pos_x, p.pos_y), radius=120, status="burn")
        self.zone(c, TelegraphShape.CROSS, 1.5, 14, origin=(self.pos_x, self.pos_y), radius=230, status="burn")
        self.schedule(0.8, lambda: self.zone(c, TelegraphShape.RING, 1.3, 14, origin=(self.pos_x, self.pos_y),
                                             radius=300, inner_radius=140, status="slow"))


# ==============================================================================
# FLOOR 10: MALAKOR, FINAL ABYSS DEMON LORD (3 PHASES ULTIMATE BOSS)
# ==============================================================================
class AbyssFinalBoss(Boss):
    """
    Ultimate Floor 10 Final Boss:
    PHASE 1 (100% - 70% HP): Cleave rush, abyss slam and aimed shadow bolts
    PHASE 2 (70% - 40% HP): Hellfire breath (3 cones), fire nova waves, demon summons
    PHASE 3 (40% - 0% HP): Cataclysm rings, death-beam star, hell spiral and rapid summons
    """
    ELEMENT = "fire"
    PHASE_THRESHOLDS = (0.70, 0.40)
    SPEED_PER_PHASE = (1.0, 1.17, 1.38)
    GCD_PER_PHASE = (1.9, 1.4, 1.0)

    def __init__(self, gx: int, gy: int, diff_mod: dict = None):
        super().__init__(gx, gy, "Malakor, Abyss Overlord", BossType.TYPE_B_MELEE_CHASER, "demon_lord", width=90, height=90, difficulty_mod=diff_mod, floor=10)
        self.max_hp = int(self.max_hp * 1.5)
        self.current_hp = self.max_hp
        self.attack_power += 8
        self.speed = 90.0
        self.abilities = self.build_abilities()

    def on_phase_change(self, new_phase: int, game_context):
        self.attack_power = {2: 34, 3: 42}.get(new_phase, self.attack_power)

    def build_abilities(self):
        return [
            Ability("Cleave Rush", lambda c: self.start_charge(c, 0.75, 450, 0.6, 10), 6.0, min_range=150, max_range=420, weight=2, commit=0.8),
            Ability("Abyss Slam", self.abyss_slam, 3.5, max_range=170, weight=3, commit=1.0),
            Ability("Shadow Bolts", self.shadow_bolts, 5.0, phases=(1, 2), min_range=110, weight=2, commit=0.8),
            Ability("Hellfire Breath", self.hellfire_breath, 7.0, phases=(2,), max_range=300, weight=2, commit=1.9),
            Ability("Fire Nova", self.fire_nova, 7.0, phases=(2, 3), weight=2, commit=1.0),
            Ability("Summon Demons", self.summon_demons, 16.0, phases=(2, 3), commit=1.0),
            Ability("Cataclysm", self.cataclysm, 11.0, phases=(3,), weight=2, commit=2.1),
            Ability("Death Beams", self.death_beams, 9.0, phases=(3,), commit=1.8),
            Ability("Hell Spiral", self.hell_spiral, 8.0, phases=(3,), commit=1.8),
        ]

    def abyss_slam(self, c):
        self.zone(c, TelegraphShape.CIRCLE, 0.9, 14, origin=(self.pos_x, self.pos_y), radius=100)

    def shadow_bolts(self, c):
        self.fan(c, 3 if self.phase == 1 else 5, 40.0, speed=290, reach=450, scale=0.6)

    def hellfire_breath(self, c):
        base = self.aim(c)
        for i, off in enumerate((0, 38, -38)):
            def cone(off=off):
                ang = base + math.radians(off)
                tgt = (self.pos_x + math.cos(ang) * 100, self.pos_y + math.sin(ang) * 100)
                self.zone(c, TelegraphShape.CONE, 0.65, 12, origin=(self.pos_x, self.pos_y), target=tgt, radius=185,
                          angle_span=60, status="burn")
            self.schedule(i * 0.55, cone)

    def fire_nova(self, c):
        for w in range(2 if self.phase == 2 else 3):
            self.schedule(w * 0.5, lambda w=w: self.ring(c, 12, offset=w * math.pi / 12, speed=280, reach=360,
                                                         scale=0.65, kind="fireball"))

    def summon_demons(self, c):
        self.summon(c, Orc, 1)
        self.summon(c, ArcherEnemy, 1)

    def cataclysm(self, c):
        o = (self.pos_x, self.pos_y)
        self.zone(c, TelegraphShape.CIRCLE, 0.9, 16, origin=o, radius=105, status="burn")
        self.zone(c, TelegraphShape.RING, 1.4, 16, origin=o, radius=210, inner_radius=105, status="burn")
        self.zone(c, TelegraphShape.RING, 1.9, 16, origin=o, radius=320, inner_radius=210, status="slow")

    def death_beams(self, c):
        o = (self.pos_x, self.pos_y)
        for turn in range(2):
            twist = turn * math.pi / 8
            for k in range(8):
                ang = twist + k * math.pi / 4
                end = (o[0] + math.cos(ang) * self.s(400), o[1] + math.sin(ang) * self.s(400))
                self.schedule(turn * 0.9, lambda end=end: self.zone(c, TelegraphShape.LINE, 0.9, 14, origin=o, target=end, radius=20))

    def hell_spiral(self, c):
        self.spiral(c, shots=20, interval=0.07, step_deg=19, arms=3, speed=230, reach=440, scale=0.6, kind="fireball")


# Boss Factory
def create_boss_for_floor(floor: int, diff_mod: dict, gx: int, gy: int) -> Boss:
    boss_map = {
        1: GoblinKingBoss,
        2: HighCultistBoss,
        3: SkeletalWarlordBoss,
        4: ForestSpiritBoss,
        5: OrcWarchiefBoss,
        6: LichQueenBoss,
        7: ManticoreBoss,
        8: GolemOverlordBoss,
        9: VoidArchmageBoss,
        10: AbyssFinalBoss
    }
    boss_cls = boss_map.get(floor, AbyssFinalBoss)
    return boss_cls(gx, gy, diff_mod)
