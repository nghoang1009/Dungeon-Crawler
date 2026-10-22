import math
import random
import pygame
from combat.damage import DamageNumber
from combat.projectile import Projectile
from combat.telegraph import TelegraphZone, TelegraphShape
from core.collision import CollisionSystem
from settings import COLOR_HP_RED, COLOR_GOLD, TILE_SIZE, flip_for
from combat.effects import ShockwaveFX, color_of, element_for, sound_of

class SlashEffect:
    """
    Renders attack slash arc / swing / thrust visual in front of player on screen.
    """
    def __init__(self, x: float, y: float, dir_x: float, dir_y: float, range_px: float = 48.0, arc_angle: float = 110.0, color=(240, 240, 255)):
        self.x = x
        self.y = y
        self.range_px = range_px
        self.arc_angle = arc_angle
        self.color = color
        self.lifetime = 0.16
        self.age = 0.0
        self.center_angle = math.atan2(dir_y, dir_x)
        self.is_alive = True

    def update(self, dt: float):
        self.age += dt
        if self.age >= self.lifetime:
            self.is_alive = False

    def render(self, surface: pygame.Surface, camera):
        if not self.is_alive:
            return

        screen_x, screen_y = camera.apply_pos(self.x, self.y)
        progress = self.age / self.lifetime
        alpha = int(255 * (1.0 - progress))

        fan_surf = pygame.Surface((int(self.range_px * 2.4), int(self.range_px * 2.4)), pygame.SRCALPHA)
        center = (fan_surf.get_width() // 2, fan_surf.get_height() // 2)

        half_ang = math.radians(self.arc_angle / 2.0)
        start_angle = self.center_angle - half_ang
        end_angle = self.center_angle + half_ang
        steps = 10

        points = [center]
        for s in range(steps + 1):
            cur_ang = start_angle + (end_angle - start_angle) * (s / steps)
            px = center[0] + math.cos(cur_ang) * self.range_px
            py = center[1] + math.sin(cur_ang) * self.range_px
            points.append((px, py))

        col_with_alpha = (*self.color[:3], max(0, min(180, alpha)))
        pygame.draw.polygon(fan_surf, col_with_alpha, points)

        for s in range(steps):
            a1 = start_angle + (end_angle - start_angle) * (s / steps)
            a2 = start_angle + (end_angle - start_angle) * ((s + 1) / steps)
            p1 = (center[0] + math.cos(a1) * self.range_px, center[1] + math.sin(a1) * self.range_px)
            p2 = (center[0] + math.cos(a2) * self.range_px, center[1] + math.sin(a2) * self.range_px)
            pygame.draw.line(fan_surf, (255, 255, 255, alpha), p1, p2, 3)

        surface.blit(fan_surf, (screen_x - center[0], screen_y - center[1]))


class HitParticle:
    """Spark / debris particle on hit."""
    def __init__(self, x: float, y: float, color=(255, 220, 80)):
        self.x = x
        self.y = y
        self.color = color
        self.lifetime = 0.25
        self.age = 0.0
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(40.0, 120.0)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed

    def update(self, dt: float):
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt

    @property
    def is_alive(self) -> bool:
        return self.age < self.lifetime

    def render(self, surface: pygame.Surface, camera):
        screen_x, screen_y = camera.apply_pos(self.x, self.y)
        alpha = int(255 * (1.0 - (self.age / self.lifetime)))
        p_surf = pygame.Surface((4, 4), pygame.SRCALPHA)
        pygame.draw.circle(p_surf, (*self.color[:3], alpha), (2, 2), 2)
        surface.blit(p_surf, (screen_x - 2, screen_y - 2))


class HazardArea:
    """Ground poison or fire pool that inflicts status effects while standing in it."""
    def __init__(self, gx: int, gy: int, effect_type: str = "poison", duration: float = 8.0):
        self.gx = gx
        self.gy = gy
        self.effect_type = effect_type  # "poison" or "burn"
        self.duration = duration
        self.age = 0.0
        self.tick_timer = 0.0

    def update(self, dt: float, player) -> bool:
        self.age += dt
        self.tick_timer += dt

        if (player.grid_x, player.grid_y) == (self.gx, self.gy) and not player.is_dashing:
            if self.tick_timer >= 0.5:
                self.tick_timer = 0.0
                player.apply_status_effect(self.effect_type, duration=2.5)

        return self.age >= self.duration

    def render(self, surface: pygame.Surface, camera):
        screen_x, screen_y = camera.apply_pos(self.gx * TILE_SIZE, self.gy * TILE_SIZE)
        surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        pulse = int(math.sin(self.age * 4.0) * 20)
        if self.effect_type == "poison":
            surf.fill((40, 180, 50, 70 + pulse))
            pygame.draw.circle(surf, (80, 240, 90, 120), (TILE_SIZE // 2, TILE_SIZE // 2), 8)
        else:
            surf.fill((220, 80, 20, 70 + pulse))
            pygame.draw.circle(surf, (255, 180, 40, 140), (TILE_SIZE // 2, TILE_SIZE // 2), 8)
        surface.blit(surf, (screen_x, screen_y))


class CombatSystem:
    """
    2D Real-Time Action Roguelike Combat System.
    Handles Melee Cleave Hitboxes, Projectiles, Telegraph Danger Zones (Read-Dodge-Punish),
    Hit particles, Ground Hazard Areas, and Damage numbers.
    """
    def __init__(self, sound_manager=None, camera=None):
        self.sound_manager = sound_manager
        self.camera = camera
        self.damage_numbers: list[DamageNumber] = []
        self.projectiles: list[Projectile] = []
        self.slash_effects: list[SlashEffect] = []
        self.particles: list[HitParticle] = []
        self.telegraph_zones: list[TelegraphZone] = []
        self.hazard_areas: list[HazardArea] = []
        self.effects: list = []          # ShockwaveFX / GhostImage (visual only)

    def spawn_shockwave(self, x: float, y: float, radius: float, color, duration: float = 0.45, filled: bool = True):
        self.effects.append(ShockwaveFX(x, y, radius, color, duration, filled))

    def _zone_impact(self, zone):
        """Sound + flash when a telegraphed strike lands (whether or not it hits the player)."""
        if zone.damage <= 0:
            return
        element = element_for(zone.status_effect, zone.element)
        color = color_of(element)
        if self.sound_manager:
            self.sound_manager.play(sound_of(element), 0.6)
        if zone.origin:
            ox, oy = zone.origin
            if zone.shape in (TelegraphShape.LINE,) and zone.target:
                ox, oy = zone.target
            reach = zone.radius if zone.shape != TelegraphShape.LINE else 40.0
            self.spawn_shockwave(ox, oy, min(reach, 190.0) if zone.shape != TelegraphShape.CONE else reach * 0.5,
                                 color, 0.4)
            for _ in range(6):
                self.particles.append(HitParticle(ox + random.uniform(-reach, reach) * 0.4,
                                                  oy + random.uniform(-reach, reach) * 0.4, color=color))
        elif zone.tiles:
            tx, ty = zone.tiles[len(zone.tiles) // 2]
            self.spawn_shockwave(tx * TILE_SIZE + 16, ty * TILE_SIZE + 16, 90, color, 0.5)

    def update(self, dt: float, tilemap, enemies, player, obstacles=None):
        for fx in self.effects:
            fx.update(dt)
        self.effects = [fx for fx in self.effects if fx.is_alive]

        # 1. Update Floating text
        for num in self.damage_numbers:
            num.update(dt)
        self.damage_numbers = [n for n in self.damage_numbers if n.is_alive]

        # 2. Update Slashes
        for sl in self.slash_effects:
            sl.update(dt)
        self.slash_effects = [s for s in self.slash_effects if s.is_alive]

        # 3. Update Particles
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.is_alive]

        # 4. Update Hazard Areas (Poison / Fire pools)
        active_hazards = []
        for h in self.hazard_areas:
            expired = h.update(dt, player)
            if not expired:
                active_hazards.append(h)
        self.hazard_areas = active_hazards

        # 5. Update Telegraph Danger Zones (Triggers damage & status effect on expiration if player is in zone)
        for zone in self.telegraph_zones:
            triggered = zone.update(dt)
            if triggered:
                self._zone_impact(zone)
                if zone.damage > 0 and zone.check_hit(player):
                    self._apply_damage_to_player(player, zone.damage)
                    if zone.status_effect:
                        player.apply_status_effect(zone.status_effect, duration=3.0)
                    if self.camera:
                        self.camera.add_shake(duration=0.30, magnitude=7.0)

        self.telegraph_zones = [z for z in self.telegraph_zones if z.is_active]

        # 6. Update Projectiles
        for proj in self.projectiles:
            if not proj.is_alive:
                continue

            proj.update(dt, tilemap, obstacles)
            if not proj.is_alive:
                continue

            if proj.owner == "player":
                for enemy in enemies:
                    if enemy.is_alive and proj.check_entity_hit(enemy):
                        self._apply_damage_to_enemy(player, enemy, proj.damage, is_crit=False, tilemap=tilemap, obstacles=obstacles)
                        proj.is_alive = False
                        break
            elif proj.owner == "enemy":
                if player.is_alive and not player.is_invulnerable and proj.check_entity_hit(player):
                    self._apply_damage_to_player(player, proj.damage)
                    proj.is_alive = False

        self.projectiles = [p for p in self.projectiles if p.is_alive]

    def render_visuals(self, surface: pygame.Surface, camera, font: pygame.font.Font, tilemap=None):
        # Render ground hazard areas (only where the player has explored, so fog never leaks trap-room pools)
        for h in self.hazard_areas:
            if tilemap is None or (tilemap.is_valid(h.gx, h.gy) and tilemap.explored[h.gy][h.gx]):
                h.render(surface, camera)

        # Render warning telegraph danger zones on ground
        for zone in self.telegraph_zones:
            zone.render(surface, camera)

        for fx in self.effects:
            fx.render(surface, camera)

        for sl in self.slash_effects:
            sl.render(surface, camera)

        for proj in self.projectiles:
            proj.render(surface, camera)

        for p in self.particles:
            p.render(surface, camera)

        for num in self.damage_numbers:
            num.render(surface, camera, font)

    def spawn_telegraph_zone(self, tiles: list[tuple[int, int]], duration: float = 0.75, damage: int = 25):
        self.telegraph_zones.append(TelegraphZone(tiles=tiles, duration=duration, damage=damage))

    def spawn_hazard_area(self, gx: int, gy: int, effect_type: str = "poison", duration: float = 8.0):
        self.hazard_areas.append(HazardArea(gx, gy, effect_type, duration))

    def player_attack(self, player, enemies: list, obstacles: list, tilemap, direction: tuple[float, float] | None = None) -> bool:
        weapon = player.current_weapon
        if not weapon or not weapon.can_attack():
            return False

        if direction is not None:
            player.facing_dir = direction
            player.flip_x = flip_for(direction[0], player.flip_x)

        fx, fy = player.facing_dir
        weapon.trigger_attack()
        player.animator.change_state("attack", reset=True)
        px, py = player.rect.centerx, player.rect.centery

        if weapon.is_ranged:
            # Spawn Ranged Projectile (Bow arrow / Staff magic bolt / Crossbow bolt / Gun bullet)
            proj_type = weapon.projectile_type
            proj_dmg = weapon.total_damage + player.attack_power
            proj_speed = 540.0 if proj_type == "bullet" else (480.0 if proj_type == "bolt" else 420.0)
            proj = Projectile(
                px, py, fx, fy,
                damage=proj_dmg,
                speed=proj_speed,
                range_px=weapon.range_px,
                owner="player",
                proj_type=proj_type
            )
            self.projectiles.append(proj)
            if self.sound_manager:
                self.sound_manager.play("attack")
            return True

        else:
            # Melee Slash Arc (Sword / Greatsword / Axe / Spear)
            slash_col = (255, 230, 140) if weapon.rarity == "LEGENDARY" else (220, 230, 255)
            self.slash_effects.append(SlashEffect(px, py, fx, fy, weapon.range_px, weapon.arc_angle, slash_col))

            if self.sound_manager:
                self.sound_manager.play("attack")

            hit_any = False
            already_hit = set()
            half_rad = math.radians(weapon.arc_angle / 2.0)
            cos_threshold = math.cos(half_rad)

            for enemy in enemies:
                if not enemy.is_alive or enemy in already_hit:
                    continue

                ex, ey = enemy.rect.centerx, enemy.rect.centery
                dx = ex - px
                dy = ey - py
                dist = math.hypot(dx, dy)
                # Big bodies (bosses) are hit by the edge of the swing, not only by their centre point
                reach = weapon.range_px + max(0, enemy.rect.width - TILE_SIZE) * 0.4

                if dist <= reach:
                    if dist > 0:
                        dot = (dx / dist) * fx + (dy / dist) * fy
                        if dot >= cos_threshold:
                            already_hit.add(enemy)
                            is_crit = random.random() < weapon.crit_chance
                            raw_dmg = weapon.total_damage + player.attack_power - enemy.defense
                            final_dmg = max(1, int(raw_dmg * (2.0 if is_crit else 1.0)))
                            self._apply_damage_to_enemy(player, enemy, final_dmg, is_crit, tilemap, obstacles, knockback_dir=(fx, fy))
                            hit_any = True

            # Hit Destructible Obstacles
            if obstacles:
                for obs in obstacles:
                    if obs.is_alive and obs.destructible and obs not in already_hit:
                        ox, oy = obs.rect.centerx, obs.rect.centery
                        dx = ox - px
                        dy = oy - py
                        dist = math.hypot(dx, dy)
                        if dist <= weapon.range_px:
                            dot = (dx / dist) * fx + (dy / dist) * fy if dist > 0 else 1.0
                            if dot >= cos_threshold:
                                already_hit.add(obs)
                                obs.take_damage(weapon.total_damage + player.attack_power)
                                hit_any = True

            if hit_any and self.camera:
                self.camera.add_shake(duration=0.15, magnitude=4.0)

            return True

    def _apply_damage_to_enemy(self, player, enemy, damage: int, is_crit: bool, tilemap, obstacles, knockback_dir=None):
        # 1. Trigger Relic damage hooks before applying damage
        if hasattr(player, "relics"):
            for r in player.unique_relics():
                damage = r.on_hit_enemy(player, enemy, damage)

        # 2. Apply damage to enemy
        enemy.take_damage(damage)
        enemy.animator.change_state("hurt", reset=True)

        # 3. Apply physics knockback
        if knockback_dir and enemy.is_alive:
            kx, ky = knockback_dir
            CollisionSystem.move_and_slide(enemy, kx * 12.0, ky * 12.0, tilemap, obstacles)

        for _ in range(4):
            self.particles.append(HitParticle(enemy.rect.centerx, enemy.rect.centery))

        if self.sound_manager:
            self.sound_manager.play("hit")

        col = COLOR_GOLD if is_crit else (255, 120, 120)
        txt = f"{damage} CRIT!" if is_crit else str(damage)
        self.damage_numbers.append(DamageNumber(enemy.rect.centerx, enemy.rect.top - 8, txt, col, is_crit))

        # 4. Enemy Death handling: Grant EXP & Score only once!
        if not enemy.is_alive and not getattr(enemy, "score_awarded", False):
            enemy.score_awarded = True
            pts = getattr(enemy, "score_reward", 100)
            if not hasattr(enemy, "score_reward"):
                score_map = {"goblin": 100, "skeleton": 150, "archer_enemy": 200, "orc": 250, "mage_enemy": 300, "boss": 2000}
                pts = score_map.get(getattr(enemy, "enemy_type", "goblin"), 100)
            player.add_score(pts)
            player.enemies_killed += 1
            if getattr(enemy, "enemy_type", "") == "boss" or hasattr(enemy, "boss_type"):
                player.bosses_killed += 1
            self.damage_numbers.append(DamageNumber(enemy.rect.centerx, enemy.rect.top - 24, f"+{pts} SCORE", COLOR_GOLD))

    def _apply_damage_to_player(self, player, damage: int):
        if not player.is_alive or player.is_invulnerable:
            return  # Invulnerable while dashing or during the post-hit grace period

        raw_dmg = damage - player.defense
        final_dmg = max(1, int(raw_dmg))
        player.take_damage(final_dmg)
        player.start_hit_invulnerability()
        player.animator.change_state("hurt", reset=True)

        if self.sound_manager:
            self.sound_manager.play("hit")
        if self.camera:
            self.camera.add_shake(duration=0.22, magnitude=6.0)

        for _ in range(4):
            self.particles.append(HitParticle(player.rect.centerx, player.rect.centery, color=(240, 50, 50)))

        self.damage_numbers.append(DamageNumber(player.rect.centerx, player.rect.top - 8, f"-{final_dmg}", COLOR_HP_RED))

    def enemy_attack_player(self, enemy, player):
        self._apply_damage_to_player(player, enemy.attack_power)
