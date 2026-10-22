"""Combat visual effects shared by bosses, telegraphs and projectiles."""
import math
import pygame

# element -> (colour, impact sound)
ELEMENTS = {
    "fire": ((255, 120, 40), "boss_fire"),
    "ice": ((120, 215, 255), "boss_ice"),
    "poison": ((110, 225, 90), "boss_poison"),
    "void": ((190, 90, 255), "boss_void"),
    "earth": ((205, 170, 110), "boss_slam"),
    "dark": ((170, 175, 210), "boss_slam"),
}
STATUS_ELEMENT = {"burn": "fire", "slow": "ice", "poison": "poison"}
DEFAULT_COLOR = (240, 60, 55)


def element_for(status: str | None, default: str | None = None) -> str | None:
    """A zone's element: its status effect wins (burn -> fire...), otherwise the caster's element."""
    return STATUS_ELEMENT.get(status) or default


def color_of(element: str | None) -> tuple[int, int, int]:
    return ELEMENTS.get(element, (DEFAULT_COLOR, "boss_slam"))[0]


def sound_of(element: str | None) -> str:
    return ELEMENTS.get(element, (DEFAULT_COLOR, "boss_slam"))[1]


class ShockwaveFX:
    """Expanding ring + soft flash used for impacts, landings, teleports and phase changes."""
    def __init__(self, x: float, y: float, radius: float, color=DEFAULT_COLOR, duration: float = 0.45,
                 filled: bool = True):
        self.x = x
        self.y = y
        self.radius = max(8.0, radius)
        self.color = color[:3]
        self.duration = duration
        self.filled = filled
        self.age = 0.0

    def update(self, dt: float):
        self.age += dt

    @property
    def is_alive(self) -> bool:
        return self.age < self.duration

    def render(self, surface: pygame.Surface, camera):
        t = min(1.0, self.age / self.duration)
        r = int(self.radius * (0.25 + 0.75 * (1.0 - (1.0 - t) ** 2)))   # ease-out expansion
        if r < 2:
            return
        alpha = int(230 * (1.0 - t))
        sx, sy = camera.apply_pos(self.x, self.y)
        fx = pygame.Surface((r * 2 + 6, r * 2 + 6), pygame.SRCALPHA)
        c = (r + 3, r + 3)
        if self.filled:
            pygame.draw.circle(fx, (*self.color, int(alpha * 0.28)), c, r)
        pygame.draw.circle(fx, (*self.color, alpha), c, r, max(2, int(6 * (1.0 - t)) + 1))
        pygame.draw.circle(fx, (255, 255, 255, int(alpha * 0.6)), c, max(1, int(r * 0.78)), 1)
        surface.blit(fx, (sx - c[0], sy - c[1]))


class GhostImage:
    """Fading copy of a sprite (charge afterimage)."""
    LIFETIME = 0.28

    def __init__(self, x: float, y: float, frame: pygame.Surface, tint=(255, 120, 90)):
        self.x = x
        self.y = y
        self.frame = frame.copy()
        self.frame.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self.age = 0.0

    def update(self, dt: float):
        self.age += dt

    @property
    def is_alive(self) -> bool:
        return self.age < self.LIFETIME

    def render(self, surface: pygame.Surface, camera):
        sx, sy = camera.apply_pos(self.x, self.y)
        img = self.frame
        img.set_alpha(int(150 * (1.0 - self.age / self.LIFETIME)))
        surface.blit(img, img.get_rect(center=(sx, sy)))


def pulse(speed: float = 6.0) -> float:
    """0..1 smooth pulse driven by the wall clock (used for auras and warning flashes)."""
    return 0.5 + 0.5 * math.sin(pygame.time.get_ticks() / 1000.0 * speed)
