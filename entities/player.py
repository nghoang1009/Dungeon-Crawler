import pygame
import math
from entities.base import Entity
from items.inventory import Inventory
from items.potion import Potion, PotionType
from combat.weapon import Weapon
from core.animation import Animator
from core.sprite_loader import SpriteSheetLoader
from core.collision import CollisionSystem
from entities.class_data import ClassData, KNIGHT_CLASS
from settings import (
    STAMINA_DASH_COST, STAMINA_SPECIAL_COST, STAMINA_REGEN_RATE, flip_for
)

BASE_DASH_SPEED = 440.0
BASE_DASH_TIME = 0.25
MAX_DASH_SPEED_BONUS = 0.20     # relics can raise dash speed by at most +20% over the base
DUPLICATE_RELIC_GOLD = 60
HIT_INVULNERABILITY_SECONDS = 0.8   # grace period after taking a hit (blinks while active)
BLINK_INTERVAL = 0.08


class Player(Entity):
    """
    Real-Time 2D Action Roguelike Player Hero.
    Supports continuous WASD movement with wall sliding, Stamina-based Dash with i-frames,
    Class Special Skills (Shield Bash, Roll Shot, Blink Teleport), Status Effects (Slow, Poison, Burn),
    Score & Stats tracking, and multi-weapon combat.
    """
    def __init__(self, grid_x: int, grid_y: int, class_data: ClassData = KNIGHT_CLASS):
        super().__init__(grid_x, grid_y, width=32, height=32)
        self.class_data = class_data
        self.class_name = class_data.name
        self.name = "Hero"

        # Core Attributes
        self.max_hp = class_data.max_hp
        self.current_hp = self.max_hp
        self.attack_power = class_data.attack
        self.defense = class_data.defense
        self.speed = class_data.speed

        # Stamina & Dash System
        self.max_stamina = 100.0
        self.stamina = 100.0
        self.stamina_regen = STAMINA_REGEN_RATE
        self.is_dashing = False
        self.dash_timer = 0.0
        self.dash_speed = BASE_DASH_SPEED
        self.dash_cooldown = 0.0
        self.dash_dir = (0.0, 1.0)
        self.invuln_timer = 0.0   # > 0 right after being hit: no further hit damage

        # Mana System (only for classes that cast magic, e.g. Mage)
        self.uses_mana = class_data.uses_mana
        self.max_mana = class_data.max_mana
        self.mana = float(class_data.max_mana)
        self.mana_regen = class_data.mana_regen

        # Special Skill Cooldown
        self.special_cooldown = 0.0

        # Progression & Score
        self.level = 1
        self.exp = 0
        self.gold = 0
        self.score = 0
        self.enemies_killed = 0
        self.bosses_killed = 0
        self.run_time = 0.0

        # Inventory & Starter equipment
        self.inventory = Inventory(capacity=25)
        self.relics = []

        starter_wp = class_data.create_starter_weapon()
        self.inventory.add_weapon(starter_wp)
        self.current_weapon_idx = 0

        # 3 Starting Health Potions
        health_pots = Potion(PotionType.HEALTH, potency=35)
        health_pots.quantity = 3
        self.inventory.add_item(health_pots)

        self.buffs = {}
        # Status Effects: {"slow": {"timer": 3.0, "amount": 0.3}, "poison": {"timer": 3.0, "tick": 0.5, "dps": 2}, "burn": ...}
        self.status_effects = {}

        # Load player sprite frames by name from TXT mapping
        sprite_loader = SpriteSheetLoader()
        sprite_loader.initialize()
        player_frames = sprite_loader.get_player_frames(self.class_name, 32)
        self.animator = Animator(player_frames, default_state="idle", fps=8.0)
        self.flip_x = False

    @property
    def current_weapon(self) -> Weapon | None:
        if 0 <= self.current_weapon_idx < len(self.inventory.weapons):
            return self.inventory.weapons[self.current_weapon_idx]
        return None

    def can_attack(self) -> bool:
        if not self.is_alive:
            return False
        wp = self.current_weapon
        return wp is not None and wp.can_attack()

    def switch_weapon(self, index: int):
        if 0 <= index < len(self.inventory.weapons):
            self.current_weapon_idx = index

    def next_weapon(self):
        if self.inventory.weapons:
            self.current_weapon_idx = (self.current_weapon_idx + 1) % len(self.inventory.weapons)

    def prev_weapon(self):
        if self.inventory.weapons:
            self.current_weapon_idx = (self.current_weapon_idx - 1) % len(self.inventory.weapons)

    @property
    def is_invulnerable(self) -> bool:
        """True while dashing or during the grace period after a hit."""
        return self.is_dashing or self.invuln_timer > 0.0

    def start_hit_invulnerability(self, seconds: float = HIT_INVULNERABILITY_SECONDS):
        self.invuln_timer = max(self.invuln_timer, seconds)

    def unique_relics(self) -> list:
        """Owned relics with duplicates removed: a second copy of the same relic never adds to its effect."""
        seen, unique = set(), []
        for r in self.relics:
            if r.relic_id not in seen:
                seen.add(r.relic_id)
                unique.append(r)
        return unique

    def add_relic(self, relic) -> bool:
        """Adds a relic. A duplicate is turned into gold instead (its effect would not stack anyway)."""
        if any(r.relic_id == relic.relic_id for r in self.relics):
            self.gold += DUPLICATE_RELIC_GOLD
            return False
        self.relics.append(relic)
        relic.on_acquire(self)
        return True

    @property
    def dash_speed_multiplier(self) -> float:
        bonus = sum(r.dash_speed_bonus for r in self.unique_relics())
        return 1.0 + min(MAX_DASH_SPEED_BONUS, bonus)

    @property
    def dash_distance_multiplier(self) -> float:
        return 1.0 + sum(r.dash_distance_bonus for r in self.unique_relics())

    @property
    def dash_stamina_cost(self) -> float:
        return max(0.0, STAMINA_DASH_COST - sum(r.dash_stamina_discount for r in self.unique_relics()))

    def add_score(self, points: int):
        self.score += points

    def trigger_dash(self, move_dir: tuple[float, float] | None = None, sound_manager=None, game=None):
        """
        SPACE Dash:
        Dashes in move direction if moving, otherwise facing direction.
        Grants invulnerability frames (i-frames) for 0.25s.
        """
        cost = self.dash_stamina_cost
        if not self.is_dashing and self.dash_cooldown <= 0 and self.stamina >= cost:
            self.is_dashing = True
            # Always rebuilt from the base values, so repeated dashes can never ramp the speed up
            self.dash_speed = BASE_DASH_SPEED * self.dash_speed_multiplier
            self.dash_timer = BASE_DASH_TIME * self.dash_distance_multiplier
            self.dash_cooldown = 0.50
            self.stamina -= cost

            if move_dir and (move_dir[0] != 0 or move_dir[1] != 0):
                self.dash_dir = move_dir
            else:
                self.dash_dir = self.facing_dir

            for r in self.unique_relics():
                r.on_dash(self, game)

            if sound_manager:
                sound_manager.play("attack")

    def trigger_special_skill(self, game_context) -> bool:
        if self.special_cooldown > 0 or self.stamina < STAMINA_SPECIAL_COST:
            return False

        self.stamina -= STAMINA_SPECIAL_COST
        self.special_cooldown = 2.5
        fx, fy = self.facing_dir

        if self.class_name == "Knight":
            self.is_dashing = True
            self.dash_timer = 0.20
            self.dash_dir = self.facing_dir
            self.dash_speed = 480.0
            game_context.combat_system.player_attack(self, game_context.enemies, game_context.obstacles, game_context.tilemap)

        elif self.class_name == "Archer":
            self.is_dashing = True
            self.dash_timer = 0.22
            self.dash_dir = (-fx, -fy)  # Backflip roll
            from combat.projectile import Projectile
            proj = Projectile(
                self.pos_x, self.pos_y, fx, fy,
                damage=self.attack_power + 15,
                speed=440.0,
                range_px=400.0,
                owner="player",
                proj_type="arrow"
            )
            game_context.combat_system.projectiles.append(proj)

        elif self.class_name == "Mage":
            blink_dist = 3
            target_gx = self.grid_x + int(fx * blink_dist)
            target_gy = self.grid_y + int(fy * blink_dist)
            if game_context.tilemap.is_walkable(target_gx, target_gy, game_context.obstacles, game_context.boss_gates):
                self.set_grid_pos(target_gx, target_gy)

        if game_context.sound_manager:
            game_context.sound_manager.play("attack")

        return True

    def apply_status_effect(self, effect_type: str, duration: float, value: float = 0.0):
        """Applies SLOW, POISON, or BURN with finite duration."""
        if effect_type == "slow":
            self.status_effects["slow"] = {"timer": duration, "amount": value if value > 0 else 0.30}
        elif effect_type == "poison":
            self.status_effects["poison"] = {"timer": duration, "tick": 0.5, "dps": value if value > 0 else 2}
        elif effect_type == "burn":
            self.status_effects["burn"] = {"timer": duration, "tick": 0.5, "dps": value if value > 0 else 4}

    def handle_continuous_input(self, keys, dt: float, tilemap, obstacles=None, closed_gates=None):
        if not self.is_alive:
            return

        move_x = 0.0
        move_y = 0.0
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            move_y -= 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            move_y += 1.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move_x -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move_x += 1.0

        mag = math.hypot(move_x, move_y)
        if mag > 0:
            move_x /= mag
            move_y /= mag
            self.facing_dir = (move_x, move_y)
            self.flip_x = flip_for(move_x, self.flip_x)

        curr_speed = self.speed

        # Speed Buffs
        if "speed" in self.buffs:
            curr_speed *= (1.0 + self.buffs["speed"]["boost"])

        # Slow Status Effect (-30% speed)
        if "slow" in self.status_effects:
            curr_speed *= (1.0 - self.status_effects["slow"]["amount"])

        if self.is_dashing:
            # Dash velocity along dash_dir
            dx = self.dash_dir[0] * self.dash_speed * dt
            dy = self.dash_dir[1] * self.dash_speed * dt
        else:
            dx = move_x * curr_speed * dt
            dy = move_y * curr_speed * dt

        if dx != 0 or dy != 0:
            CollisionSystem.move_and_slide(self, dx, dy, tilemap, obstacles)
            if not self.is_dashing and self.animator.current_state not in ("attack", "hurt"):
                self.animator.change_state("walk")
        else:
            if not self.is_dashing and self.animator.current_state not in ("attack", "hurt"):
                self.animator.change_state("idle")

    def use_health_potion(self, sound_manager=None, combat_system=None) -> bool:
        if self.current_hp >= self.max_hp:
            return False

        for idx, item in enumerate(self.inventory.items):
            if isinstance(item, Potion) and item.potion_type == PotionType.HEALTH:
                if self.inventory.use_item_at(idx, self):
                    if sound_manager:
                        sound_manager.play("potion")
                    if combat_system:
                        from combat.damage import DamageNumber
                        combat_system.damage_numbers.append(
                            DamageNumber(self.pos_x, self.pos_y - 12, f"+{item.potency} HP", (60, 240, 100))
                        )
                    return True
        return False

    def use_mana_potion(self, sound_manager=None, combat_system=None) -> bool:
        """Quick-use the first Mana Potion in the inventory (key 2)."""
        if not self.uses_mana or self.mana >= self.max_mana:
            return False

        for idx, item in enumerate(self.inventory.items):
            if isinstance(item, Potion) and item.potion_type == PotionType.MANA:
                if self.inventory.use_item_at(idx, self):
                    if sound_manager:
                        sound_manager.play("potion")
                    if combat_system:
                        from combat.damage import DamageNumber
                        combat_system.damage_numbers.append(
                            DamageNumber(self.pos_x, self.pos_y - 12, f"+{item.potency} MP", (80, 160, 255))
                        )
                    return True
        return False

    def add_gold(self, amount: int):
        self.gold += amount

    def restore_mana(self, amount: float) -> float:
        """Restores mana capped at max_mana. Returns the actually restored amount."""
        if not self.uses_mana or amount <= 0:
            return 0.0
        before = self.mana
        self.mana = min(float(self.max_mana), self.mana + amount)
        return self.mana - before

    def use_mana(self, amount: float) -> bool:
        """Spends mana for a cast. Fails (spending nothing) when mana is insufficient."""
        if not self.uses_mana or self.mana < amount:
            return False
        self.mana = max(0.0, self.mana - amount)
        return True

    def apply_buff(self, buff_type: str, boost: float, duration: float):
        self.buffs[buff_type] = {"boost": boost, "duration": duration}

    def update(self, dt: float, combat_system=None):
        if not self.is_alive:
            return

        self.run_time += dt
        self.sync_rect()

        # Update weapon attack cooldown timer
        if self.current_weapon:
            self.current_weapon.update(dt)

        self.animator.update(dt)

        # Return to idle after attack or hurt animation completes
        if self.animator.current_state in ("attack", "hurt") and self.animator.is_finished:
            self.animator.change_state("idle")

        # Regenerate stamina
        if not self.is_dashing and self.stamina < self.max_stamina:
            self.stamina = min(self.max_stamina, self.stamina + self.stamina_regen * dt)

        # Regenerate mana (casting classes only)
        if self.uses_mana and self.mana < self.max_mana:
            self.mana = min(float(self.max_mana), self.mana + self.mana_regen * dt)

        if self.invuln_timer > 0:
            self.invuln_timer = max(0.0, self.invuln_timer - dt)

        # Dash & Special cooldowns
        if self.dash_cooldown > 0:
            self.dash_cooldown -= dt
        if self.special_cooldown > 0:
            self.special_cooldown -= dt

        if self.is_dashing:
            self.dash_timer -= dt
            if self.dash_timer <= 0:
                self.is_dashing = False

        # Status Effects Tick & Timer
        expired_status = []
        for s_type, s_data in self.status_effects.items():
            s_data["timer"] -= dt
            if s_data["timer"] <= 0:
                expired_status.append(s_type)
            else:
                if s_type in ("poison", "burn"):
                    s_data["tick"] -= dt
                    if s_data["tick"] <= 0:
                        s_data["tick"] = 0.5
                        dmg = int(s_data["dps"] * 0.5)
                        if dmg > 0:
                            self.take_damage(dmg)
                            if combat_system:
                                from combat.damage import DamageNumber
                                col = (120, 240, 80) if s_type == "poison" else (255, 120, 40)
                                txt = f"-{dmg} {s_type.upper()}"
                                combat_system.damage_numbers.append(DamageNumber(self.pos_x, self.pos_y - 14, txt, col))

        for s_type in expired_status:
            del self.status_effects[s_type]

        # Buffs
        expired = []
        for b_name, b_data in self.buffs.items():
            b_data["duration"] -= dt
            if b_data["duration"] <= 0:
                expired.append(b_name)
        for b_name in expired:
            del self.buffs[b_name]

    def render(self, surface: pygame.Surface, camera):
        screen_rect = camera.apply(self.rect)
        frame = self.animator.get_current_frame(flip_x=self.flip_x)

        # Draw Dash Ghost / Trail if dashing
        if self.is_dashing:
            ghost = frame.copy()
            ghost.fill((100, 200, 255, 120), special_flags=pygame.BLEND_RGBA_MULT)
            surface.blit(ghost, (screen_rect.x - int(self.dash_dir[0] * 6), screen_rect.y - int(self.dash_dir[1] * 6)))

        # Draw Status Aura (Poison green or Burn orange/red glow)
        if "poison" in self.status_effects:
            p_glow = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.circle(p_glow, (50, 220, 50, 80), (16, 16), 14)
            surface.blit(p_glow, (screen_rect.x, screen_rect.y))
        elif "burn" in self.status_effects:
            b_glow = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.circle(b_glow, (255, 100, 30, 90), (16, 16), 14)
            surface.blit(b_glow, (screen_rect.x, screen_rect.y))

        # Blink while the post-hit grace period runs
        if self.invuln_timer > 0 and not self.is_dashing and int(self.invuln_timer / BLINK_INTERVAL) % 2 == 0:
            frame = frame.copy()
            frame.fill((255, 255, 255, 110), special_flags=pygame.BLEND_RGBA_MULT)

        surface.blit(frame, (screen_rect.x, screen_rect.y))

        # Render equipped weapon indicator from items.png via TXT resolution
        if self.current_weapon:
            fx, fy = self.facing_dir
            wp_x = screen_rect.centerx + int(fx * 12) - 8
            wp_y = screen_rect.centery + int(fy * 12) - 8

            loader = SpriteSheetLoader()
            w_surf = loader.get_item_sprite(self.current_weapon.name, 16)
            surface.blit(w_surf, (wp_x, wp_y))
