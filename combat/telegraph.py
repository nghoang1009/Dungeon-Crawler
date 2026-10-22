import pygame
import math
from settings import TILE_SIZE
from combat.effects import color_of, element_for

class TelegraphShape:
    TILES = "tiles"
    LINE = "line"
    CONE = "cone"
    CIRCLE = "circle"
    CROSS = "cross"
    RING = "ring"          # donut: hits between inner_radius and radius, the middle is safe
    ROOM_WIDE = "room_wide"


class TelegraphZone:
    """
    Visual warning danger zone on grid tiles / screen positions
    supporting multiple shapes (Circle, Line, Cone, Cross, Room-Wide, Tiles)
    with a countdown timer (0.5s–1.0s) enabling 'Read -> Dodge -> Punish' mechanics.
    """
    def __init__(self,
                 tiles: list[tuple[int, int]] | None = None,
                 duration: float = 0.75,
                 damage: int = 25,
                 shape: str = TelegraphShape.TILES,
                 origin: tuple[float, float] | None = None,
                 target: tuple[float, float] | None = None,
                 radius: float = 48.0,
                 angle_span: float = 60.0,
                 status_effect: str | None = None,
                 inner_radius: float = 0.0):
        self.tiles = tiles if tiles is not None else []
        self.duration = duration
        self.age = 0.0
        self.damage = damage
        self.shape = shape
        self.origin = origin          # (world_x, world_y)
        self.target = target          # (world_x, world_y)
        self.radius = radius          # in pixels
        self.angle_span = angle_span  # in degrees for cone
        self.inner_radius = inner_radius  # safe middle of a RING
        self.status_effect = status_effect
        self.is_resolved = False
        self.is_active = True
        self.element = None           # caster's element, used for colour / impact effect when there is no status

    def update(self, dt: float) -> bool:
        """Updates timer. Returns True when warning finishes and triggers damage strike."""
        self.age += dt
        if self.age >= self.duration and not self.is_resolved:
            self.is_resolved = True
            self.is_active = False
            return True
        return False

    def check_hit(self, player) -> bool:
        """Checks if Player is currently inside this telegraph danger area."""
        if not player.is_alive or player.is_invulnerable:
            return False

        px, py = player.pos_x, player.pos_y
        pgx, pgy = player.grid_x, player.grid_y

        if self.shape in (TelegraphShape.TILES, TelegraphShape.ROOM_WIDE):
            return (pgx, pgy) in self.tiles

        elif self.shape == TelegraphShape.CIRCLE:
            if not self.origin:
                return (pgx, pgy) in self.tiles
            ox, oy = self.origin
            return math.hypot(px - ox, py - oy) <= self.radius

        elif self.shape == TelegraphShape.RING:
            if not self.origin:
                return (pgx, pgy) in self.tiles
            ox, oy = self.origin
            return self.inner_radius <= math.hypot(px - ox, py - oy) <= self.radius

        elif self.shape == TelegraphShape.LINE:
            if not self.origin or not self.target:
                return (pgx, pgy) in self.tiles
            ox, oy = self.origin
            tx, ty = self.target
            dx = tx - ox
            dy = ty - oy
            seg_len = math.hypot(dx, dy)
            if seg_len == 0:
                return math.hypot(px - ox, py - oy) <= self.radius
            # Distance from point to line segment
            t = max(0.0, min(1.0, ((px - ox) * dx + (py - oy) * dy) / (seg_len * seg_len)))
            proj_x = ox + t * dx
            proj_y = oy + t * dy
            return math.hypot(px - proj_x, py - proj_y) <= self.radius

        elif self.shape == TelegraphShape.CONE:
            if not self.origin or not self.target:
                return (pgx, pgy) in self.tiles
            ox, oy = self.origin
            tx, ty = self.target
            dist = math.hypot(px - ox, py - oy)
            if dist > self.radius:
                return False
            # Angle check
            center_angle = math.atan2(ty - oy, tx - ox)
            player_angle = math.atan2(py - oy, px - ox)
            diff = abs(math.atan2(math.sin(player_angle - center_angle), math.cos(player_angle - center_angle)))
            return diff <= math.radians(self.angle_span / 2.0)

        elif self.shape == TelegraphShape.CROSS:
            if not self.origin:
                return (pgx, pgy) in self.tiles
            ox, oy = self.origin
            half_w = self.radius * 0.35
            # Horizontal bar check or vertical bar check
            in_h = (abs(py - oy) <= half_w) and (abs(px - ox) <= self.radius)
            in_v = (abs(px - ox) <= half_w) and (abs(py - oy) <= self.radius)
            return in_h or in_v

        return (pgx, pgy) in self.tiles

    def render(self, surface: pygame.Surface, camera):
        """
        Warning area. A faint base shows where the strike will land and a brighter fill grows over it, so the
        moment of impact can be read at a glance. Colour follows the element (fire / poison / ice / default red).
        """
        if not self.is_active:
            return

        progress = min(1.0, self.age / self.duration)
        color = color_of(element_for(self.status_effect, self.element))
        pulse_a = 0.5 + 0.5 * math.sin(self.age * 14.0)
        last_flash = 1.0 if progress > 0.82 else 0.0       # blink right before the hit
        base = (*color, int(34 + 20 * pulse_a))
        grow = (*color, int(80 + 90 * progress + 40 * last_flash))
        edge = (255, 235, 150, min(255, int(150 + 100 * progress)))

        if self.shape in (TelegraphShape.TILES, TelegraphShape.ROOM_WIDE) or (not self.origin and self.tiles):
            alpha = int(60 + 110 * progress + 40 * last_flash)
            for tx, ty in self.tiles:
                screen_x, screen_y = camera.apply_pos(tx * TILE_SIZE, ty * TILE_SIZE)
                tile_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                tile_surf.fill((*color, alpha))
                pygame.draw.rect(tile_surf, edge, (0, 0, TILE_SIZE, TILE_SIZE), 2)
                surface.blit(tile_surf, (screen_x, screen_y))
            return

        if self.shape == TelegraphShape.CIRCLE and self.origin:
            sox, soy = camera.apply_pos(*self.origin)
            r = int(self.radius)
            c_surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            c = (r + 2, r + 2)
            pygame.draw.circle(c_surf, base, c, r)
            pygame.draw.circle(c_surf, grow, c, max(2, int(r * progress)))
            pygame.draw.circle(c_surf, edge, c, r, 2)
            surface.blit(c_surf, (sox - c[0], soy - c[1]))

        elif self.shape == TelegraphShape.RING and self.origin:
            sox, soy = camera.apply_pos(*self.origin)
            r = int(self.radius)
            inner = int(self.inner_radius)
            ring_surf = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            c = (r + 2, r + 2)
            pygame.draw.circle(ring_surf, base, c, r)
            pygame.draw.circle(ring_surf, grow, c, max(2, int(inner + (r - inner) * progress)))
            if inner > 0:
                pygame.draw.circle(ring_surf, (0, 0, 0, 0), c, inner)
                pygame.draw.circle(ring_surf, edge, c, inner, 2)
            pygame.draw.circle(ring_surf, edge, c, r, 2)
            surface.blit(ring_surf, (sox - c[0], soy - c[1]))

        elif self.shape == TelegraphShape.LINE and self.origin and self.target:
            ox, oy = self.origin
            tx, ty = self.target
            sox, soy = camera.apply_pos(ox, oy)
            stx, sty = camera.apply_pos(tx, ty)
            w = max(4, int(self.radius * 2))
            line_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            pygame.draw.line(line_surf, base, (sox, soy), (stx, sty), w)
            gx, gy = sox + (stx - sox) * progress, soy + (sty - soy) * progress     # the strike "travels" down the line
            pygame.draw.line(line_surf, grow, (sox, soy), (gx, gy), w)
            pygame.draw.line(line_surf, edge, (sox, soy), (stx, sty), max(2, w // 5))
            surface.blit(line_surf, (0, 0))

        elif self.shape == TelegraphShape.CONE and self.origin and self.target:
            ox, oy = self.origin
            tx, ty = self.target
            sox, soy = camera.apply_pos(ox, oy)
            center_ang = math.atan2(ty - oy, tx - ox)
            half_ang = math.radians(self.angle_span / 2.0)
            cone_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)

            def cone_points(radius):
                pts = [(sox, soy)]
                for k in range(11):
                    ang = center_ang - half_ang + (2 * half_ang * (k / 10))
                    pts.append((sox + math.cos(ang) * radius, soy + math.sin(ang) * radius))
                return pts

            pygame.draw.polygon(cone_surf, base, cone_points(self.radius))
            pygame.draw.polygon(cone_surf, grow, cone_points(self.radius * max(0.05, progress)))
            pygame.draw.lines(cone_surf, edge, True, cone_points(self.radius), 2)
            surface.blit(cone_surf, (0, 0))

        elif self.shape == TelegraphShape.CROSS and self.origin:
            sox, soy = camera.apply_pos(*self.origin)
            r = int(self.radius)
            hw = max(4, int(r * 0.35))
            cross_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            arms = ((0, r - hw // 2, r * 2, hw), (r - hw // 2, 0, hw, r * 2))
            for rect in arms:
                pygame.draw.rect(cross_surf, base, rect)
            g = int(r * progress)
            pygame.draw.rect(cross_surf, grow, (r - g, r - hw // 2, g * 2, hw))
            pygame.draw.rect(cross_surf, grow, (r - hw // 2, r - g, hw, g * 2))
            for rect in arms:
                pygame.draw.rect(cross_surf, edge, rect, 1)
            surface.blit(cross_surf, (sox - r, soy - r))

        else:
            for tx, ty in self.tiles:
                screen_x, screen_y = camera.apply_pos(tx * TILE_SIZE, ty * TILE_SIZE)
                tile_surf = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
                tile_surf.fill(grow)
                pygame.draw.rect(tile_surf, edge, (0, 0, TILE_SIZE, TILE_SIZE), 2)
                surface.blit(tile_surf, (screen_x, screen_y))
