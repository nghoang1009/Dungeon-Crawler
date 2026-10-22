import pygame
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, MAP_WIDTH, MAP_HEIGHT, TILE_SIZE

class Camera:
    """
    2D Camera that follows target (Player) smoothly and clamps to dungeon map boundary.
    """
    def __init__(self, width: int = SCREEN_WIDTH, height: int = SCREEN_HEIGHT):
        self.width = width
        self.height = height
        self.offset_x = 0.0
        self.offset_y = 0.0

        # Max bounds in pixels
        self.max_x = MAP_WIDTH * TILE_SIZE - self.width
        self.max_y = MAP_HEIGHT * TILE_SIZE - self.height

        # Screen shake parameters
        self.shake_duration = 0.0
        self.shake_magnitude = 0.0
        self.shake_offset_x = 0.0
        self.shake_offset_y = 0.0

    def set_map_size(self, map_tiles_w: int, map_tiles_h: int):
        self.max_x = max(0, map_tiles_w * TILE_SIZE - self.width)
        self.max_y = max(0, map_tiles_h * TILE_SIZE - self.height)

    def add_shake(self, duration: float = 0.25, magnitude: float = 6.0):
        self.shake_duration = duration
        self.shake_magnitude = magnitude

    def update(self, target, dt: float = 0.016):
        # Target center position
        target_center_x = target.rect.centerx if hasattr(target, "rect") else target.x
        target_center_y = target.rect.centery if hasattr(target, "rect") else target.y

        # Desired camera offset
        desired_x = target_center_x - self.width // 2
        desired_y = target_center_y - self.height // 2

        # Smooth lerp interpolation
        lerp_factor = 0.12
        self.offset_x += (desired_x - self.offset_x) * lerp_factor
        self.offset_y += (desired_y - self.offset_y) * lerp_factor

        # Clamp within map boundaries
        self.offset_x = max(0, min(self.offset_x, self.max_x))
        self.offset_y = max(0, min(self.offset_y, self.max_y))

        # Update shake
        if self.shake_duration > 0:
            self.shake_duration -= dt
            import random
            self.shake_offset_x = random.uniform(-self.shake_magnitude, self.shake_magnitude)
            self.shake_offset_y = random.uniform(-self.shake_magnitude, self.shake_magnitude)
            if self.shake_duration <= 0:
                self.shake_offset_x = 0.0
                self.shake_offset_y = 0.0
        else:
            self.shake_offset_x = 0.0
            self.shake_offset_y = 0.0

    def apply(self, entity_or_rect):
        """Returns new Rect with camera offset applied."""
        if hasattr(entity_or_rect, "rect"):
            rect = entity_or_rect.rect
        else:
            rect = entity_or_rect

        return pygame.Rect(
            int(rect.x - self.offset_x + self.shake_offset_x),
            int(rect.y - self.offset_y + self.shake_offset_y),
            rect.width,
            rect.height
        )

    def apply_pos(self, x: float, y: float) -> tuple[int, int]:
        """Convert world coordinates (x, y) to screen coordinates."""
        return (
            int(x - self.offset_x + self.shake_offset_x),
            int(y - self.offset_y + self.shake_offset_y)
        )

    def screen_to_world(self, screen_x: int, screen_y: int) -> tuple[float, float]:
        """Convert screen pixel coords to world pixel coords."""
        return (
            screen_x + self.offset_x - self.shake_offset_x,
            screen_y + self.offset_y - self.shake_offset_y
        )

    def is_rect_visible(self, rect: pygame.Rect) -> bool:
        """Check if a world rect is inside current camera viewport (Frustum Culling)."""
        view_rect = pygame.Rect(
            int(self.offset_x),
            int(self.offset_y),
            self.width,
            self.height
        )
        return view_rect.colliderect(rect)
