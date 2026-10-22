import math
import time
import pygame
from settings import (
    SCREEN_WIDTH, TILE_WALL, TILE_CLOSED_GATE, TILE_OPEN_GATE, TILE_EXIT, TILE_CHEST, ROOM_MINIMAP_COLORS
)
from dungeon.room import RoomType
from ui.theme import draw_panel, draw_text, shade, TEXT_DIM, ACCENT

TILE_PX = 4                  # minimap pixels per dungeon tile
MARGIN = 14
PAD = 8
FADE_NEAR = 0.26             # opacity while the player is behind the minimap
FADE_FAR = 0.94
FADE_SPEED = 5.0             # opacity change per second
FLOOR_COLOR = (92, 84, 112)
FLOOR_FOG = (58, 53, 74)

MARKERS = {
    RoomType.BOSS: ("B", (255, 96, 96)),
    RoomType.TREASURE: ("T", (255, 214, 90)),
    RoomType.SHOP: ("$", (110, 230, 240)),
    RoomType.NPC: ("N", (150, 220, 150)),
    RoomType.RESCUE: ("N", (150, 220, 150)),
    RoomType.SURVIVAL: ("!", (255, 160, 90)),
    RoomType.EVENT: ("!", (230, 130, 240)),
    RoomType.TRAP: ("!", (255, 120, 120)),
}


class Minimap:
    """
    Corner minimap drawn from the real explored floor plan (not straight lines between room centres):
    - Explored floor tiles are painted incrementally onto a cached surface, brighter near the player.
    - Discovered rooms get a soft tint by room type plus a small badge (B boss, T treasure, $ shop...).
    - The current room is outlined; player is a pulsing dot with a facing tick, the boss a red dot.
    - It fades out whenever the player (or the boss) walks behind it, and M shows / hides it.
    """
    def __init__(self, *_ignored):
        self.visible = True
        self.font = pygame.font.SysFont("consolas", 10, bold=True)
        self.font_title = pygame.font.SysFont("consolas", 11, bold=True)
        self._alpha = FADE_FAR
        self._last_time = time.perf_counter()
        self._map_id = None
        self._map_surf: pygame.Surface | None = None
        self._painted: list[list[int]] = []
        self._discovered: set[int] = set()

    # --------------------------------------------------------------- helpers
    def toggle(self):
        self.visible = not self.visible

    def _reset_for(self, tilemap):
        self._map_id = id(tilemap)
        self._map_surf = pygame.Surface((tilemap.width * TILE_PX, tilemap.height * TILE_PX), pygame.SRCALPHA)
        self._painted = [[0] * tilemap.width for _ in range(tilemap.height)]
        self._discovered = set()

    def _tile_color(self, tilemap, tx: int, ty: int, lit: bool):
        tile = tilemap.grid[ty][tx]
        if tile == TILE_WALL:
            return None
        if tile == TILE_CLOSED_GATE:
            return (210, 70, 70)
        if tile == TILE_OPEN_GATE:
            return (84, 190, 104)
        if tile == TILE_EXIT:
            return (70, 220, 170)
        if tile == TILE_CHEST:
            return (232, 186, 70)
        return FLOOR_COLOR if lit else FLOOR_FOG

    def _paint_tile(self, tilemap, tx: int, ty: int, lit: bool):
        color = self._tile_color(tilemap, tx, ty, lit)
        rect = (tx * TILE_PX, ty * TILE_PX, TILE_PX, TILE_PX)
        if color is None:
            self._map_surf.fill((0, 0, 0, 0), rect)
        else:
            self._map_surf.fill((*color, 255), rect)

    def _sync(self, tilemap):
        """Repaints only tiles whose explored/visible/gate state changed since the last frame."""
        for ty in range(tilemap.height):
            exp_row, vis_row, painted = tilemap.explored[ty], tilemap.visible[ty], self._painted[ty]
            for tx in range(tilemap.width):
                if not exp_row[tx]:
                    continue
                tile = tilemap.grid[ty][tx]
                state = 3 if tile == TILE_WALL else (2 if vis_row[tx] else 1)
                # Gates / exit / chests keep their own colour whatever the lighting
                key = state * 100 + tile
                if painted[tx] != key:
                    self._paint_tile(tilemap, tx, ty, state == 2)
                    painted[tx] = key

    def _is_room_discovered(self, room, tilemap) -> bool:
        """A room is discovered once any of its tiles has been explored (sticky)."""
        rid = id(room)
        if rid in self._discovered:
            return True
        for ty in range(room.y, room.bottom):
            for tx in range(room.x, room.right):
                if tilemap.explored[ty][tx]:
                    self._discovered.add(rid)
                    return True
        return False

    # ---------------------------------------------------------------- render
    def render(self, surface: pygame.Surface, tilemap, player, enemies, boss, rooms=None, camera=None,
               floor: int | None = None):
        if not self.visible or tilemap.width == 0 or tilemap.height == 0:
            return

        now = time.perf_counter()
        dt = min(0.1, now - self._last_time)
        self._last_time = now

        if self._map_id != id(tilemap):
            self._reset_for(tilemap)
        self._sync(tilemap)

        map_w, map_h = tilemap.width * TILE_PX, tilemap.height * TILE_PX
        header_h = 18
        panel = pygame.Rect(0, 0, map_w + PAD * 2, map_h + PAD * 2 + header_h)
        panel.topright = (SCREEN_WIDTH - MARGIN, MARGIN)

        # Fade while the player or the boss is behind the minimap
        target = FADE_FAR
        if camera is not None:
            hot = panel.inflate(28, 28)
            for ent in (player, boss if boss and boss.is_alive else None):
                if ent is not None and hot.collidepoint(camera.apply_pos(ent.pos_x, ent.pos_y)):
                    target = FADE_NEAR
        step = FADE_SPEED * dt
        self._alpha += max(-step, min(step, target - self._alpha))

        layer = pygame.Surface(panel.size, pygame.SRCALPHA)
        draw_panel(layer, layer.get_rect(), alpha=205)
        draw_text(layer, self.font_title, "MAP" if floor is None else f"FLOOR {floor}", ACCENT, (PAD + 2, 5))
        draw_text(layer, self.font, "[M]", TEXT_DIM, (panel.width - PAD - 2, 6), anchor="topright")

        ox, oy = PAD, PAD + header_h
        layer.blit(self._map_surf, (ox, oy))

        def to_px(tx: float, ty: float) -> tuple[int, int]:
            return int(ox + tx * TILE_PX), int(oy + ty * TILE_PX)

        here = (player.grid_x, player.grid_y) if player else None
        if rooms:
            for room in rooms:
                if not self._is_room_discovered(room, tilemap):
                    continue
                color = ROOM_MINIMAP_COLORS.get(room.room_type, (130, 120, 155))
                rx, ry = to_px(room.x, room.y)
                rect = pygame.Rect(rx, ry, room.width * TILE_PX, room.height * TILE_PX)
                tint = pygame.Surface(rect.size, pygame.SRCALPHA)
                tint.fill((*color, 70))
                layer.blit(tint, rect.topleft)

                in_room = bool(here and room.is_pos_inside(*here))
                pygame.draw.rect(layer, (245, 245, 255) if in_room else shade(color, 0.85), rect,
                                 width=2 if in_room else 1)

                marker = MARKERS.get(room.room_type)
                if marker:
                    glyph = "E" if room.room_type == RoomType.BOSS and not (boss and boss.is_alive) else marker[0]
                    badge = pygame.Rect(0, 0, 14, 14)
                    badge.center = rect.center
                    pygame.draw.circle(layer, (14, 12, 22), badge.center, 8)
                    pygame.draw.circle(layer, marker[1], badge.center, 8, width=1)
                    layer.blit(self.font.render(glyph, True, marker[1]),
                               self.font.render(glyph, True, marker[1]).get_rect(center=badge.center))

        pulse = 0.5 + 0.5 * math.sin(now * 5.0)

        if boss and boss.is_alive and self._map_surf is not None:
            if tilemap.explored[boss.grid_y][boss.grid_x]:
                bx, by = to_px(boss.grid_x + 0.5, boss.grid_y + 0.5)
                pygame.draw.circle(layer, (255, 70, 70), (bx, by), 3 + int(pulse))
                pygame.draw.circle(layer, (255, 255, 255), (bx, by), 3 + int(pulse), width=1)

        if player:
            px, py = to_px(player.grid_x + 0.5, player.grid_y + 0.5)
            pygame.draw.circle(layer, (80, 255, 140), (px, py), 5, width=1 if pulse < 0.5 else 2)
            pygame.draw.circle(layer, (255, 255, 255), (px, py), 3)
            fx, fy = player.facing_dir
            mag = math.hypot(fx, fy) or 1.0
            pygame.draw.line(layer, (255, 255, 255), (px, py), (px + fx / mag * 7, py + fy / mag * 7), 2)

        layer.set_alpha(int(255 * self._alpha))
        surface.blit(layer, panel.topleft)
