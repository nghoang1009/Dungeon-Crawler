import pygame
import math
import random
from entities.base import Entity
from ai.state_machine import StateMachine
from ai.states import IdleState, PatrolState, ChaseState, KeepDistanceState, AttackState, HurtState, DeadState, EnemyState
from ai.pathfinding import AStarPathfinder
from core.animation import Animator
from core.sprite_loader import SpriteSheetLoader
from core.collision import CollisionSystem
from settings import TILE_SIZE, ENEMY_EXP_REWARDS, ENEMY_PATHFIND_COOLDOWN, flip_for

class Enemy(Entity):
    """
    Real-Time 2D Grid-Based Enemy driven by FSM and periodic A* pathfinding.
    Renders direct pixel-art sprites from monsters.png.
    """
    def __init__(self, grid_x: int, grid_y: int, enemy_type: str = "goblin", width: int = 32, height: int = 32):
        super().__init__(grid_x, grid_y, width, height)
        self.enemy_type = enemy_type
        self.is_ranged = False
        self.home_room = None  # Room this enemy belongs to; it never leaves its bounds
        self.slow_timer = 0.0
        self._slow_factor = 1.0

        self.detect_range = 240.0
        self.attack_range = 42.0
        self.exp_reward = ENEMY_EXP_REWARDS.get(enemy_type, 20)

        self.path: list[tuple[int, int]] = []
        self.path_target_tile: tuple[int, int] | None = None
        self.path_recalc_timer = 0.0

        sprite_loader = SpriteSheetLoader()
        sprite_loader.initialize()
        frames = sprite_loader.get_enemy_frames(self.enemy_type, width)
        self.animator = Animator(frames, default_state="idle", fps=7.0)
        self.flip_x = False

        self.state_machine = StateMachine(self)
        self.state_machine.add_state(IdleState())
        self.state_machine.add_state(PatrolState())
        self.state_machine.add_state(ChaseState())
        self.state_machine.add_state(KeepDistanceState())
        self.state_machine.add_state(AttackState())
        self.state_machine.add_state(HurtState())
        self.state_machine.add_state(DeadState())

        self.state_machine.change_state(EnemyState.IDLE)
        self.sync_rect()

    def apply_slow(self, factor: float, duration: float):
        """Slows movement by `factor` for `duration` seconds. Re-applying only refreshes the timer (no stacking)."""
        if self.slow_timer <= 0:
            self._slow_factor = factor
            self.speed *= factor
        self.slow_timer = duration

    def _tick_slow(self, dt: float):
        if self.slow_timer > 0:
            self.slow_timer -= dt
            if self.slow_timer <= 0:
                self.speed /= self._slow_factor
                self._slow_factor = 1.0

    def confine_to_home_room(self):
        """Keeps the enemy inside its own room so it cannot chase the player out and get stranded
        outside when the room's doors lock."""
        room = self.home_room
        if room is None or not self.is_alive:
            return

        half_w = self.rect.width / 2
        half_h = self.rect.height / 2
        min_x, max_x = room.x * TILE_SIZE + half_w, room.right * TILE_SIZE - half_w
        min_y, max_y = room.y * TILE_SIZE + half_h, room.bottom * TILE_SIZE - half_h
        x = min(max(self.pos_x, min_x), max_x)
        y = min(max(self.pos_y, min_y), max_y)
        if x != self.pos_x or y != self.pos_y:
            self.pos_x, self.pos_y = x, y
            self.path = []
            self.sync_rect()

    def get_distance_to(self, target) -> float:
        tx = target.pos_x if hasattr(target, "pos_x") else target.rect.centerx
        ty = target.pos_y if hasattr(target, "pos_y") else target.rect.centery
        return math.hypot(tx - self.pos_x, ty - self.pos_y)

    def has_line_of_sight(self, target, tilemap, obstacles=None, closed_gates=None) -> bool:
        return tilemap.has_line_of_sight(self.grid_x, self.grid_y, target.grid_x, target.grid_y, obstacles, closed_gates)

    def update_path_to_target(self, target_world_pos: tuple[float, float], dt: float, tilemap, obstacles=None, closed_gates=None):
        self.path_recalc_timer -= dt
        target_tx = int(target_world_pos[0] // TILE_SIZE)
        target_ty = int(target_world_pos[1] // TILE_SIZE)

        if self.path_recalc_timer <= 0 or self.path_target_tile != (target_tx, target_ty):
            self.path_recalc_timer = ENEMY_PATHFIND_COOLDOWN + random.uniform(0.0, 0.08)
            self.path_target_tile = (target_tx, target_ty)
            self.path = AStarPathfinder.find_path(
                (self.grid_x, self.grid_y), (target_tx, target_ty), tilemap, obstacles, closed_gates
            )

    def follow_current_path(self, dt: float, tilemap, obstacles=None):
        if not self.path:
            return

        next_tile = self.path[0]
        target_wx = next_tile[0] * TILE_SIZE + TILE_SIZE // 2
        target_wy = next_tile[1] * TILE_SIZE + TILE_SIZE // 2

        dx = target_wx - self.pos_x
        dy = target_wy - self.pos_y
        dist = math.hypot(dx, dy)

        if dist < 8.0:
            self.path.pop(0)
        else:
            self.move_toward_world(target_wx, target_wy, self.speed, dt, tilemap, obstacles)

    def move_toward_world(self, wx: float, wy: float, speed: float, dt: float, tilemap, obstacles=None):
        dx = wx - self.pos_x
        dy = wy - self.pos_y
        dist = math.hypot(dx, dy)
        if dist > 0:
            nx = (dx / dist) * speed * dt
            ny = (dy / dist) * speed * dt
            CollisionSystem.move_and_slide(self, nx, ny, tilemap, obstacles)
            self.facing_dir = (dx / dist, dy / dist)
            self.flip_x = flip_for(dx, self.flip_x)

    def take_damage(self, amount: int):
        super().take_damage(amount)
        if self.current_hp <= 0:
            self.is_alive = False
            self.state_machine.change_state(EnemyState.DEAD)
        else:
            if self.state_machine.current_state_name != EnemyState.DEAD:
                self.state_machine.change_state(EnemyState.HURT)

    def on_death(self):
        pass

    def update(self, dt: float, game_context):
        self._tick_slow(dt)
        self.sync_rect()
        self.animator.update(dt)
        self.state_machine.update(dt, game_context)
        self.confine_to_home_room()

        if self.animator.current_state in ("attack", "hurt") and self.animator.is_finished:
            self.animator.change_state("idle")

    def render(self, surface: pygame.Surface, camera):
        screen_rect = camera.apply(self.rect)
        frame = self.animator.get_current_frame(flip_x=self.flip_x)
        surface.blit(frame, (screen_rect.x, screen_rect.y))

        if self.is_alive and self.current_hp < self.max_hp:
            bar_w = 26
            bar_h = 3
            bx = screen_rect.centerx - bar_w // 2
            by = screen_rect.top - 6
            pct = max(0.0, min(1.0, self.current_hp / self.max_hp))
            pygame.draw.rect(surface, (50, 10, 10), (bx, by, bar_w, bar_h))
            pygame.draw.rect(surface, (220, 40, 40), (bx, by, int(bar_w * pct), bar_h))


    def init_stats(self, base_hp: int, base_dmg: int, defense: int, speed: float,
                   score_reward: int, difficulty_mod: dict | None = None,
                   attack_range: float = 42.0, detect_range: float = 240.0):
        """Initializes and scales enemy attributes cleanly according to difficulty modifiers."""
        hp_mult = difficulty_mod.get("enemy_hp", 1.0) if difficulty_mod else 1.0
        dmg_mult = difficulty_mod.get("enemy_dmg", 1.0) if difficulty_mod else 1.0

        self.max_hp = max(1, int(base_hp * hp_mult))
        self.current_hp = self.max_hp
        self.attack_power = max(1, int(base_dmg * dmg_mult))
        self.defense = defense
        self.speed = speed
        self.attack_range = attack_range
        self.detect_range = detect_range
        self.score_reward = score_reward


# 3 Melee Enemies
class Goblin(Enemy):
    def __init__(self, grid_x: int, grid_y: int, difficulty_mod: dict = None):
        super().__init__(grid_x, grid_y, enemy_type="goblin", width=32, height=32)
        self.init_stats(base_hp=35, base_dmg=8, defense=0, speed=135.0, score_reward=100, difficulty_mod=difficulty_mod)


class Skeleton(Enemy):
    def __init__(self, grid_x: int, grid_y: int, difficulty_mod: dict = None):
        super().__init__(grid_x, grid_y, enemy_type="skeleton", width=32, height=32)
        self.init_stats(base_hp=60, base_dmg=14, defense=2, speed=95.0, score_reward=150, difficulty_mod=difficulty_mod)


class Orc(Enemy):
    def __init__(self, grid_x: int, grid_y: int, difficulty_mod: dict = None):
        super().__init__(grid_x, grid_y, enemy_type="orc", width=36, height=36)
        self.init_stats(base_hp=120, base_dmg=24, defense=4, speed=75.0, score_reward=250, attack_range=46.0, difficulty_mod=difficulty_mod)


# 2 Ranged Enemies
class ArcherEnemy(Enemy):
    def __init__(self, grid_x: int, grid_y: int, difficulty_mod: dict = None):
        super().__init__(grid_x, grid_y, enemy_type="archer_enemy", width=32, height=32)
        self.is_ranged = True
        self.preferred_min_dist = 130.0
        self.preferred_max_dist = 240.0
        self.attack_rate = 1.6
        self.init_stats(base_hp=45, base_dmg=12, defense=1, speed=110.0, score_reward=200, detect_range=280.0, difficulty_mod=difficulty_mod)


class MageEnemy(Enemy):
    def __init__(self, grid_x: int, grid_y: int, difficulty_mod: dict = None):
        super().__init__(grid_x, grid_y, enemy_type="mage_enemy", width=32, height=32)
        self.is_ranged = True
        self.preferred_min_dist = 140.0
        self.preferred_max_dist = 260.0
        self.attack_rate = 2.2
        self.init_stats(base_hp=50, base_dmg=22, defense=0, speed=85.0, score_reward=300, detect_range=300.0, difficulty_mod=difficulty_mod)


# Area Hazard Enemies
class PoisonSlime(Enemy):
    """Area / Poison Enemy: Inflicts poison on melee strike, spawns hazard pool on death."""
    def __init__(self, grid_x: int, grid_y: int, difficulty_mod: dict = None):
        super().__init__(grid_x, grid_y, enemy_type="poison_slime", width=32, height=32)
        self.status_inflict = "poison"
        self.init_stats(base_hp=70, base_dmg=12, defense=1, speed=88.0, score_reward=180, attack_range=40.0, difficulty_mod=difficulty_mod)

    def on_death_context(self, game_context):
        if game_context and hasattr(game_context, "combat_system"):
            game_context.combat_system.spawn_hazard_area(self.grid_x, self.grid_y, "poison", duration=6.0)


class FireImp(Enemy):
    """Area / Burn Enemy: Ranged fireball projectile that creates burning ground hazards."""
    def __init__(self, grid_x: int, grid_y: int, difficulty_mod: dict = None):
        super().__init__(grid_x, grid_y, enemy_type="fire_imp", width=32, height=32)
        self.is_ranged = True
        self.projectile_type = "fireball"
        self.preferred_min_dist = 120.0
        self.preferred_max_dist = 230.0
        self.attack_rate = 2.0
        self.init_stats(base_hp=48, base_dmg=16, defense=0, speed=105.0, score_reward=220, detect_range=270.0, difficulty_mod=difficulty_mod)

    def on_attack(self, game_context):
        if game_context and hasattr(game_context, "combat_system") and random.random() < 0.40:
            game_context.combat_system.spawn_hazard_area(self.grid_x, self.grid_y, "burn", duration=5.0)
