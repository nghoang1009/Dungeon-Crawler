import random
import math
from collections import deque
from dungeon.bsp import BSPNode
from dungeon.room import Room, RoomType
from world.gate import Gate, BossRoomController
from settings import (
    MAP_WIDTH, MAP_HEIGHT, DUNGEON_MAX_ATTEMPTS,
    TILE_WALL, TILE_FLOOR, TILE_PLAYER_SPAWN,
    TILE_EXIT, TILE_CHEST, TILE_TRAP, TILE_OPEN_GATE,
    BOSS_ROOM_MIN_SIZE, BOSS_ROOM_MAX_SIZE, BOSS_ROOM_SIZE_BY_FLOOR
)

ARENA_SLIDE = 16  # how far (tiles) the arena may shift from the original room centre
MIN_ARENA = 13  # smallest boss arena (tiles) the generator will fall back to


class DungeonGenerator:
    """
    Procedural Dungeon Generator producing dynamic floor layouts:
    - 8-12 rooms per floor across Floors 1 to 10.
    - Diverse room shapes (Square Arena, L-Shape, Cross, Pillar Room).
    - Multi-branch and loop topologies with rich room archetypes:
      (Start, Combat, Elite, Treasure, Shop, Rescue, Survival, Event, Trap, Boss Arena).
    """
    def __init__(self,
                 width: int = MAP_WIDTH,
                 height: int = MAP_HEIGHT,
                 target_room_count: int = 10,
                 seed: int | None = None,
                 floor: int = 1):
        self.width = width
        self.height = height
        self.target_room_count = target_room_count
        self.floor = floor

        self.seed = seed if seed is not None else random.randint(100000, 999999)
        self.rng = random.Random(self.seed)

        self.grid: list[list[int]] = []
        self.rooms: list[Room] = []
        self.corridors: list[list[tuple[int, int]]] = []
        self.start_room: Room | None = None
        self.boss_room: Room | None = None
        self.treasure_rooms: list[Room] = []
        self.npc_rooms: list[Room] = []
        self.boss_gates: list[Gate] = []
        self.boss_controller: BossRoomController | None = None
        self.root_node: BSPNode | None = None
        self.generation_errors: list[str] = []

    def generate(self) -> list[list[int]]:
        """
        Generates the floor with bounded retries. Every attempt re-seeds the rng
        with (seed, attempt) so retries explore new layouts while the same seed
        always yields the same final map. Raises RuntimeError after the attempt cap.
        """
        self.generation_errors.clear()
        for attempt in range(DUNGEON_MAX_ATTEMPTS):
            self.rng = random.Random(f"{self.seed}:{attempt}")
            errors = self._generate_once()
            if not errors:
                return self.grid
            self.generation_errors = errors

        raise RuntimeError(
            f"Dungeon generation failed for seed {self.seed} after "
            f"{DUNGEON_MAX_ATTEMPTS} attempts. Reasons: {self.generation_errors}"
        )

    def _generate_once(self) -> list[str]:
        self.grid = [[TILE_WALL for _ in range(self.width)] for _ in range(self.height)]
        self.corridors.clear()
        self.boss_gates.clear()
        self.treasure_rooms.clear()
        self.npc_rooms.clear()

        # 1. BSP Tree Subdivisions tuned for 8-12 rooms
        min_leaf = self.rng.randint(9, 12)
        self.root_node = BSPNode(2, 2, self.width - 4, self.height - 4)
        nodes_to_split = [self.root_node]

        while nodes_to_split:
            current = nodes_to_split.pop(0)
            if current.split(min_leaf, self.rng):
                if current.left_child:
                    nodes_to_split.append(current.left_child)
                if current.right_child:
                    nodes_to_split.append(current.right_child)

        # 2. Allocate Varied Shape Rooms in Leaves
        raw_rooms = self.root_node.create_rooms(6, 6, 14, 12, self.rng)

        # Clamp and select target room count (8 to 12 rooms).
        # Prune BSP subtrees that only held truncated rooms so the connection
        # phase can never reference (or carve corridors to) a discarded room.
        self.rooms = raw_rooms[:12]
        if len(self.rooms) < 7:
            return ["Not enough rooms allocated by BSP"]
        self.root_node.prune_to_rooms(set(self.rooms))

        # 3. Classify Action Roguelike Roles with distinct topologies
        self._classify_rooms()

        # 4. Expand Boss Room into a Grand Arena (overlap-safe)
        if not self._expand_boss_room():
            return ["Boss arena too small for the boss"]

        # 5. Connect Tree Nodes with Dynamic Corridors
        self._connect_bsp_nodes(self.root_node)

        # 6. Add extra topological loop corridors
        self._add_topological_loops()

        # 6.5 Build the room graph: BFS depths, branch room_ids, repair isolated rooms
        self._build_room_graph()

        # 7. Carve Corridors into Grid
        for corridor in self.corridors:
            for cx, cy in corridor:
                if 0 <= cx < self.width and 0 <= cy < self.height:
                    self.grid[cy][cx] = TILE_FLOOR

        # 8. Carve Varied Room Shapes
        for room in self.rooms:
            self._carve_room_shape(room)

        # 9. Identify & Install Gates at all Boss Room corridor entrances & find door tiles
        self._install_boss_gates()
        self._find_room_doors()

        # 10. Populate Spawns, Chests (<=2 in Treasure room), and Traps
        self._populate_dungeon_objects()

        # 11. Instantiate BossRoomController
        self.boss_controller = BossRoomController(self.boss_room, self.boss_gates)

        # 12. Validate dungeon structure & reachability
        ok, errors = self.validate_dungeon()
        if not ok:
            return errors

        return []

    def _carve_room_shape(self, room: Room):
        shape_type = self.rng.choice(["rect", "rect", "l_shape", "cross", "pillar_room"])
        if room.room_type == RoomType.BOSS:
            shape_type = "rect"

        for ry in range(room.y, room.bottom):
            for rx in range(room.x, room.right):
                if not (0 <= rx < self.width and 0 <= ry < self.height):
                    continue

                if shape_type == "l_shape":
                    if rx > room.center_x + 1 and ry < room.center_y - 1:
                        continue
                elif shape_type == "cross":
                    if (rx < room.x + 2 or rx > room.right - 3) and (ry < room.y + 2 or ry > room.bottom - 3):
                        continue
                elif shape_type == "pillar_room":
                    if (rx in (room.center_x - 2, room.center_x + 2)) and (ry in (room.center_y - 2, room.center_y + 2)):
                        continue

                self.grid[ry][rx] = TILE_FLOOR

    def _expand_boss_room(self) -> bool:
        """Grows the boss room into an arena sized for the boss. False if no free spot was found."""
        if not self.boss_room:
            return True

        br = self.boss_room
        others = [r for r in self.rooms if r is not br]

        # Try candidate arena sizes, shrinking a tile every two failed attempts (down to MIN_ARENA) so a
        # crowded layout still gets an arena big enough for the boss. Falls back to the original bounds.
        size_min, size_max = BOSS_ROOM_SIZE_BY_FLOOR.get(self.floor, (BOSS_ROOM_MIN_SIZE, BOSS_ROOM_MAX_SIZE))
        for attempt in range(16):
            shrink = attempt // 2
            lo = max(MIN_ARENA, size_min - shrink)
            hi = max(lo, min(size_max - shrink, self.width - 6, self.height - 6))
            boss_w = self.rng.randint(lo, hi)
            boss_h = self.rng.randint(lo, hi)

            # Prefer the original centre, then slide the arena to the nearest free spot
            cx, cy = br.center_x, br.center_y
            offsets = sorted(((dx, dy) for dx in range(-ARENA_SLIDE, ARENA_SLIDE + 1)
                              for dy in range(-ARENA_SLIDE, ARENA_SLIDE + 1)),
                             key=lambda o: o[0] * o[0] + o[1] * o[1])
            placed = None
            for dx, dy in offsets:
                new_x = cx + dx - boss_w // 2
                new_y = cy + dy - boss_h // 2
                if new_x < 2 or new_y < 2 or new_x + boss_w > self.width - 2 or new_y + boss_h > self.height - 2:
                    continue
                candidate = Room(new_x, new_y, boss_w, boss_h, RoomType.BOSS)
                if not any(candidate.intersects(r, padding=2) for r in others):
                    placed = (new_x, new_y)
                    break
            if placed is None:
                continue
            new_x, new_y = placed

            br.x, br.y = new_x, new_y
            br.width, br.height = boss_w, boss_h
            br.left, br.right = new_x, new_x + boss_w
            br.top, br.bottom = new_y, new_y + boss_h
            br.center_x, br.center_y = new_x + boss_w // 2, new_y + boss_h // 2
            return True

        return min(br.width, br.height) >= MIN_ARENA

    def _connect_bsp_nodes(self, node: BSPNode):
        if node.is_leaf:
            return

        if node.left_child:
            self._connect_bsp_nodes(node.left_child)
        if node.right_child:
            self._connect_bsp_nodes(node.right_child)

        if node.left_child and node.right_child:
            r1 = node.left_child.get_room(self.rng)
            r2 = node.right_child.get_room(self.rng)
            if r1 and r2:
                corridor = self._create_l_corridor(r1.center_x, r1.center_y, r2.center_x, r2.center_y)
                self.corridors.append(corridor)
                r1.connected_rooms.append(r2)
                r2.connected_rooms.append(r1)

    def _add_topological_loops(self):
        if len(self.rooms) < 5:
            return
        num_loops = self.rng.randint(1, 3)
        for _ in range(num_loops):
            r1 = self.rng.choice(self.rooms)
            r2 = self.rng.choice(self.rooms)
            if r1 != r2 and r2 not in r1.connected_rooms and r1 != self.boss_room and r2 != self.boss_room:
                corridor = self._create_l_corridor(r1.center_x, r1.center_y, r2.center_x, r2.center_y)
                self.corridors.append(corridor)
                r1.connected_rooms.append(r2)
                r2.connected_rooms.append(r1)

    def _build_room_graph(self):
        """
        Turns the BSP connection list into an explicit room graph:
        - Repairs isolated rooms by connecting them to the nearest connected room.
        - Assigns BFS depth from the Start room.
        - Assigns branch-style room_ids ("A0", "A1", "B0"...) like a dungeon overview map.
        """
        if not self.start_room:
            return

        # Repair isolated rooms (graph-level connectivity)
        for _ in range(len(self.rooms)):
            reached = self._graph_reachable_from_start()
            unreachable = [r for r in self.rooms if r not in reached]
            if not unreachable:
                break

            stranded = min(
                unreachable,
                key=lambda rm: math.hypot(rm.center_x - self.start_room.center_x,
                                          rm.center_y - self.start_room.center_y)
            )
            target = min(
                reached,
                key=lambda rm: math.hypot(rm.center_x - stranded.center_x,
                                          rm.center_y - stranded.center_y)
            )
            corridor = self._create_l_corridor(stranded.center_x, stranded.center_y,
                                               target.center_x, target.center_y)
            self.corridors.append(corridor)
            stranded.connected_rooms.append(target)
            target.connected_rooms.append(stranded)

        # BFS: depths + branch labels
        self.start_room.depth = 0
        self.start_room.room_id = "ST"
        visited = {self.start_room}
        queue = deque([self.start_room])
        next_branch_idx = 0
        branch_of: dict[Room, str] = {}
        branch_counters: dict[str, int] = {}

        while queue:
            current = queue.popleft()
            for neighbor in current.connected_rooms:
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                neighbor.depth = current.depth + 1

                if current is self.start_room:
                    letter = chr(ord('A') + next_branch_idx)
                    next_branch_idx += 1
                    branch_of[neighbor] = letter
                    branch_counters[letter] = 1
                    neighbor.room_id = f"{letter}0"
                else:
                    letter = branch_of.get(current, "X")
                    idx = branch_counters.get(letter, 0)
                    branch_of[neighbor] = letter
                    branch_counters[letter] = idx + 1
                    neighbor.room_id = f"{letter}{idx}"
                queue.append(neighbor)

        # Safety net: every room must carry a unique id
        used_ids = {r.room_id for r in self.rooms if r.room_id}
        for r in self.rooms:
            if not r.room_id or r.room_id in used_ids and sum(1 for o in self.rooms if o.room_id == r.room_id) > 1:
                fallback = f"Z{self.rooms.index(r)}"
                while fallback in used_ids:
                    fallback += "x"
                r.room_id = fallback
                used_ids.add(fallback)

    def _graph_reachable_from_start(self) -> set[Room]:
        if not self.start_room:
            return set()
        seen = {self.start_room}
        queue = deque([self.start_room])
        while queue:
            current = queue.popleft()
            for neighbor in current.connected_rooms:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        return seen

    def _create_l_corridor(self, x1: int, y1: int, x2: int, y2: int) -> list[tuple[int, int]]:
        points = []
        horizontal_first = self.rng.choice([True, False])

        if horizontal_first:
            for x in range(min(x1, x2), max(x1, x2) + 1):
                points.append((x, y1))
                points.append((x, min(y1 + 1, self.height - 2)))
            for y in range(min(y1, y2), max(y1, y2) + 1):
                points.append((x2, y))
                points.append((min(x2 + 1, self.width - 2), y))
        else:
            for y in range(min(y1, y2), max(y1, y2) + 1):
                points.append((x1, y))
                points.append((min(x1 + 1, self.width - 2), y))
            for x in range(min(x1, x2), max(x1, x2) + 1):
                points.append((x, y2))
                points.append((x, min(y2 + 1, self.height - 2)))

        return points

    def _classify_rooms(self):
        self.start_room = self.rooms[0]
        self.start_room.room_type = RoomType.START

        # Furthest room is Boss Arena
        max_dist = -1.0
        best_boss = None
        for room in self.rooms[1:]:
            dist = math.hypot(room.center_x - self.start_room.center_x, room.center_y - self.start_room.center_y)
            if dist > max_dist:
                max_dist = dist
                best_boss = room

        self.boss_room = best_boss if best_boss else self.rooms[-1]
        self.boss_room.room_type = RoomType.BOSS

        remaining = [r for r in self.rooms if r not in (self.start_room, self.boss_room)]
        self.rng.shuffle(remaining)

        # 1 Treasure room
        if remaining:
            treasure_room = remaining.pop(0)
            treasure_room.room_type = RoomType.TREASURE
            self.treasure_rooms.append(treasure_room)

        # 1 Shop room
        if remaining:
            shop_room = remaining.pop(0)
            shop_room.room_type = RoomType.SHOP
            self.npc_rooms.append(shop_room)

        # 1 Special Room (Rescue / Survival / Event / Trap depending on floor)
        if remaining:
            special_room = remaining.pop(0)
            roll_special = self.rng.random()
            if roll_special < 0.35:
                special_room.room_type = RoomType.RESCUE
                self.npc_rooms.append(special_room)
            elif roll_special < 0.65:
                special_room.room_type = RoomType.SURVIVAL
            else:
                special_room.room_type = RoomType.EVENT

        # 1 Elite room
        if remaining:
            elite_room = remaining.pop(0)
            elite_room.room_type = RoomType.ELITE

        # Distribute remaining as Combat / Trap rooms
        for idx, r in enumerate(remaining):
            if idx % 3 == 0:
                r.room_type = RoomType.TRAP
            else:
                r.room_type = RoomType.COMBAT

    def _install_boss_gates(self):
        if not self.boss_room:
            return

        br = self.boss_room
        gate_coords = set()

        # Gates sit in the doorway (the first corridor tile outside the room), not on the room's edge row
        for x in range(br.x, br.right):
            if self.grid[br.y - 1][x] == TILE_FLOOR and self.grid[br.y][x] == TILE_FLOOR:
                gate_coords.add((x, br.y - 1))
            if self.grid[br.bottom][x] == TILE_FLOOR and self.grid[br.bottom - 1][x] == TILE_FLOOR:
                gate_coords.add((x, br.bottom))

        for y in range(br.y, br.bottom):
            if self.grid[y][br.x - 1] == TILE_FLOOR and self.grid[y][br.x] == TILE_FLOOR:
                gate_coords.add((br.x - 1, y))
            if self.grid[y][br.right] == TILE_FLOOR and self.grid[y][br.right - 1] == TILE_FLOOR:
                gate_coords.add((br.right, y))

        for gx, gy in gate_coords:
            self.boss_gates.append(Gate(gx, gy, is_open=True))
            self.grid[gy][gx] = TILE_OPEN_GATE

    def _find_room_doors(self):
        """Identifies the doorway tiles (first corridor tile outside the room) of all combat rooms."""
        for r in self.rooms:
            if r.room_type not in (RoomType.COMBAT, RoomType.ELITE, RoomType.SURVIVAL):
                continue

            doors = []
            for x in range(r.x, r.right):
                if self.grid[r.y - 1][x] == TILE_FLOOR and self.grid[r.y][x] == TILE_FLOOR:
                    doors.append((x, r.y - 1))
                if self.grid[r.bottom][x] == TILE_FLOOR and self.grid[r.bottom - 1][x] == TILE_FLOOR:
                    doors.append((x, r.bottom))

            for y in range(r.y, r.bottom):
                if self.grid[y][r.x - 1] == TILE_FLOOR and self.grid[y][r.x] == TILE_FLOOR:
                    doors.append((r.x - 1, y))
                if self.grid[y][r.right] == TILE_FLOOR and self.grid[y][r.right - 1] == TILE_FLOOR:
                    doors.append((r.right, y))

            r.door_tiles = doors

    def _populate_dungeon_objects(self):
        for room in self.rooms:
            room.spawn_positions.clear()

        if self.start_room:
            sx, sy = self.start_room.center
            self.grid[sy][sx] = TILE_PLAYER_SPAWN
            self.start_room.spawn_positions.append((sx, sy))

        if self.boss_room:
            bx, by = self.boss_room.center
            self.grid[by][bx] = TILE_EXIT
            self.boss_room.spawn_positions.append((bx, by))

        # Treasure rooms (strictly <= 2 chests)
        for room in self.rooms:
            if room.room_type == RoomType.TREASURE:
                tx, ty = room.center
                self.grid[ty][tx] = TILE_CHEST
                room.spawn_positions.append((tx, ty))
                if room.width > 8:
                    cx2, cy2 = room.get_random_floor_tile(self.rng)
                    if self.grid[cy2][cx2] == TILE_FLOOR and (cx2, cy2) != (tx, ty):
                        self.grid[cy2][cx2] = TILE_CHEST
                        room.spawn_positions.append((cx2, cy2))
            elif room.room_type in (RoomType.COMBAT, RoomType.ELITE, RoomType.EVENT) and self.rng.random() < 0.30:
                cx, cy = room.get_random_floor_tile(self.rng)
                # Keep the centre (elite spawn / room reward) and the tile below it (relic drop) free of chests
                reserved = ((room.center_x, room.center_y), (room.center_x, room.center_y + 1))
                if self.grid[cy][cx] == TILE_FLOOR and (cx, cy) not in reserved:
                    self.grid[cy][cx] = TILE_CHEST
                    room.spawn_positions.append((cx, cy))

        # Traps in TRAP rooms and some Combat rooms
        for room in self.rooms:
            if room.room_type == RoomType.TRAP:
                for _ in range(5):
                    tx, ty = room.get_random_floor_tile(self.rng)
                    if self.grid[ty][tx] == TILE_FLOOR:
                        self.grid[ty][tx] = TILE_TRAP
                        room.spawn_positions.append((tx, ty))
            elif room.room_type == RoomType.COMBAT and self.rng.random() < 0.30:
                tx, ty = room.get_random_floor_tile(self.rng)
                if self.grid[ty][tx] == TILE_FLOOR:
                    self.grid[ty][tx] = TILE_TRAP
                    room.spawn_positions.append((tx, ty))

    def validate_dungeon(self) -> tuple[bool, list[str]]:
        """
        Structural + reachability validation. Returns (is_valid, error_reasons):
        - Start & Boss room exist, Boss room reachable, all mandatory rooms connected.
        - Corridors connect rooms: every room reachable in the room graph.
        - No isolated room, no spawn inside a wall, boss spawn inside the Boss Room,
          no unintended room overlap, playable map (flood fill over the grid).
        """
        errors: list[str] = []

        if not self.start_room:
            errors.append("Missing Start room")
        if not self.boss_room:
            errors.append("Missing Boss room")
        if errors:
            return False, errors

        # 1. Room-graph connectivity: every room reachable from Start in the graph
        reached = self._graph_reachable_from_start()
        isolated = [r for r in self.rooms if r not in reached]
        if isolated:
            errors.append(f"Isolated rooms in graph: {[r.room_id for r in isolated]}")
        if self.boss_room not in reached:
            errors.append("Boss room not reachable in room graph")

        # 2. Grid flood fill: every room center reachable on the actual tilemap
        start_pt = self.start_room.center
        queue = [start_pt]
        visited = {start_pt}
        while queue:
            cx, cy = queue.pop(0)
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.width and 0 <= ny < self.height:
                    if (nx, ny) not in visited and self.grid[ny][nx] != TILE_WALL:
                        visited.add((nx, ny))
                        queue.append((nx, ny))

        for r in self.rooms:
            if r.center not in visited:
                errors.append(f"Room {r.room_id} center unreachable on grid")
        if self.boss_room.center not in visited:
            errors.append("Boss room center unreachable on grid")

        # 3. Spawn positions must not sit inside walls
        for r in self.rooms:
            for sx, sy in r.spawn_positions:
                if self.grid[sy][sx] == TILE_WALL:
                    errors.append(f"Spawn in wall in room {r.room_id} at {(sx, sy)}")

        # 4. Player spawn tile present & walkable (obstacles are placed later, on floor tiles only)
        sx, sy = self.start_room.center
        if self.grid[sy][sx] != TILE_PLAYER_SPAWN:
            errors.append(f"Player spawn tile missing at {(sx, sy)}")

        # 5. Boss spawns at the Boss Room center, inside the room
        if self.boss_room.room_type != RoomType.BOSS:
            errors.append("Selected boss room is not BOSS type")
        bx, by = self.boss_room.center
        if self.grid[by][bx] == TILE_WALL:
            errors.append("Boss spawn position is inside a wall")

        # 6. No unintended room overlap (zero-gap adjacency included)
        for i in range(len(self.rooms)):
            for j in range(i + 1, len(self.rooms)):
                if self.rooms[i].intersects(self.rooms[j], padding=0):
                    errors.append(f"Rooms overlap: {self.rooms[i].room_id} & {self.rooms[j].room_id}")

        # 7. Treasure chest cap
        for t_room in self.treasure_rooms:
            chest_count = sum(
                1 for ry in range(t_room.y, t_room.bottom)
                for rx in range(t_room.x, t_room.right)
                if self.grid[ry][rx] == TILE_CHEST
            )
            if chest_count > 2:
                errors.append(f"Treasure room {t_room.room_id} has {chest_count} chests (>2)")

        return not errors, errors

    def get_player_spawn_pos(self) -> tuple[int, int]:
        if self.start_room:
            return self.start_room.center
        return (2, 2)
