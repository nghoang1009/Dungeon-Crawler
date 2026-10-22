import pygame
from settings import TILE_SIZE

class Door:
    """
    Door or gate between corridors and rooms. Can be locked or unlocked.
    """
    def __init__(self, tx: int, ty: int, is_locked: bool = False):
        self.tx = tx
        self.ty = ty
        self.is_locked = is_locked
        self.is_open = False
        self.rect = pygame.Rect(tx * TILE_SIZE, ty * TILE_SIZE, TILE_SIZE, TILE_SIZE)

    def interact(self, player) -> bool:
        if self.is_locked:
            return False  # Requires key
        self.is_open = not self.is_open
        return True


class Trap:
    """
    Hidden/Visible floor spike trap that triggers when stepped on.
    """
    def __init__(self, tx: int, ty: int, damage: int = 15):
        self.tx = tx
        self.ty = ty
        self.damage = damage
        self.cooldown = 0.0
        self.rect = pygame.Rect(tx * TILE_SIZE + 4, ty * TILE_SIZE + 4, TILE_SIZE - 8, TILE_SIZE - 8)

    def update(self, dt: float, player, combat_system=None):
        if self.cooldown > 0:
            self.cooldown -= dt

        # Check trigger
        if self.cooldown <= 0 and self.rect.colliderect(player.get_hitbox()) and not player.is_invulnerable:
            player.take_damage(self.damage)
            player.start_hit_invulnerability()
            self.cooldown = 2.0  # re-arm delay
            if combat_system:
                from combat.damage import DamageNumber
                from settings import COLOR_HP_RED
                combat_system.damage_numbers.append(
                    DamageNumber(self.rect.centerx, self.rect.top, f"TRAP! -{self.damage}", COLOR_HP_RED)
                )
