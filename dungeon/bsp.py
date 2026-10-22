import random
from dungeon.room import Room

class BSPNode:
    """
    Binary Space Partitioning Tree Node for procedural dungeon generation.
    Splits rectangular dungeon space recursively into left and right sub-regions.
    """
    def __init__(self, x: int, y: int, width: int, height: int):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

        self.left_child: "BSPNode | None" = None
        self.right_child: "BSPNode | None" = None
        self.room: Room | None = None
        self.corridor: list[tuple[int, int]] = []

    @property
    def is_leaf(self) -> bool:
        return self.left_child is None and self.right_child is None

    def split(self, min_size: int, rng: random.Random) -> bool:
        """
        Splits this node into two children nodes horizontally or vertically.
        Returns True if successfully split, False if node is too small.
        """
        if not self.is_leaf:
            return False

        # Determine split orientation based on aspect ratio or random choice
        split_horizontal = rng.choice([True, False])
        if self.width / self.height >= 1.3:
            split_horizontal = False # Force vertical split
        elif self.height / self.width >= 1.3:
            split_horizontal = True  # Force horizontal split

        max_split = (self.height if split_horizontal else self.width) - min_size
        if max_split <= min_size:
            return False # Node too small to split into valid child nodes

        split_pos = rng.randint(min_size, max_split)

        if split_horizontal:
            self.left_child = BSPNode(self.x, self.y, self.width, split_pos)
            self.right_child = BSPNode(self.x, self.y + split_pos, self.width, self.height - split_pos)
        else:
            self.left_child = BSPNode(self.x, self.y, split_pos, self.height)
            self.right_child = BSPNode(self.x + split_pos, self.y, self.width - split_pos, self.height)

        return True

    def create_rooms(self, min_w: int, min_h: int, max_w: int, max_h: int, rng: random.Random) -> list[Room]:
        """
        Recursively traverse BSP tree and instantiate concrete Room objects within leaf nodes.
        """
        rooms = []
        if self.is_leaf:
            # Determine room size within this leaf partition
            max_w_fit = min(max_w, self.width - 2)
            max_h_fit = min(max_h, self.height - 2)
            min_w_fit = min(min_w, max_w_fit)
            min_h_fit = min(min_h, max_h_fit)

            r_w = rng.randint(min_w_fit, max_w_fit)
            r_h = rng.randint(min_h_fit, max_h_fit)

            # Center/offset room within leaf node
            max_off_x = self.width - r_w - 1
            max_off_y = self.height - r_h - 1
            off_x = rng.randint(1, max(1, max_off_x))
            off_y = rng.randint(1, max(1, max_off_y))

            self.room = Room(self.x + off_x, self.y + off_y, r_w, r_h)
            rooms.append(self.room)
        else:
            if self.left_child:
                rooms.extend(self.left_child.create_rooms(min_w, min_h, max_w, max_h, rng))
            if self.right_child:
                rooms.extend(self.right_child.create_rooms(min_w, min_h, max_w, max_h, rng))

        return rooms

    def get_room(self, rng: random.Random | None = None) -> Room | None:
        """
        Finds any room existing within this node or its descendants.
        Uses the provided seeded rng (never the global random state) so the same
        seed always yields the same room selection.
        """
        if self.room is not None:
            return self.room

        left_room = self.left_child.get_room(rng) if self.left_child else None
        right_room = self.right_child.get_room(rng) if self.right_child else None

        if left_room and right_room:
            if rng is not None:
                return rng.choice([left_room, right_room])
            return left_room  # deterministic fallback (no global random)
        return left_room or right_room

    # ------------------------------------------------------------ pruning
    def contains_kept(self, kept: set) -> bool:
        """True if this node or any descendant holds a kept (non-truncated) room."""
        if self.room is not None and self.room in kept:
            return True
        return ((self.left_child is not None and self.left_child.contains_kept(kept)) or
                (self.right_child is not None and self.right_child.contains_kept(kept)))

    def prune_to_rooms(self, kept: set):
        """
        Drops child subtrees holding no kept room. Called after the generator
        truncates its room list so corridors/connections never reference a
        discarded room (which would leak phantom graph nodes).
        """
        if self.left_child:
            self.left_child.prune_to_rooms(kept)
            if not self.left_child.contains_kept(kept):
                self.left_child = None
        if self.right_child:
            self.right_child.prune_to_rooms(kept)
            if not self.right_child.contains_kept(kept):
                self.right_child = None
