import heapq
import math
from settings import ASTAR_MAX_ITERATIONS

class Node:
    """Represents a graph search node in A* pathfinding."""
    def __init__(self, x: int, y: int, g_cost: float, h_cost: float, parent: "Node | None" = None):
        self.x = x
        self.y = y
        self.g_cost = g_cost
        self.h_cost = h_cost
        self.f_cost = g_cost + h_cost
        self.parent = parent

    def __lt__(self, other: "Node") -> bool:
        if self.f_cost == other.f_cost:
            return self.h_cost < other.h_cost
        return self.f_cost < other.f_cost

    @property
    def pos(self) -> tuple[int, int]:
        return (self.x, self.y)

class AStarPathfinder:
    """
    A* Pathfinding Algorithm on 2D Grid with support for dynamic obstacles (Barrels, Pillars, Locked Gates)
    and Manhattan distance heuristic.
    """

    @staticmethod
    def manhattan_distance(x1: int, y1: int, x2: int, y2: int) -> float:
        return abs(x1 - x2) + abs(y1 - y2)

    @staticmethod
    def euclidean_distance(x1: int, y1: int, x2: int, y2: int) -> float:
        return math.hypot(x1 - x2, y1 - y2)

    @classmethod
    def find_path(cls,
                  start: tuple[int, int],
                  goal: tuple[int, int],
                  tilemap,
                  obstacles=None,
                  closed_gates=None,
                  allow_diagonals: bool = False,
                  max_iterations: int = ASTAR_MAX_ITERATIONS) -> list[tuple[int, int]]:
        """
        Calculates optimal shortest tile path from `start` to `goal` on grid.
        Considers walls, destructible/indestructible obstacles, and locked gates as impassable.
        """
        start_x, start_y = int(start[0]), int(start[1])
        goal_x, goal_y = int(goal[0]), int(goal[1])

        if (start_x, start_y) == (goal_x, goal_y):
            return []

        # If goal is blocked, seek closest adjacent walkable tile
        if not tilemap.is_walkable(goal_x, goal_y, obstacles, closed_gates):
            adjacent_found = None
            min_dist = float('inf')
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = goal_x + dx, goal_y + dy
                if tilemap.is_walkable(nx, ny, obstacles, closed_gates):
                    d = cls.manhattan_distance(start_x, start_y, nx, ny)
                    if d < min_dist:
                        min_dist = d
                        adjacent_found = (nx, ny)
            if adjacent_found:
                goal_x, goal_y = adjacent_found
            else:
                return []

        open_list: list[Node] = []
        open_dict: dict[tuple[int, int], Node] = {}
        closed_set: set[tuple[int, int]] = set()

        start_h = cls.manhattan_distance(start_x, start_y, goal_x, goal_y)
        start_node = Node(start_x, start_y, g_cost=0.0, h_cost=start_h)
        heapq.heappush(open_list, start_node)
        open_dict[(start_x, start_y)] = start_node

        iterations = 0

        if allow_diagonals:
            directions = [
                (0, -1, 1.0), (0, 1, 1.0), (-1, 0, 1.0), (1, 0, 1.0),
                (-1, -1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (1, 1, 1.414)
            ]
        else:
            directions = [(0, -1, 1.0), (0, 1, 1.0), (-1, 0, 1.0), (1, 0, 1.0)]

        while open_list and iterations < max_iterations:
            iterations += 1
            current_node = heapq.heappop(open_list)
            curr_pos = current_node.pos

            if curr_pos in open_dict:
                del open_dict[curr_pos]

            closed_set.add(curr_pos)

            # Reached Goal Check
            if curr_pos == (goal_x, goal_y):
                path = []
                curr = current_node
                while curr.parent is not None:
                    path.append((curr.x, curr.y))
                    curr = curr.parent
                path.reverse()
                return path

            # Explore neighbors
            for move in directions:
                dx, dy, cost_step = move
                nx, ny = current_node.x + dx, current_node.y + dy
                neighbor_pos = (nx, ny)

                if neighbor_pos in closed_set:
                    continue

                if not tilemap.is_walkable(nx, ny, obstacles, closed_gates):
                    continue

                if dx != 0 and dy != 0:
                    if not tilemap.is_walkable(current_node.x + dx, current_node.y, obstacles, closed_gates) or \
                       not tilemap.is_walkable(current_node.x, current_node.y + dy, obstacles, closed_gates):
                        continue

                tentative_g = current_node.g_cost + cost_step

                if neighbor_pos in open_dict:
                    existing_node = open_dict[neighbor_pos]
                    if tentative_g < existing_node.g_cost:
                        existing_node.g_cost = tentative_g
                        existing_node.f_cost = tentative_g + existing_node.h_cost
                        existing_node.parent = current_node
                        heapq.heapify(open_list)
                else:
                    h_cost = cls.manhattan_distance(nx, ny, goal_x, goal_y)
                    neighbor_node = Node(nx, ny, g_cost=tentative_g, h_cost=h_cost, parent=current_node)
                    heapq.heappush(open_list, neighbor_node)
                    open_dict[neighbor_pos] = neighbor_node

        return []
