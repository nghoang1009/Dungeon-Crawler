import pygame
from settings import (
    TILE_SIZE, TILE_WALL, TILE_DOOR,
    TILE_CLOSED_GATE, TILE_OPEN_GATE, TILE_TRAP, TILE_EXIT, WALKABLE_TILES,
    FOG_ENABLED, FOG_RADIUS, FOG_EXPLORED_ALPHA
)
from core.sprite_loader import SpriteSheetLoader

class TileMap:
    """
    Grid Tilemap for 2D Action Roguelike.
    Directly renders crisp pixel-art tiles from tiles.png (walls, stone floors, doors, stairs, traps).
    """
    def __init__(self, grid: list[list[int]]):
        self.grid = grid
        self.height = len(grid)
        self.width = len(grid[0]) if self.height > 0 else 0

        self.explored = [[False for _ in range(self.width)] for _ in range(self.height)]
        self.visible = [[False for _ in range(self.width)] for _ in range(self.height)]

        self.sprite_loader = SpriteSheetLoader()
        self.sprite_loader.initialize()

        self._tile_surf_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._fog_key = None
        self._wall_edge: list[list[bool]] = []
        self._rebuild_wall_edges()
        self._fog_unexplored = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        self._fog_unexplored.fill((10, 10, 14, 255))
        self._fog_explored = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
        self._fog_explored.fill((15, 12, 22, FOG_EXPLORED_ALPHA))

    def is_valid(self, tx: int, ty: int) -> bool:
        return 0 <= tx < self.width and 0 <= ty < self.height

    def get_tile(self, tx: int, ty: int) -> int:
        if self.is_valid(tx, ty):
            return self.grid[ty][tx]
        return TILE_WALL

    def set_tile(self, tx: int, ty: int, tile_id: int):
        if self.is_valid(tx, ty):
            self.grid[ty][tx] = tile_id
            self._fog_key = None
            self._rebuild_wall_edges()

    def _rebuild_wall_edges(self):
        """A wall is drawn as brick face only when it borders open space; solid rock stays black void."""
        self._wall_edge = [[False] * self.width for _ in range(self.height)]
        for ty in range(self.height):
            for tx in range(self.width):
                if self.grid[ty][tx] != TILE_WALL:
                    continue
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx, ny = tx + dx, ty + dy
                        if self.is_valid(nx, ny) and self.grid[ny][nx] != TILE_WALL:
                            self._wall_edge[ty][tx] = True

    def is_walkable(self, tx: int, ty: int, obstacles=None, closed_gates=None) -> bool:
        if not self.is_valid(tx, ty):
            return False

        tile_id = self.grid[ty][tx]
        if tile_id not in WALKABLE_TILES:
            return False

        if tile_id == TILE_CLOSED_GATE:
            return False

        if closed_gates:
            for g in closed_gates:
                if (g.tx, g.ty) == (tx, ty) and not g.is_open:
                    return False

        if obstacles:
            for obs in obstacles:
                if obs.is_alive and (obs.tx, obs.ty) == (tx, ty):
                    return False

        return True

    def is_opaque(self, tx: int, ty: int, obstacles=None, closed_gates=None) -> bool:
        if not self.is_valid(tx, ty):
            return True
        tile_id = self.grid[ty][tx]
        if tile_id in (TILE_WALL, TILE_CLOSED_GATE):
            return True

        if closed_gates:
            for g in closed_gates:
                if (g.tx, g.ty) == (tx, ty) and not g.is_open:
                    return True

        if obstacles:
            for obs in obstacles:
                if obs.is_alive and (obs.tx, obs.ty) == (tx, ty):
                    return True
        return False

    def update_fog_of_war(self, player_tx: int, player_ty: int, radius: float = FOG_RADIUS):
        key = (player_tx, player_ty, radius)
        if key == self._fog_key:
            return
        self._fog_key = key

        for row in self.visible:
            row[:] = [False] * self.width

        rad_int = int(radius) + 1
        min_x = max(0, player_tx - rad_int)
        max_x = min(self.width - 1, player_tx + rad_int)
        min_y = max(0, player_ty - rad_int)
        max_y = min(self.height - 1, player_ty + rad_int)

        r_sq = radius * radius

        for ty in range(min_y, max_y + 1):
            for tx in range(min_x, max_x + 1):
                dist_sq = (tx - player_tx) ** 2 + (ty - player_ty) ** 2
                if dist_sq <= r_sq:
                    if self.has_line_of_sight(player_tx, player_ty, tx, ty):
                        self.visible[ty][tx] = True
                        self.explored[ty][tx] = True

    def has_line_of_sight(self, x0: int, y0: int, x1: int, y1: int, obstacles=None, closed_gates=None) -> bool:
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        curr_x, curr_y = x0, y0
        while (curr_x, curr_y) != (x1, y1):
            if (curr_x, curr_y) != (x0, y0) and (curr_x, curr_y) != (x1, y1):
                if self.is_opaque(curr_x, curr_y, obstacles, closed_gates):
                    return False

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                curr_x += sx
            if e2 < dx:
                err += dx
                curr_y += sy

        return True

    FLOOR_VARIANTS = ("floor_0", "floor_skull", "floor_crack_1", "floor_crack_2", "floor_crack_3")

    @staticmethod
    def _floor_variant(tx: int, ty: int) -> int:
        """Mostly plain floor, with the occasional skull / crack decal (deterministic per tile)."""
        h = (tx * 7919 + ty * 104729) % 41
        return h + 1 if h < 4 else 0

    def get_tile_surface(self, tile_id: int, tx: int, ty: int) -> pygame.Surface:
        var = self._floor_variant(tx, ty) if tile_id not in (
            TILE_WALL, TILE_DOOR, TILE_CLOSED_GATE, TILE_OPEN_GATE, TILE_EXIT, TILE_TRAP) else 0
        key = (tile_id, var)
        surf = self._tile_surf_cache.get(key)
        if surf is None:
            surf = self._tile_surf_cache[key] = self._build_tile_surface(tile_id, tx, ty)
        return surf

    def _build_tile_surface(self, tile_id: int, tx: int, ty: int) -> pygame.Surface:
        """Retrieves exact real sprite from tiles.png according to tiles.txt mapping."""
        if tile_id == TILE_WALL:
            # 3.a Stone brick wall top
            return self.sprite_loader.get_tile_wall(style=1)
        elif tile_id == TILE_DOOR:
            # 17.d Framed door open
            return self.sprite_loader.get_tile_door(open_state=True)
        elif tile_id == TILE_CLOSED_GATE:
            # 17.g Grated iron door
            return self.sprite_loader.get_tile_gate(open_state=False)
        elif tile_id == TILE_OPEN_GATE:
            # 17.d Open door passage
            return self.sprite_loader.get_tile_gate(open_state=True)
        elif tile_id == TILE_EXIT:
            # 17.h Staircase down
            return self.sprite_loader.get_tile_stairs_down()
        elif tile_id == TILE_TRAP:
            # 17.q Spikes up
            return self.sprite_loader.get_tile_trap()
        else:
            # 7.b / 7.c / 7.d Natural Stone Floor variations
            asset = self.sprite_loader.get_asset_tile(self.FLOOR_VARIANTS[self._floor_variant(tx, ty)])
            if asset:
                return asset
            return self.sprite_loader.get_tile_floor(variant=(tx * 7 + ty * 13) % 3)

    def render(self, surface: pygame.Surface, camera):
        start_col = max(0, int(camera.offset_x // TILE_SIZE) - 1)
        end_col = min(self.width, int((camera.offset_x + camera.width) // TILE_SIZE) + 2)
        start_row = max(0, int(camera.offset_y // TILE_SIZE) - 1)
        end_row = min(self.height, int((camera.offset_y + camera.height) // TILE_SIZE) + 2)

        for ty in range(start_row, end_row):
            for tx in range(start_col, end_col):
                screen_x, screen_y = camera.apply_pos(tx * TILE_SIZE, ty * TILE_SIZE)

                if FOG_ENABLED and not self.explored[ty][tx]:
                    # Fully opaque fog: skip the sprite and paint the fog tile directly.
                    surface.blit(self._fog_unexplored, (screen_x, screen_y))
                    continue

                tile_id = self.grid[ty][tx]
                if tile_id == TILE_WALL and not self._wall_edge[ty][tx]:
                    surface.fill((0, 0, 0), (screen_x, screen_y, TILE_SIZE, TILE_SIZE))
                    continue

                surface.blit(self.get_tile_surface(tile_id, tx, ty), (screen_x, screen_y))

                if FOG_ENABLED and not self.visible[ty][tx]:
                    surface.blit(self._fog_explored, (screen_x, screen_y))
