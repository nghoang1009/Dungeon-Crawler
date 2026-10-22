import pygame
from settings import TILE_SIZE

class Entity:
    """
    Base object class for Real-Time 2D Grid-Based Action Roguelike living entities.
    Physics position (pos_x, pos_y) moves continuously via delta-time velocities with Move & Slide wall checks.
    Grid coordinates (grid_x, grid_y) are continuously tracked and synchronized for grid-based abilities,
    A* pathfinding, and tile queries.
    """
    HITBOX_OFFSET_Y = 4  # hitbox sits slightly below the sprite centre (feet)

    def __init__(self, grid_x: int, grid_y: int, width: int = 32, height: int = 32):
        self.grid_x = int(grid_x)
        self.grid_y = int(grid_y)
        self.width = width
        self.height = height

        # Real-time continuous float positions
        self.pos_x = float(grid_x * TILE_SIZE + TILE_SIZE // 2)
        self.pos_y = float(grid_y * TILE_SIZE + TILE_SIZE // 2)

        self.rect = pygame.Rect(int(self.pos_x - width // 2), int(self.pos_y - height // 2), width, height)
        self.hitbox = pygame.Rect(int(self.pos_x - 10), int(self.pos_y - 6), 20, 16)

        self.max_hp = 100
        self.current_hp = 100
        self.attack_power = 10
        self.defense = 0
        self.speed = 140.0  # pixels per second

        self.facing_dir = (0, 1)  # (dx, dy)
        self.is_alive = True
        self.is_removed = False

    def sync_rect(self):
        """Aligns bounding box and synchronizes grid coordinates (grid_x, grid_y)."""
        self.rect.centerx = int(self.pos_x)
        self.rect.centery = int(self.pos_y)
        self.hitbox.centerx = int(self.pos_x)
        self.hitbox.centery = int(self.pos_y + self.HITBOX_OFFSET_Y)

        # Synchronize Grid tile position
        self.grid_x = int(self.pos_x // TILE_SIZE)
        self.grid_y = int(self.pos_y // TILE_SIZE)

    def set_grid_pos(self, gx: int, gy: int):
        self.grid_x = int(gx)
        self.grid_y = int(gy)
        self.pos_x = float(gx * TILE_SIZE + TILE_SIZE // 2)
        self.pos_y = float(gy * TILE_SIZE + TILE_SIZE // 2)
        self.sync_rect()

    def get_hitbox(self) -> pygame.Rect:
        return self.hitbox

    def get_tile_pos(self) -> tuple[int, int]:
        return (self.grid_x, self.grid_y)

    def take_damage(self, amount: int):
        self.current_hp = max(0, self.current_hp - amount)
        if self.current_hp <= 0:
            self.is_alive = False

    def heal(self, amount: int):
        self.current_hp = min(self.max_hp, self.current_hp + amount)
