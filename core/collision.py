import pygame
import math
from settings import TILE_SIZE

class CollisionSystem:
    """
    Handles bounding box collisions, wall collisions, entity-tile interactions,
    and safe multi-step continuous knockback without clipping or sticking in walls.
    """

    @staticmethod
    def check_wall_collision(rect: pygame.Rect, tilemap, obstacles=None) -> bool:
        """
        Check if a given bounding box overlaps with any non-walkable tile in tilemap
        or any solid obstacle.
        """
        left_tile = int(rect.left // TILE_SIZE)
        right_tile = int(rect.right // TILE_SIZE)
        top_tile = int(rect.top // TILE_SIZE)
        bottom_tile = int(rect.bottom // TILE_SIZE)

        for ty in range(top_tile, bottom_tile + 1):
            for tx in range(left_tile, right_tile + 1):
                if not tilemap.is_walkable(tx, ty):
                    tile_rect = pygame.Rect(tx * TILE_SIZE, ty * TILE_SIZE, TILE_SIZE, TILE_SIZE)
                    if rect.colliderect(tile_rect):
                        return True

        if obstacles:
            for obs in obstacles:
                if obs.is_alive and obs.rect.colliderect(rect):
                    return True

        return False

    MAX_STEP = 4.0  # px per sub-step: keeps fast dashes from tunnelling or snapping into walls

    @staticmethod
    def _blocking_rects(rect: pygame.Rect, tilemap, obstacles=None) -> list[pygame.Rect]:
        """All solid tile/obstacle rects overlapping `rect`."""
        blockers = []
        for ty in range(int(rect.top // TILE_SIZE), int((rect.bottom - 1) // TILE_SIZE) + 1):
            for tx in range(int(rect.left // TILE_SIZE), int((rect.right - 1) // TILE_SIZE) + 1):
                if not tilemap.is_walkable(tx, ty):
                    blockers.append(pygame.Rect(tx * TILE_SIZE, ty * TILE_SIZE, TILE_SIZE, TILE_SIZE))
        if obstacles:
            for obs in obstacles:
                if obs.is_alive and obs.rect.colliderect(rect):
                    blockers.append(obs.rect)
        return blockers

    @staticmethod
    def _depenetrate(hitbox: pygame.Rect, tilemap, obstacles=None):
        """Push a hitbox that is already inside a solid (e.g. gate closing on it) out by the smallest distance."""
        for _ in range(4):
            blockers = CollisionSystem._blocking_rects(hitbox, tilemap, obstacles)
            if not blockers:
                return
            b = blockers[0]
            options = [
                (hitbox.right - b.left, -1, 0),
                (b.right - hitbox.left, 1, 0),
                (hitbox.bottom - b.top, 0, -1),
                (b.bottom - hitbox.top, 0, 1),
            ]
            # Prefer a push that lands on free space
            for dist, ox, oy in sorted(options):
                trial = hitbox.move(ox * dist, oy * dist)
                if not CollisionSystem._blocking_rects(trial, tilemap, obstacles):
                    hitbox.move_ip(ox * dist, oy * dist)
                    break
            else:
                dist, ox, oy = min(options)
                hitbox.move_ip(ox * dist, oy * dist)

    @staticmethod
    def move_and_slide(entity, dx: float, dy: float, tilemap, obstacles=None) -> tuple[float, float]:
        """
        Move entity by (dx, dy) in small sub-steps with separate axis checks for smooth sliding.
        The hitbox is checked exactly where it is drawn/used (including its vertical offset), and a
        blocked axis is resolved against the actual blocking rect, so dashes never end inside a wall.
        Returns the (dx, dy) that was not blocked (0 on a blocked axis).
        """
        hitbox = entity.get_hitbox() if hasattr(entity, "get_hitbox") else entity.rect
        off_y = getattr(entity, "HITBOX_OFFSET_Y", 0)

        hitbox.centerx = int(entity.pos_x)
        hitbox.centery = int(entity.pos_y + off_y)
        CollisionSystem._depenetrate(hitbox, tilemap, obstacles)
        entity.pos_x = float(hitbox.centerx) if hitbox.centerx != int(entity.pos_x) else entity.pos_x
        entity.pos_y = float(hitbox.centery - off_y) if hitbox.centery != int(entity.pos_y + off_y) else entity.pos_y

        steps = max(1, math.ceil(max(abs(dx), abs(dy)) / CollisionSystem.MAX_STEP))
        sdx, sdy = dx / steps, dy / steps
        blocked_x = blocked_y = False

        for _ in range(steps):
            if sdx and not blocked_x:
                entity.pos_x += sdx
                hitbox.centerx = int(entity.pos_x)
                blockers = CollisionSystem._blocking_rects(hitbox, tilemap, obstacles)
                if blockers:
                    if sdx > 0:
                        hitbox.right = min(b.left for b in blockers)
                    else:
                        hitbox.left = max(b.right for b in blockers)
                    entity.pos_x = float(hitbox.centerx)
                    blocked_x = True

            if sdy and not blocked_y:
                entity.pos_y += sdy
                hitbox.centery = int(entity.pos_y + off_y)
                blockers = CollisionSystem._blocking_rects(hitbox, tilemap, obstacles)
                if blockers:
                    if sdy > 0:
                        hitbox.bottom = min(b.top for b in blockers)
                    else:
                        hitbox.top = max(b.bottom for b in blockers)
                    entity.pos_y = float(hitbox.centery - off_y)
                    blocked_y = True

            if blocked_x and blocked_y:
                break

        # Sync main entity rect with resolved position
        if hasattr(entity, "sync_rect"):
            entity.sync_rect()

        return (0 if blocked_x else dx), (0 if blocked_y else dy)

    @staticmethod
    def apply_knockback(entity, dir_x: float, dir_y: float, distance: float, tilemap, obstacles=None, steps: int = 6):
        """
        Sub-stepped knockback physics. Halts smoothly when encountering obstacles/walls
        without penetrating or sticking inside solid tiles.
        """
        mag = math.hypot(dir_x, dir_y)
        if mag == 0 or distance <= 0:
            return

        norm_x = dir_x / mag
        norm_y = dir_y / mag
        step_dist = distance / steps

        for _ in range(steps):
            step_dx = norm_x * step_dist
            step_dy = norm_y * step_dist
            res_dx, res_dy = CollisionSystem.move_and_slide(entity, step_dx, step_dy, tilemap, obstacles)
            # If motion blocked completely in both dimensions, abort remaining knockback steps
            if res_dx == 0 and res_dy == 0:
                break

    @staticmethod
    def circle_overlap(pos1: tuple[float, float], r1: float, pos2: tuple[float, float], r2: float) -> bool:
        """Check distance between two circles for radial triggers or attacks."""
        dx = pos1[0] - pos2[0]
        dy = pos1[1] - pos2[1]
        dist_sq = dx * dx + dy * dy
        return dist_sq <= (r1 + r2) ** 2
