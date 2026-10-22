import pygame
import math
from core.sprite_loader import SpriteSheetLoader
from settings import TILE_SIZE

TRAIL_COLORS = {
    "enemy_magic": (190, 90, 255),
    "fireball": (255, 140, 50),
    "poison_spit": (110, 225, 90),
    "arrow": (235, 235, 245),
    "bolt": (235, 235, 245),
}


class Projectile:
    """
    Ranged projectile (arrows, magic bolts, enemy fireballs).
    Moves with constant velocity, triggers hit on impact with enemies/players/obstacles/walls,
    and terminates after lifetime expiration. Uses native 32x32 sprites from items.png.
    """
    def __init__(self,
                 x: float,
                 y: float,
                 dir_x: float,
                 dir_y: float,
                 damage: int,
                 speed: float = 340.0,
                 range_px: float = 380.0,
                 owner: str = "player",
                 proj_type: str = "arrow"):
        self.pos_x = float(x)
        self.pos_y = float(y)

        mag = math.hypot(dir_x, dir_y)
        if mag > 0:
            self.dir_x = dir_x / mag
            self.dir_y = dir_y / mag
        else:
            self.dir_x = 1.0
            self.dir_y = 0.0

        self.damage = damage
        self.speed = speed
        self.lifetime = range_px / max(1.0, speed)
        self.age = 0.0
        self.owner = owner
        self.proj_type = proj_type
        self.is_alive = True

        self.radius = 6.0
        self.trail: list[tuple[float, float]] = []
        self.angle = math.degrees(math.atan2(-self.dir_y, self.dir_x))

        loader = SpriteSheetLoader()
        loader.initialize()
        if proj_type in ("arrow", "bolt"):
            self.base_surf = loader.get_sprite("arrow", dest_size=24)
        elif proj_type == "bullet":
            self.base_surf = loader.get_sprite("coin", dest_size=16)
        elif proj_type == "enemy_magic":
            self.base_surf = loader.get_sprite("black potion", dest_size=24)
        elif proj_type == "poison_spit":
            self.base_surf = loader.get_sprite("bright green potion", dest_size=20)
        elif proj_type == "fireball":
            self.base_surf = loader.get_sprite("red potion", dest_size=22)
        else:
            self.base_surf = loader.get_sprite("crystal pendant", dest_size=24)

    def update(self, dt: float, tilemap, obstacles=None):
        self.age += dt
        if self.age >= self.lifetime:
            self.is_alive = False
            return

        dx = self.dir_x * self.speed * dt
        dy = self.dir_y * self.speed * dt
        self.trail.append((self.pos_x, self.pos_y))
        if len(self.trail) > 8:
            self.trail.pop(0)
        self.pos_x += dx
        self.pos_y += dy

        # Check wall collision
        tx = int(self.pos_x // TILE_SIZE)
        ty = int(self.pos_y // TILE_SIZE)
        if not tilemap.is_walkable(tx, ty):
            self.is_alive = False
            return

        # Check solid obstacles collision
        if obstacles:
            for obs in obstacles:
                if obs.is_alive and obs.rect.collidepoint(self.pos_x, self.pos_y):
                    if obs.destructible:
                        obs.take_damage(self.damage)
                    self.is_alive = False
                    return

    def check_entity_hit(self, entity) -> bool:
        if not entity.is_alive:
            return False
        hitbox = entity.get_hitbox() if hasattr(entity, "get_hitbox") else entity.rect
        return hitbox.collidepoint(self.pos_x, self.pos_y)

    def render(self, surface: pygame.Surface, camera):
        if not self.is_alive:
            return

        color = TRAIL_COLORS.get(self.proj_type, (220, 220, 235))
        n = len(self.trail)
        for i, (tx, ty) in enumerate(self.trail):
            frac = (i + 1) / (n + 1)
            sx, sy = camera.apply_pos(tx, ty)
            r = max(1, int(5 * frac))
            dot = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(dot, (*color, int(150 * frac)), (r, r), r)
            surface.blit(dot, (sx - r, sy - r))

        screen_x, screen_y = camera.apply_pos(self.pos_x, self.pos_y)
        rotated_surf = pygame.transform.rotate(self.base_surf, self.angle)
        rect = rotated_surf.get_rect(center=(screen_x, screen_y))
        surface.blit(rotated_surf, rect.topleft)


class HomingProjectile(Projectile):
    """Slow seeker orb: steers towards `target` with a limited turn rate, so it can be out-run or dodged."""
    def __init__(self, *args, target=None, turn_rate: float = 1.4, **kwargs):
        super().__init__(*args, **kwargs)
        self.target = target
        self.turn_rate = turn_rate

    def update(self, dt: float, tilemap, obstacles=None):
        if self.target is not None and getattr(self.target, "is_alive", False):
            desired = math.atan2(self.target.pos_y - self.pos_y, self.target.pos_x - self.pos_x)
            current = math.atan2(self.dir_y, self.dir_x)
            diff = math.atan2(math.sin(desired - current), math.cos(desired - current))
            step = max(-self.turn_rate * dt, min(self.turn_rate * dt, diff))
            self.dir_x, self.dir_y = math.cos(current + step), math.sin(current + step)
            self.angle = math.degrees(math.atan2(-self.dir_y, self.dir_x))
        super().update(dt, tilemap, obstacles)
