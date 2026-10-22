import pygame
import math

class SpriteGenerator:
    """
    Generates dynamic procedural pixel-art surfaces with strict alpha-channel transparency (SRCALPHA).
    Zero magenta/purple artifacts. Cached for optimal 60 FPS performance.
    """
    _cache = {}

    @classmethod
    def get_player_frames(cls, player_class: str = "Knight", size: int = 32) -> dict[str, list[pygame.Surface]]:
        key = f"player_{player_class}_{size}"
        if key in cls._cache:
            return cls._cache[key]

        frames = {"idle": [], "walk": [], "attack": [], "hurt": [], "dead": []}

        # Class-specific palettes and equipment
        if player_class == "Knight":
            main_color = (65, 115, 210)       # Royal blue armor
            trim_color = (240, 210, 80)        # Gold visor / trim
            cape_color = (190, 45, 45)         # Red cape
            cloth_color = (35, 65, 130)
        elif player_class == "Archer":
            main_color = (45, 150, 75)         # Forest ranger green
            trim_color = (180, 130, 60)        # Leather trim
            cape_color = (30, 100, 50)         # Hunter cloak
            cloth_color = (100, 75, 45)
        else: # Mage
            main_color = (125, 55, 190)        # Arcane purple robe
            trim_color = (80, 220, 240)        # Cyan arcane glow
            cape_color = (70, 30, 110)         # Hood / Mantle
            cloth_color = (45, 20, 75)

        # 1. Idle Frames (4 frames - gentle breathing)
        for i in range(4):
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            off = int(math.sin(i * math.pi / 2) * 1.5)

            # Cloak / Cape
            pygame.draw.rect(surf, cape_color, (7, 12 + off, 18, 14), border_radius=2)
            # Torso Body
            pygame.draw.rect(surf, cloth_color, (9, 10 + off, 14, 13), border_radius=3)
            pygame.draw.rect(surf, main_color, (11, 11 + off, 10, 9), border_radius=2)
            # Head / Helmet / Hood
            pygame.draw.circle(surf, main_color, (16, 8 + off), 6)
            pygame.draw.rect(surf, trim_color, (13, 7 + off, 6, 2), border_radius=1)
            # Feet / Boots
            pygame.draw.rect(surf, (25, 25, 35), (9, 24, 4, 6), border_radius=1)
            pygame.draw.rect(surf, (25, 25, 35), (19, 24, 4, 6), border_radius=1)
            frames["idle"].append(surf)

        # 2. Walk Frames (4 frames - stepping & bobbing)
        for i in range(4):
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            bob = 1 if i % 2 == 1 else 0
            leg_l = 2 if i == 1 else 0
            leg_r = 2 if i == 3 else 0

            pygame.draw.rect(surf, cape_color, (7, 11 + bob, 18, 14), border_radius=2)
            pygame.draw.rect(surf, cloth_color, (9, 9 + bob, 14, 13), border_radius=3)
            pygame.draw.rect(surf, main_color, (11, 10 + bob, 10, 9), border_radius=2)
            pygame.draw.circle(surf, main_color, (16, 7 + bob), 6)
            pygame.draw.rect(surf, trim_color, (13, 6 + bob, 6, 2), border_radius=1)

            pygame.draw.rect(surf, (25, 25, 35), (9, 23 + leg_l, 4, 6), border_radius=1)
            pygame.draw.rect(surf, (25, 25, 35), (19, 23 + leg_r, 4, 6), border_radius=1)
            frames["walk"].append(surf)

        # 3. Attack Frames (4 frames - class specific weapon swing / shoot / cast)
        for i in range(4):
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            shift_x = i * 2

            pygame.draw.rect(surf, cape_color, (6 + shift_x, 11, 18, 14), border_radius=2)
            pygame.draw.rect(surf, cloth_color, (8 + shift_x, 9, 14, 13), border_radius=3)
            pygame.draw.rect(surf, main_color, (10 + shift_x, 10, 10, 9), border_radius=2)
            pygame.draw.circle(surf, main_color, (15 + shift_x, 7), 6)
            pygame.draw.rect(surf, trim_color, (12 + shift_x, 6, 6, 2), border_radius=1)

            # Class weapon visual in hand
            if player_class == "Knight":
                # Sword swing pose
                pygame.draw.line(surf, (240, 240, 255), (20 + shift_x, 14), (28 + shift_x, 6), 3)
                pygame.draw.circle(surf, (255, 215, 0), (19 + shift_x, 15), 2)
            elif player_class == "Archer":
                # Bow pull pose
                pygame.draw.arc(surf, (150, 100, 50), (18 + shift_x, 4, 10, 18), -math.pi/2, math.pi/2, 2)
                pygame.draw.line(surf, (255, 255, 255), (19 + shift_x, 13), (25 + shift_x, 13), 1)
            else: # Mage
                # Staff cast pose
                pygame.draw.line(surf, (140, 90, 45), (20 + shift_x, 22), (24 + shift_x, 4), 2)
                pygame.draw.circle(surf, (80, 220, 255), (25 + shift_x, 4), 4)

            pygame.draw.rect(surf, (25, 25, 35), (8 + shift_x, 23, 4, 6), border_radius=1)
            pygame.draw.rect(surf, (25, 25, 35), (18 + shift_x, 23, 4, 6), border_radius=1)
            frames["attack"].append(surf)

        # 4. Hurt Frames (2 frames - Pure white flash with alpha transparency)
        for i in range(2):
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 255, 255, 240), (16, 8), 7)
            pygame.draw.rect(surf, (255, 255, 255, 240), (8, 10, 16, 14), border_radius=3)
            pygame.draw.rect(surf, (255, 255, 255, 200), (9, 24, 4, 6))
            pygame.draw.rect(surf, (255, 255, 255, 200), (19, 24, 4, 6))
            frames["hurt"].append(surf)

        # 5. Dead Frames (1 frame - fallen armor on ground)
        surf_dead = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.ellipse(surf_dead, (20, 20, 30, 160), (4, size - 10, 24, 8))
        pygame.draw.rect(surf_dead, main_color, (8, size - 12, 16, 8), border_radius=2)
        pygame.draw.circle(surf_dead, trim_color, (size // 2, size - 10), 3)
        frames["dead"].append(surf_dead)

        cls._cache[key] = frames
        return frames

    @classmethod
    def get_enemy_frames(cls, enemy_type: str, size: int = 32) -> dict[str, list[pygame.Surface]]:
        key = f"enemy_{enemy_type}_{size}"
        if key in cls._cache:
            return cls._cache[key]

        frames = {"idle": [], "walk": [], "attack": [], "hurt": [], "dead": []}

        configs = {
            "goblin": {"main": (45, 160, 55), "dark": (20, 90, 30), "eye": (255, 50, 20), "size": 28},
            "skeleton": {"main": (225, 225, 215), "dark": (140, 140, 135), "eye": (60, 220, 255), "size": 32},
            "orc": {"main": (185, 65, 40), "dark": (105, 30, 15), "eye": (255, 225, 0), "size": 36},
            "archer_enemy": {"main": (160, 120, 50), "dark": (80, 55, 25), "eye": (255, 80, 80), "size": 30},
            "mage_enemy": {"main": (100, 40, 160), "dark": (50, 20, 80), "eye": (255, 240, 60), "size": 30}
        }
        cfg = configs.get(enemy_type, configs["goblin"])

        # 1. Idle Frames
        for i in range(4):
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            off = int(math.sin(i * math.pi / 2) * 1.5)

            # Head
            pygame.draw.circle(surf, cfg["main"], (size // 2, 10 + off), 7)
            # Glowing eyes
            pygame.draw.circle(surf, cfg["eye"], (size // 2 - 3, 9 + off), 2)
            pygame.draw.circle(surf, cfg["eye"], (size // 2 + 3, 9 + off), 2)
            # Torso
            pygame.draw.rect(surf, cfg["dark"], (size // 2 - 6, 17 + off, 12, 10), border_radius=2)
            # Legs
            pygame.draw.rect(surf, (25, 25, 30), (size // 2 - 6, 26, 4, 5))
            pygame.draw.rect(surf, (25, 25, 30), (size // 2 + 2, 26, 4, 5))
            frames["idle"].append(surf)

        # 2. Walk Frames
        for i in range(4):
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            bob = 1 if i % 2 == 1 else 0
            leg_l = 2 if i == 1 else 0
            leg_r = 2 if i == 3 else 0

            pygame.draw.circle(surf, cfg["main"], (size // 2, 10 + bob), 7)
            pygame.draw.circle(surf, cfg["eye"], (size // 2 - 3, 9 + bob), 2)
            pygame.draw.circle(surf, cfg["eye"], (size // 2 + 3, 9 + bob), 2)
            pygame.draw.rect(surf, cfg["dark"], (size // 2 - 6, 17 + bob, 12, 10), border_radius=2)
            pygame.draw.rect(surf, (25, 25, 30), (size // 2 - 6, 25 + leg_l, 4, 5))
            pygame.draw.rect(surf, (25, 25, 30), (size // 2 + 2, 25 + leg_r, 4, 5))
            frames["walk"].append(surf)

        # 3. Attack Frames
        for i in range(4):
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            shift_x = i * 2
            pygame.draw.circle(surf, cfg["main"], (size // 2 + shift_x, 10), 7)
            pygame.draw.circle(surf, cfg["eye"], (size // 2 + 3 + shift_x, 9), 2)
            pygame.draw.rect(surf, cfg["dark"], (size // 2 - 6 + shift_x, 17, 12, 10), border_radius=2)

            if enemy_type == "archer_enemy":
                # Bow aim
                pygame.draw.arc(surf, (150, 110, 60), (size // 2 + 6 + shift_x, 8, 8, 16), -math.pi/2, math.pi/2, 2)
            elif enemy_type == "mage_enemy":
                # Arcane ball
                pygame.draw.circle(surf, (240, 80, 255), (size // 2 + 12 + shift_x, 14), 4)
            else:
                # Melee claw/club
                pygame.draw.line(surf, (220, 200, 160), (size // 2 + 4 + shift_x, 20), (size // 2 + 14 + shift_x, 10), 3)

            pygame.draw.rect(surf, (25, 25, 30), (size // 2 - 6 + shift_x, 26, 4, 5))
            pygame.draw.rect(surf, (25, 25, 30), (size // 2 + 2 + shift_x, 26, 4, 5))
            frames["attack"].append(surf)

        # 4. Hurt Frames (White flash, no purple)
        for i in range(2):
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(surf, (255, 255, 255, 240), (size // 2, 10), 7)
            pygame.draw.rect(surf, (255, 255, 255, 240), (size // 2 - 6, 17, 12, 10), border_radius=2)
            frames["hurt"].append(surf)

        # 5. Dead Frames
        surf_dead = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.ellipse(surf_dead, (20, 20, 30, 160), (size // 2 - 10, size - 10, 20, 8))
        pygame.draw.circle(surf_dead, cfg["main"], (size // 2, size - 7), 5)
        frames["dead"].append(surf_dead)

        cls._cache[key] = frames
        return frames

    @classmethod
    def get_boss_frames(cls, size: int = 56) -> dict[str, list[pygame.Surface]]:
        key = f"boss_{size}"
        if key in cls._cache:
            return cls._cache[key]

        frames = {"idle": [], "walk": [], "attack": [], "telegraph": [], "skill": [], "hurt": [], "dead": []}

        # 1. Idle Frames
        for i in range(4):
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            off = int(math.sin(i * math.pi / 2) * 2.5)

            # Horns
            pygame.draw.polygon(surf, (240, 60, 40), [(12, 14 + off), (4, 2 + off), (18, 8 + off)])
            pygame.draw.polygon(surf, (240, 60, 40), [(44, 14 + off), (52, 2 + off), (38, 8 + off)])
            # Giant Body
            pygame.draw.rect(surf, (50, 20, 65), (14, 20 + off, 28, 26), border_radius=6)
            pygame.draw.rect(surf, (220, 50, 40), (22, 26 + off, 12, 14), border_radius=3)
            # Head
            pygame.draw.circle(surf, (80, 30, 95), (28, 16 + off), 12)
            pygame.draw.circle(surf, (255, 230, 50), (23, 14 + off), 3)
            pygame.draw.circle(surf, (255, 230, 50), (33, 14 + off), 3)
            # Claws
            pygame.draw.rect(surf, (40, 15, 55), (8, 24 + off, 6, 16), border_radius=2)
            pygame.draw.rect(surf, (40, 15, 55), (42, 24 + off, 6, 16), border_radius=2)
            # Feet
            pygame.draw.rect(surf, (25, 10, 35), (16, 46, 8, 8), border_radius=2)
            pygame.draw.rect(surf, (25, 10, 35), (32, 46, 8, 8), border_radius=2)
            frames["idle"].append(surf)

        frames["walk"] = list(frames["idle"])

        # 2. Attack Frames (Heavy claw slash)
        for i in range(4):
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            shift = i * 3
            pygame.draw.polygon(surf, (240, 60, 40), [(12 + shift, 14), (4 + shift, 2), (18 + shift, 8)])
            pygame.draw.polygon(surf, (240, 60, 40), [(44 + shift, 14), (52 + shift, 2), (38 + shift, 8)])
            pygame.draw.rect(surf, (50, 20, 65), (14 + shift, 20, 28, 26), border_radius=6)
            pygame.draw.circle(surf, (80, 30, 95), (28 + shift, 16), 12)
            # Giant slashing claw
            pygame.draw.line(surf, (255, 180, 50), (40 + shift, 14), (52 + shift, 36), 5)
            frames["attack"].append(surf)

        # 3. Telegraph / Warning Frame (Glows intense red warning aura)
        surf_tele = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(surf_tele, (255, 40, 40, 120), (28, 28), 26)
        pygame.draw.circle(surf_tele, (255, 220, 0), (28, 20), 14)
        pygame.draw.rect(surf_tele, (220, 30, 30), (14, 22, 28, 26), border_radius=6)
        frames["telegraph"].append(surf_tele)

        # 4. Hurt Frame (Pure white flash)
        surf_hurt = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.circle(surf_hurt, (255, 255, 255, 240), (28, 24), 22)
        pygame.draw.rect(surf_hurt, (255, 255, 255, 240), (14, 20, 28, 26), border_radius=6)
        frames["hurt"].append(surf_hurt)

        # 5. Dead Frame
        surf_dead = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.ellipse(surf_dead, (20, 10, 25, 180), (6, size - 14, 44, 12))
        pygame.draw.circle(surf_dead, (70, 20, 80), (size // 2, size - 12), 10)
        frames["dead"].append(surf_dead)

        cls._cache[key] = frames
        return frames

    @classmethod
    def get_obstacle_surface(cls, obstacle_type: str = "barrel", size: int = 32) -> pygame.Surface:
        key = f"obs_{obstacle_type}_{size}"
        if key in cls._cache:
            return cls._cache[key]

        surf = pygame.Surface((size, size), pygame.SRCALPHA)

        if obstacle_type == "barrel":
            # Wooden barrel with metal hoops
            pygame.draw.ellipse(surf, (145, 95, 45), (4, 4, size - 8, size - 8))
            pygame.draw.rect(surf, (130, 80, 35), (6, 8, size - 12, size - 16))
            # Iron bands
            pygame.draw.line(surf, (180, 180, 190), (6, 10), (size - 7, 10), 2)
            pygame.draw.line(surf, (180, 180, 190), (6, size - 11), (size - 7, size - 11), 2)
            # Wood planks
            pygame.draw.line(surf, (90, 55, 25), (size // 2, 6), (size // 2, size - 7), 1)

        elif obstacle_type == "pillar":
            # Solid stone pillar
            pygame.draw.rect(surf, (75, 70, 85), (4, 2, size - 8, size - 4), border_radius=3)
            pygame.draw.rect(surf, (105, 100, 120), (2, 2, size - 4, 6), border_radius=2)
            pygame.draw.rect(surf, (55, 50, 65), (2, size - 8, size - 4, 6), border_radius=2)
            # Stone cracks
            pygame.draw.line(surf, (40, 35, 48), (12, 10), (18, 18), 1)
            pygame.draw.line(surf, (40, 35, 48), (18, 18), (14, 24), 1)

        cls._cache[key] = surf
        return surf

    @classmethod
    def get_projectile_surface(cls, proj_type: str = "arrow", size: int = 16) -> pygame.Surface:
        key = f"proj_{proj_type}_{size}"
        if key in cls._cache:
            return cls._cache[key]

        surf = pygame.Surface((size, size), pygame.SRCALPHA)

        if proj_type == "arrow":
            # Wooden arrow with iron tip and feather
            pygame.draw.line(surf, (160, 110, 60), (2, 8), (12, 8), 2)
            pygame.draw.polygon(surf, (220, 220, 230), [(12, 5), (16, 8), (12, 11)])
            pygame.draw.line(surf, (240, 240, 250), (1, 6), (3, 8), 1)
            pygame.draw.line(surf, (240, 240, 250), (1, 10), (3, 8), 1)
        elif proj_type == "magic_bolt":
            # Glowing cyan/purple magic orb
            pygame.draw.circle(surf, (120, 240, 255, 140), (8, 8), 7)
            pygame.draw.circle(surf, (200, 255, 255), (8, 8), 4)
            pygame.draw.circle(surf, (255, 255, 255), (8, 8), 2)
        elif proj_type == "enemy_magic":
            # Dark purple/red cursed magic bolt
            pygame.draw.circle(surf, (220, 50, 200, 140), (8, 8), 7)
            pygame.draw.circle(surf, (255, 100, 80), (8, 8), 4)

        cls._cache[key] = surf
        return surf

    @classmethod
    def get_tile_surface(cls, tile_id: int, size: int = 32) -> pygame.Surface:
        key = f"tile_{tile_id}_{size}"
        if key in cls._cache:
            return cls._cache[key]

        surf = pygame.Surface((size, size))
        if tile_id == 0:  # WALL
            surf.fill((25, 22, 35))
            pygame.draw.rect(surf, (55, 50, 75), (0, 0, size, 8))
            pygame.draw.line(surf, (15, 12, 22), (0, size-1), (size, size-1), 2)
            pygame.draw.line(surf, (35, 32, 48), (0, 8), (size, 8), 1)
            pygame.draw.line(surf, (15, 12, 22), (size//2, 8), (size//2, 18), 1)
            pygame.draw.line(surf, (15, 12, 22), (size//4, 18), (size//4, size), 1)
            pygame.draw.line(surf, (15, 12, 22), (3*size//4, 18), (3*size//4, size), 1)
        elif tile_id == 1:  # FLOOR
            surf.fill((45, 42, 56))
            pygame.draw.rect(surf, (52, 48, 65), (1, 1, size-2, size-2), 1)
            surf.set_at((6, 8), (62, 58, 78))
            surf.set_at((22, 19), (62, 58, 78))
            surf.set_at((14, 25), (38, 35, 48))
        elif tile_id == 4:  # DOOR
            surf.fill((45, 42, 56))
            pygame.draw.rect(surf, (140, 85, 40), (4, 4, size-8, size-8), border_radius=3)
            pygame.draw.circle(surf, (240, 200, 60), (size-8, size//2), 2)
        elif tile_id == 5:  # EXIT
            surf.fill((45, 42, 56))
            pygame.draw.circle(surf, (40, 180, 140), (size//2, size//2), size//2 - 3, 3)
            for r in range(2, size//2 - 4, 3):
                pygame.draw.circle(surf, (80, 230, 190), (size//2, size//2), r, 1)
        elif tile_id == 7:  # TRAP
            surf.fill((45, 42, 56))
            for pt in [(8, 8), (24, 8), (16, 16), (8, 24), (24, 24)]:
                pygame.draw.polygon(surf, (200, 60, 60), [(pt[0]-3, pt[1]+3), (pt[0]+3, pt[1]+3), (pt[0], pt[1]-4)])
        else:
            surf.fill((50, 50, 60))

        cls._cache[key] = surf
        return surf


class Animator:
    """
    Handles playback, state transitions, and frame updates with delta-time.
    """
    def __init__(self, animations: dict[str, list[pygame.Surface]], default_state: str = "idle", fps: float = 8.0):
        self.animations = animations
        self.current_state = default_state
        self.fps = fps
        self.state_fps = {"walk": fps * 1.4}   # footsteps read better a bit faster than the idle breathing
        self.frame_index = 0.0
        self.is_finished = False

    def change_state(self, new_state: str, reset: bool = False):
        if new_state != self.current_state or reset:
            self.current_state = new_state
            self.frame_index = 0.0
            self.is_finished = False

    def update(self, dt: float):
        if self.current_state not in self.animations or not self.animations[self.current_state]:
            return

        frames = self.animations[self.current_state]
        self.frame_index += self.state_fps.get(self.current_state, self.fps) * dt

        if self.frame_index >= len(frames):
            self.frame_index = 0.0
            self.is_finished = True

    def get_current_frame(self, flip_x: bool = False) -> pygame.Surface:
        frames = self.animations.get(self.current_state, [])
        if not frames:
            fallback = pygame.Surface((32, 32), pygame.SRCALPHA)
            return fallback

        idx = int(self.frame_index) % len(frames)
        frame = frames[idx]

        if flip_x:
            return pygame.transform.flip(frame, True, False)
        return frame
