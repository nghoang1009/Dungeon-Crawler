import math
import random
from ai.state_machine import State

class EnemyState:
    IDLE = "IDLE"
    PATROL = "PATROL"
    CHASE = "CHASE"
    KEEP_DISTANCE = "KEEP_DISTANCE"
    ATTACK = "ATTACK"
    HURT = "HURT"
    DEAD = "DEAD"


class IdleState(State):
    def __init__(self):
        super().__init__(EnemyState.IDLE)
        self.timer = 0.0

    def enter(self, entity):
        self.timer = random.uniform(1.0, 2.2)
        entity.animator.change_state("idle")

    def execute(self, entity, dt: float, game_context):
        player = game_context.player
        dist = entity.get_distance_to(player)

        if dist <= entity.detect_range and entity.has_line_of_sight(player, game_context.tilemap, game_context.obstacles, game_context.boss_gates):
            if getattr(entity, "is_ranged", False):
                entity.state_machine.change_state(EnemyState.KEEP_DISTANCE)
            else:
                entity.state_machine.change_state(EnemyState.CHASE)
            return

        self.timer -= dt
        if self.timer <= 0:
            entity.state_machine.change_state(EnemyState.PATROL)


class PatrolState(State):
    def __init__(self):
        super().__init__(EnemyState.PATROL)
        self.target_wx = 0.0
        self.target_wy = 0.0
        self.timer = 0.0

    def enter(self, entity):
        self.timer = random.uniform(2.0, 3.5)
        entity.animator.change_state("walk")
        # Wander to random nearby location
        off_x = random.uniform(-60.0, 60.0)
        off_y = random.uniform(-60.0, 60.0)
        self.target_wx = entity.pos_x + off_x
        self.target_wy = entity.pos_y + off_y

    def execute(self, entity, dt: float, game_context):
        player = game_context.player
        dist = entity.get_distance_to(player)

        if dist <= entity.detect_range and entity.has_line_of_sight(player, game_context.tilemap, game_context.obstacles, game_context.boss_gates):
            if getattr(entity, "is_ranged", False):
                entity.state_machine.change_state(EnemyState.KEEP_DISTANCE)
            else:
                entity.state_machine.change_state(EnemyState.CHASE)
            return

        self.timer -= dt
        if self.timer <= 0:
            entity.state_machine.change_state(EnemyState.IDLE)
            return

        entity.move_toward_world(self.target_wx, self.target_wy, entity.speed * 0.45, dt, game_context.tilemap, game_context.obstacles)


class ChaseState(State):
    def __init__(self):
        super().__init__(EnemyState.CHASE)

    def enter(self, entity):
        entity.animator.change_state("walk")

    def execute(self, entity, dt: float, game_context):
        player = game_context.player
        dist = entity.get_distance_to(player)

        if dist <= entity.attack_range:
            entity.state_machine.change_state(EnemyState.ATTACK)
            return

        if dist > entity.detect_range * 1.5:
            entity.state_machine.change_state(EnemyState.IDLE)
            return

        # Real-time A* Path pursuit with cooldown
        entity.update_path_to_target((player.pos_x, player.pos_y), dt, game_context.tilemap, game_context.obstacles, game_context.boss_gates)
        entity.follow_current_path(dt, game_context.tilemap, game_context.obstacles)


class KeepDistanceState(State):
    """
    Ranged Real-Time Kiting AI:
    - If Player is too close (< min_dist): Back away smoothly.
    - If Player in range with Line of Sight: Enter telegraph windup attack on cooldown.
    - If Player is blocked or far: Advance using A* around barrels/pillars.
    """
    def __init__(self):
        super().__init__(EnemyState.KEEP_DISTANCE)
        self.shot_cooldown = 0.0

    def enter(self, entity):
        entity.animator.change_state("walk")
        self.shot_cooldown = random.uniform(0.4, 1.0)

    def execute(self, entity, dt: float, game_context):
        player = game_context.player
        dist = entity.get_distance_to(player)
        self.shot_cooldown -= dt

        if dist > entity.detect_range * 1.6:
            entity.state_machine.change_state(EnemyState.IDLE)
            return

        min_r = getattr(entity, "preferred_min_dist", 120.0)
        max_r = getattr(entity, "preferred_max_dist", 240.0)
        has_los = entity.has_line_of_sight(player, game_context.tilemap, game_context.obstacles, game_context.boss_gates)

        # 1. Player is too close -> KITE BACKWARDS
        if dist < min_r:
            entity.animator.change_state("walk")
            dx = entity.pos_x - player.pos_x
            dy = entity.pos_y - player.pos_y
            mag = math.hypot(dx, dy)
            if mag > 0:
                ret_x = entity.pos_x + (dx / mag) * 45.0
                ret_y = entity.pos_y + (dy / mag) * 45.0
                entity.move_toward_world(ret_x, ret_y, entity.speed * 0.85, dt, game_context.tilemap, game_context.obstacles)

        # 2. In range & Line of Sight -> SHOOT / CAST
        elif dist <= max_r and has_los:
            entity.animator.change_state("idle")
            dx = player.pos_x - entity.pos_x
            dy = player.pos_y - entity.pos_y
            entity.facing_dir = (dx, dy)
            entity.flip_x = dx < 0

            if self.shot_cooldown <= 0:
                entity.state_machine.change_state(EnemyState.ATTACK)
                self.shot_cooldown = getattr(entity, "attack_rate", 1.8)

        # 3. Blocked by Barrel/Wall or Out of range -> ADVANCE VIA A*
        else:
            entity.animator.change_state("walk")
            entity.update_path_to_target((player.pos_x, player.pos_y), dt, game_context.tilemap, game_context.obstacles, game_context.boss_gates)
            entity.follow_current_path(dt, game_context.tilemap, game_context.obstacles)


class AttackState(State):
    """Enemy attack with windup telegraph before striking."""
    def __init__(self):
        super().__init__(EnemyState.ATTACK)
        self.attack_duration = 0.50
        self.timer = 0.0
        self.damage_applied = False

    def enter(self, entity):
        self.timer = self.attack_duration
        self.damage_applied = False
        entity.animator.change_state("attack", reset=True)

    def execute(self, entity, dt: float, game_context):
        self.timer -= dt
        player = game_context.player

        # Deliver strike mid-swing
        if not self.damage_applied and self.timer <= self.attack_duration * 0.45:
            if getattr(entity, "is_ranged", False):
                from combat.projectile import Projectile
                dx = player.pos_x - entity.pos_x
                dy = player.pos_y - entity.pos_y
                ptype = getattr(entity, "projectile_type", "enemy_magic" if entity.enemy_type == "mage_enemy" else "arrow")
                proj = Projectile(
                    entity.pos_x, entity.pos_y, dx, dy,
                    damage=entity.attack_power,
                    speed=290.0,
                    range_px=entity.detect_range,
                    owner="enemy",
                    proj_type=ptype
                )
                game_context.combat_system.projectiles.append(proj)
                if hasattr(entity, "on_attack"):
                    entity.on_attack(game_context)
                if game_context.sound_manager:
                    game_context.sound_manager.play("attack")
            else:
                dist = entity.get_distance_to(player)
                if dist <= entity.attack_range * 1.25 and not player.is_invulnerable:
                    game_context.combat_system.enemy_attack_player(entity, player)
                    if getattr(entity, "status_inflict", None):
                        player.apply_status_effect(entity.status_inflict, duration=3.0)
                    if hasattr(entity, "on_attack"):
                        entity.on_attack(game_context)
            self.damage_applied = True

        if self.timer <= 0:
            if getattr(entity, "is_ranged", False):
                entity.state_machine.change_state(EnemyState.KEEP_DISTANCE)
            else:
                dist = entity.get_distance_to(player)
                if dist <= entity.attack_range:
                    self.enter(entity)
                else:
                    entity.state_machine.change_state(EnemyState.CHASE)


class HurtState(State):
    def __init__(self):
        super().__init__(EnemyState.HURT)
        self.stun_timer = 0.18

    def enter(self, entity):
        self.stun_timer = 0.18
        entity.animator.change_state("hurt", reset=True)

    def execute(self, entity, dt: float, game_context):
        self.stun_timer -= dt
        if self.stun_timer <= 0:
            if entity.current_hp <= 0:
                entity.state_machine.change_state(EnemyState.DEAD)
            else:
                if getattr(entity, "is_ranged", False):
                    entity.state_machine.change_state(EnemyState.KEEP_DISTANCE)
                else:
                    entity.state_machine.change_state(EnemyState.CHASE)


class DeadState(State):
    def __init__(self):
        super().__init__(EnemyState.DEAD)
        self.decay_timer = 0.8
        self.death_handled = False

    def enter(self, entity):
        self.decay_timer = 0.8
        self.death_handled = False
        entity.animator.change_state("dead", reset=True)

    def execute(self, entity, dt: float, game_context):
        if not self.death_handled:
            self.death_handled = True
            if hasattr(entity, "on_death_context"):
                entity.on_death_context(game_context)
            else:
                entity.on_death()

        self.decay_timer -= dt
        if self.decay_timer <= 0:
            entity.is_removed = True
