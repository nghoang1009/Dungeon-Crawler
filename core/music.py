import os
import pygame

TRACK_EXTENSIONS = (".ogg", ".mp3", ".wav")
BASE_VOLUME = 0.15
DUCKED_VOLUME = 0.10      # while paused / inventory / modals are open


class MusicManager:
    """
    Streams looping background music from assets/music/<name>.(ogg|mp3|wav).
    Tracks: "menu" (menus, game over, victory), "dungeon" (exploration) and "boss" (boss fight).
    Replace any file with your own music of the same name. Silent (never raises) when the mixer or a file is missing.
    """
    def __init__(self, sound_manager=None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.music_dir = os.path.join(base_dir, "assets", "music")
        self.sound_manager = sound_manager
        self.enabled = True
        self.current: str | None = None
        self._ducked = False
        self._volume = BASE_VOLUME

    # ------------------------------------------------------------------ helpers
    @property
    def available(self) -> bool:
        return pygame.mixer.get_init() is not None

    def _path_for(self, track: str) -> str | None:
        for ext in TRACK_EXTENSIONS:
            path = os.path.join(self.music_dir, track + ext)
            if os.path.exists(path):
                return path
        return None

    def _apply_volume(self):
        if not self.available:
            return
        target = 0.0 if not self.enabled else (DUCKED_VOLUME if self._ducked else BASE_VOLUME)
        if target != self._volume:
            self._volume = target
            pygame.mixer.music.set_volume(target)

    # ---------------------------------------------------------------------- API
    def play(self, track: str, fade_ms: int = 900):
        """Starts `track` in a loop (no-op if it is already playing)."""
        if track == self.current or not self.available:
            return
        path = self._path_for(track)
        if path is None:
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.0 if not self.enabled else self._volume)
            pygame.mixer.music.play(loops=-1, fade_ms=fade_ms)
            self.current = track
        except pygame.error as exc:
            print(f"[Music] Could not play {track}: {exc}")

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        self._apply_volume()
        return self.enabled

    def update(self, track: str | None, ducked: bool = False):
        """Call once per frame with the wanted track; handles switching and volume ducking."""
        self._ducked = ducked
        if track:
            self.play(track)
        self._apply_volume()
