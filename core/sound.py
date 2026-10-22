import pygame
import math
import random
import struct
import time

# Minimum seconds between two plays of the same effect (stops 16-shot volleys from becoming a wall of noise)
MIN_INTERVAL = {"boss_shoot": 0.07, "boss_warn": 0.18, "boss_cast": 0.25, "boss_fire": 0.12, "boss_ice": 0.12,
                "boss_poison": 0.12, "boss_void": 0.12, "boss_slam": 0.10, "boss_beam": 0.10}
DEFAULT_MIN_INTERVAL = 0.03

class SoundManager:
    """
    Manages procedural sound effects synthesized in real-time or loaded from audio files.
    Allows zero external dependency runtime with full SFX support.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SoundManager, cls).__new__(cls)
            cls._instance.initialized = False
            cls._instance.sounds = {}
            cls._instance.muted = False
            cls._instance._last_played = {}
        return cls._instance

    def initialize(self):
        if self.initialized:
            return
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self._generate_sfx()
            self.initialized = True
        except Exception as e:
            print(f"[SoundManager] Audio initialization error: {e}")
            self.muted = True

    def _generate_sfx(self):
        """Synthesize retro 8-bit / 16-bit sound effects procedurally."""
        try:
            # 1. Attack / Slash SFX (White noise burst + low pass)
            self.sounds["attack"] = self._create_noise_sound(duration=0.12, decay=15.0)
            # 2. Hit / Hurt SFX (Low pitch bend down)
            self.sounds["hit"] = self._create_tone_sound(freq_start=280, freq_end=80, duration=0.15)
            # 3. Enemy Death SFX (Explosion rumble)
            self.sounds["death"] = self._create_tone_sound(freq_start=160, freq_end=40, duration=0.3)
            # 4. Chest Open SFX (Fanfare chirp upward)
            self.sounds["chest"] = self._create_tone_sound(freq_start=350, freq_end=700, duration=0.22)
            # 5. Potion drink SFX (Two tone bubble)
            self.sounds["potion"] = self._create_tone_sound(freq_start=400, freq_end=600, duration=0.18)
            # 6. Level Up SFX
            self.sounds["levelup"] = self._create_tone_sound(freq_start=300, freq_end=900, duration=0.45)
            # 7. Boss roar
            self.sounds["boss_roar"] = self._create_tone_sound(freq_start=120, freq_end=50, duration=0.6)
            self._generate_boss_sfx()
        except Exception as e:
            print(f"[SoundManager] Failed to synthesize sounds: {e}")

    def _synth(self, duration: float, gen, gain: float = 0.5) -> pygame.mixer.Sound:
        """Builds a stereo Sound from gen(t, progress) -> sample in [-1, 1]."""
        sample_rate = 22050
        n = int(sample_rate * duration)
        raw = bytearray()
        for i in range(n):
            t = i / sample_rate
            val = max(-1.0, min(1.0, gen(t, i / n)))
            packed = struct.pack("<h", int(val * 32767 * gain))
            raw.extend(packed)
            raw.extend(packed)
        return pygame.mixer.Sound(buffer=bytes(raw))

    def _generate_boss_sfx(self):
        """Boss move sounds: one per element plus cast / warning / charge / shot / summon / stun cues."""
        tau = 2.0 * math.pi
        rnd = random.random

        def sweep(f0, f1, p):
            return f0 + (f1 - f0) * p

        # Cast: soft rising two-tone warble (the boss starts a move)
        self.sounds["boss_cast"] = self._synth(0.35, lambda t, p: (
            math.sin(tau * sweep(300, 520, p) * t + 2.0 * math.sin(tau * 9 * t)) * 0.6
            + math.sin(tau * sweep(450, 780, p) * t) * 0.25) * math.sin(math.pi * p) , 0.5)
        # Warning ping when a danger zone appears
        self.sounds["boss_warn"] = self._synth(0.14, lambda t, p: math.sin(tau * 880 * t) * math.exp(-p * 5), 0.4)
        # Charge: rising whoosh
        self.sounds["boss_charge"] = self._synth(0.45, lambda t, p: (
            (rnd() * 2 - 1) * 0.5 * p + math.sin(tau * sweep(110, 640, p) * t) * 0.5) * (0.3 + 0.7 * p) * (1 - p * 0.3), 0.5)
        # Slam / earth impact: low thump + debris
        self.sounds["boss_slam"] = self._synth(0.45, lambda t, p: (
            math.sin(tau * sweep(95, 32, p) * t) * math.exp(-p * 4)
            + (rnd() * 2 - 1) * 0.5 * math.exp(-p * 14)), 0.7)
        # Fire: crackling roar
        self.sounds["boss_fire"] = self._synth(0.55, lambda t, p: (
            (rnd() * 2 - 1) * (0.45 + 0.4 * math.sin(tau * 28 * t) ** 2) * math.exp(-p * 3.2)
            + (((t * 120) % 1.0) * 2 - 1) * 0.28 * math.exp(-p * 4)), 0.55)
        # Ice: bright glassy shimmer
        self.sounds["boss_ice"] = self._synth(0.55, lambda t, p: (
            math.sin(tau * 1240 * t) * 0.35 + math.sin(tau * 1865 * t) * 0.3
            + math.sin(tau * 2490 * t) * 0.18 * math.sin(tau * 17 * t)) * math.exp(-p * 5), 0.45)
        # Poison: bubbling
        self.sounds["boss_poison"] = self._synth(0.55, lambda t, p: (
            math.sin(tau * (240 + 520 * ((t * 15) % 1.0)) * t) * (1 - ((t * 15) % 1.0)) * 0.9) * math.exp(-p * 2.5), 0.5)
        # Void: wobbling low sweep
        self.sounds["boss_void"] = self._synth(0.65, lambda t, p: (
            math.sin(tau * sweep(240, 85, p) * t + 3.0 * math.sin(tau * 6 * t)) * 0.8
            + (rnd() * 2 - 1) * 0.12) * math.sin(math.pi * min(1.0, p * 1.4)) * (1 - p * 0.5), 0.55)
        # Beam / lightning zap
        self.sounds["boss_beam"] = self._synth(0.28, lambda t, p: (
            (((t * sweep(1500, 220, p)) % 1.0) * 2 - 1) * 0.6 + (rnd() * 2 - 1) * 0.2) * math.exp(-p * 4), 0.45)
        # Projectile launch
        self.sounds["boss_shoot"] = self._synth(0.13, lambda t, p: math.sin(tau * sweep(760, 300, p) * t) * math.exp(-p * 4), 0.4)
        # Summon: swelling low chord
        self.sounds["boss_summon"] = self._synth(0.7, lambda t, p: (
            math.sin(tau * 110 * t) + math.sin(tau * 165 * t) * 0.8 + math.sin(tau * 220 * t) * 0.6)
            * 0.35 * math.sin(math.pi * p) ** 0.7, 0.55)
        # Stun / clang: metallic ring
        self.sounds["boss_stun"] = self._synth(0.4, lambda t, p: (
            math.sin(tau * 440 * t) * 0.5 + math.sin(tau * 587 * t) * 0.4 + math.sin(tau * 1180 * t) * 0.25
            + (rnd() * 2 - 1) * 0.25 * math.exp(-p * 30)) * math.exp(-p * 6), 0.5)

    def _create_tone_sound(self, freq_start: float, freq_end: float, duration: float) -> pygame.mixer.Sound:
        sample_rate = 22050
        num_samples = int(sample_rate * duration)
        raw_data = bytearray()

        for i in range(num_samples):
            t = i / sample_rate
            progress = i / num_samples
            freq = freq_start + (freq_end - freq_start) * progress
            # Sine wave with exponential decay
            val = math.sin(2.0 * math.pi * freq * t) * math.exp(-progress * 4.0)
            sample = int(val * 32767 * 0.4)
            sample = max(-32768, min(32767, sample))
            packed = struct.pack("<h", sample)
            raw_data.extend(packed)  # Left
            raw_data.extend(packed)  # Right

        return pygame.mixer.Sound(buffer=bytes(raw_data))

    def _create_noise_sound(self, duration: float, decay: float) -> pygame.mixer.Sound:
        sample_rate = 22050
        num_samples = int(sample_rate * duration)
        raw_data = bytearray()
        import random

        for i in range(num_samples):
            progress = i / num_samples
            val = (random.random() * 2.0 - 1.0) * math.exp(-progress * decay)
            sample = int(val * 32767 * 0.35)
            sample = max(-32768, min(32767, sample))
            packed = struct.pack("<h", sample)
            raw_data.extend(packed)
            raw_data.extend(packed)

        return pygame.mixer.Sound(buffer=bytes(raw_data))

    def play(self, sound_name: str, volume: float = 0.6):
        if self.muted or not self.initialized:
            return
        snd = self.sounds.get(sound_name)
        if snd:
            now = time.perf_counter()
            last = self._last_played.get(sound_name, -1.0)
            if now - last < MIN_INTERVAL.get(sound_name, DEFAULT_MIN_INTERVAL):
                return
            self._last_played[sound_name] = now
            snd.set_volume(volume)
            snd.play()
