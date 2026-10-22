
class RoomType:
    START = "START ROOM"
    COMBAT = "COMBAT ROOM"
    ELITE = "ELITE ROOM"
    TRAP = "TRAP ROOM"
    TREASURE = "TREASURE ROOM"
    SHOP = "SHOP ROOM"
    NPC = "NPC ROOM"
    RESCUE = "RESCUE ROOM"
    SURVIVAL = "SURVIVAL ROOM"
    EVENT = "EVENT ROOM"
    BOSS = "BOSS ROOM"
    NORMAL = "NORMAL ROOM"


class RoomState:
    UNVISITED = "UNVISITED"
    ACTIVE = "ACTIVE"
    CLEARED = "CLEARED"


class Room:
    """
    Represents an allocated room in the procedural dungeon.
    Tracks clearance status, room challenges, state, enemies, and bounds.
    """
    def __init__(self, x: int, y: int, width: int, height: int, room_type: str = RoomType.NORMAL):
        self.x = int(x)
        self.y = int(y)
        self.width = int(width)
        self.height = int(height)
        self.room_type = room_type
        self.state = RoomState.UNVISITED

        self.left = self.x
        self.right = self.x + self.width
        self.top = self.y
        self.bottom = self.y + self.height

        self.center_x = self.x + self.width // 2
        self.center_y = self.y + self.height // 2

        self.connected_rooms = []
        self.is_cleared = False
        self.has_visited = False

        # Room-graph metadata (assigned by DungeonGenerator after connection)
        self.room_id = ""        # Branch label shown on the minimap, e.g. "A0", "B2"
        self.depth = 0           # BFS distance from the Start room in the room graph
        self.spawn_positions: list[tuple[int, int]] = []  # Notable tiles: player spawn, chests, traps, exit

        # Room Combat & Special Data
        self.enemies = []
        self.door_tiles = []  # Coordinates of entrance tiles to lock during combat
        self.survival_timer = 20.0
        self.wave_timer = 4.0
        self.is_rescued = False
        self.puzzle_solved = False
        self.reward_spawned = False

    @property
    def center(self) -> tuple[int, int]:
        return (self.center_x, self.center_y)

    def is_pos_inside(self, gx: int, gy: int) -> bool:
        return self.x <= gx < self.right and self.y <= gy < self.bottom

    def is_pos_inside_inner(self, gx: int, gy: int) -> bool:
        return self.x < gx < self.right - 1 and self.y < gy < self.bottom - 1

    def intersects(self, other: "Room", padding: int = 1) -> bool:
        return not (
            self.right + padding < other.left or
            self.left - padding > other.right or
            self.bottom + padding < other.top or
            self.top - padding > other.bottom
        )

    def get_inner_tiles(self) -> list[tuple[int, int]]:
        tiles = []
        for r_y in range(self.y + 1, self.bottom - 1):
            for r_x in range(self.x + 1, self.right - 1):
                tiles.append((r_x, r_y))
        return tiles

    def get_random_floor_tile(self, rng=None) -> tuple[int, int]:
        import random
        r = rng if rng else random
        inner_w = max(1, self.width - 2)
        inner_h = max(1, self.height - 2)
        tx = self.x + 1 + r.randint(0, inner_w - 1)
        ty = self.y + 1 + r.randint(0, inner_h - 1)
        return (tx, ty)
