"""
Synthesises the game's background music (original loops, no samples) into assets/music/*.wav.

  python tools/build_music.py

Three seamless 8-bar loops: menu (calm, A minor), dungeon (dark, D minor) and boss (driving, E phrygian).
Pure Python (wave + math + random), so it needs no extra libraries. Drop your own .wav/.ogg/.mp3 files named
menu / dungeon / boss into assets/music/ to replace them; core/music.py loads whichever it finds.
"""
import math
import os
import random
import wave
from array import array

SR = 22050
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "music")

NOTE_INDEX = {"C": 0, "C#": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}


def hz(name: str) -> float:
    """'A3' -> 220.0"""
    pitch, octave = name[:-1], int(name[-1])
    midi = 12 * (octave + 1) + NOTE_INDEX[pitch]
    return 440.0 * 2 ** ((midi - 69) / 12)


# ------------------------------------------------------------------ oscillators
def square(phase, duty=0.5):
    return 1.0 if (phase % 1.0) < duty else -1.0


def triangle(phase):
    p = phase % 1.0
    return 4 * p - 1 if p < 0.5 else 3 - 4 * p


def saw(phase):
    return 2 * (phase % 1.0) - 1


def sine(phase):
    return math.sin(2 * math.pi * phase)


WAVES = {"square": square, "pulse": lambda p: square(p, 0.25), "triangle": triangle, "saw": saw, "sine": sine}


class Track:
    def __init__(self, bpm: float, bars: int):
        self.bpm = bpm
        self.beat = 60.0 / bpm
        self.seconds = bars * 4 * self.beat
        self.n = int(self.seconds * SR)
        self.buf = [0.0] * self.n   # events past the end wrap to the start so the loop is seamless

    def note(self, freq, start_beat, length_beats, wave_name="triangle", vol=0.3, attack=0.01, release=0.18,
             vibrato=0.0):
        osc = WAVES[wave_name]
        start = int(start_beat * self.beat * SR)
        length = int(length_beats * self.beat * SR)
        tail = int(release * SR)
        att = max(1, int(attack * SR))
        phase = 0.0
        for i in range(length + tail):
            if i < att:
                env = i / att
            elif i < length:
                env = 1.0
            else:
                env = math.exp(-5.0 * (i - length) / max(1, tail))
            f = freq * (1 + vibrato * math.sin(2 * math.pi * 5.5 * i / SR)) if vibrato else freq
            phase += f / SR
            self.buf[(start + i) % self.n] += osc(phase) * env * vol

    def chord(self, freqs, start_beat, length_beats, **kw):
        for f in freqs:
            self.note(f, start_beat, length_beats, **kw)

    def kick(self, start_beat, vol=0.55):
        start = int(start_beat * self.beat * SR)
        for i in range(int(0.16 * SR)):
            t = i / SR
            f = 40 + 90 * math.exp(-t * 35)
            self.buf[(start + i) % self.n] += math.sin(2 * math.pi * f * t) * math.exp(-t * 22) * vol

    def snare(self, start_beat, vol=0.28, rng=None):
        rng = rng or random
        start = int(start_beat * self.beat * SR)
        for i in range(int(0.16 * SR)):
            t = i / SR
            noise = rng.random() * 2 - 1
            self.buf[(start + i) % self.n] += (noise * 0.8 + math.sin(2 * math.pi * 190 * t) * 0.4) * math.exp(-t * 26) * vol

    def hat(self, start_beat, vol=0.08, rng=None, length=0.04):
        rng = rng or random
        start = int(start_beat * self.beat * SR)
        prev = 0.0
        for i in range(int(length * SR)):
            noise = rng.random() * 2 - 1
            self.buf[(start + i) % self.n] += (noise - prev) * math.exp(-i / SR * 90) * vol
            prev = noise

    def save(self, name: str, gain=0.85):
        peak = max(abs(x) for x in self.buf) or 1.0
        scale = gain / peak
        edge = int(0.005 * SR)   # 5 ms fade at both ends so the loop point can never click
        for i in range(edge):
            ramp = i / edge
            self.buf[i] *= ramp
            self.buf[-1 - i] *= ramp
        data = array("h", (int(math.tanh(x * scale * 1.2) * 0.9 * 32767) for x in self.buf))
        os.makedirs(OUT, exist_ok=True)
        path = os.path.join(OUT, f"{name}.wav")
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes(data.tobytes())
        print(f"  {name}.wav  {self.seconds:.1f}s")


# ------------------------------------------------------------------ compositions
def menu_track() -> Track:
    """Calm A-minor: slow pad, rolling arpeggio, a small lead line."""
    t = Track(bpm=76, bars=8)
    prog = [("A2", ["A3", "C4", "E4"]), ("F2", ["F3", "A3", "C4"]), ("C3", ["C4", "E4", "G4"]), ("G2", ["G3", "B3", "D4"])]
    lead = {0: ["E5", "D5", "C5", "D5"], 1: ["C5", "A4", "C5", "E5"], 2: ["G5", "E5", "D5", "C5"], 3: ["D5", "B4", "D5", "G4"]}
    for bar in range(8):
        root, chord = prog[bar % 4]
        b = bar * 4
        t.note(hz(root), b, 2, "triangle", vol=0.34, release=0.4)
        t.note(hz(root), b + 2, 2, "triangle", vol=0.30, release=0.4)
        t.chord([hz(n) for n in chord], b, 4, wave_name="triangle", vol=0.09, attack=0.35, release=0.6)
        for k in range(8):   # arpeggio in eighths
            n = chord[[0, 1, 2, 1, 0, 1, 2, 1][k]]
            octave_up = n[:-1] + str(int(n[-1]) + 1)
            t.note(hz(octave_up), b + k * 0.5, 0.45, "sine", vol=0.11, release=0.25)
        if bar % 2 == 0:
            for k, n in enumerate(lead[(bar // 2) % 4]):
                t.note(hz(n), b + k * 1.0 + 0.0, 0.9, "square", vol=0.05, release=0.3, vibrato=0.004)
    return t


def dungeon_track() -> Track:
    """Dark D-minor ambience: low drone pulse, sparse bells, soft kick and ticking hats."""
    rng = random.Random(7)
    t = Track(bpm=88, bars=8)
    prog = [("D2", ["D3", "F3", "A3"]), ("Bb1", ["Bb2", "D3", "F3"]), ("G2", ["G3", "Bb3", "D4"]), ("A1", ["A2", "C#3", "E3"])]
    bells = ["D5", "F5", "A5", "C6", "E5", "G5", "A4", "D6"]
    for bar in range(8):
        root, chord = prog[bar % 4]
        b = bar * 4
        t.chord([hz(n) for n in chord], b, 4, wave_name="saw", vol=0.045, attack=0.6, release=0.8)
        for k in range(8):
            octave = 0 if k % 4 != 3 else 1
            r = root[:-1] + str(int(root[-1]) + octave)
            t.note(hz(r), b + k * 0.5, 0.4, "square", vol=0.10 if k % 2 == 0 else 0.06, release=0.1)
        t.kick(b, 0.42)
        t.kick(b + 2.0, 0.34)
        for k in range(8):
            t.hat(b + k * 0.5 + 0.25, vol=0.035, rng=rng)
        for _ in range(rng.choice([1, 2, 2])):
            t.note(hz(rng.choice(bells)), b + rng.choice([0.5, 1.5, 2.5, 3.0, 3.5]), 1.2, "sine", vol=0.10, release=1.2)
    return t


def boss_track() -> Track:
    """Driving E-phrygian: 16th bass, four-on-the-floor kick, snare backbeat and a square lead riff."""
    rng = random.Random(11)
    t = Track(bpm=144, bars=8)
    prog = [("E2", ["E3", "G3", "B3"]), ("F2", ["F3", "A3", "C4"]), ("E2", ["E3", "G3", "B3"]), ("D2", ["D3", "F3", "A3"])]
    riff = [
        ["E5", "E5", "G5", "E5", "F5", "E5", "D5", "E5"],
        ["F5", "F5", "A5", "F5", "G5", "F5", "E5", "F5"],
        ["E5", "G5", "B5", "G5", "E5", "G5", "B5", "A5"],
        ["D5", "D5", "F5", "D5", "E5", "D5", "C5", "B4"],
    ]
    for bar in range(8):
        root, chord = prog[bar % 4]
        b = bar * 4
        for k in range(16):
            r = root[:-1] + str(int(root[-1]) + (1 if k % 8 == 6 else 0))
            t.note(hz(r), b + k * 0.25, 0.22, "square", vol=0.13 if k % 4 == 0 else 0.08, release=0.05)
        for beat in range(4):
            t.kick(b + beat, 0.5)
        t.snare(b + 1, rng=rng)
        t.snare(b + 3, rng=rng)
        for k in range(8):
            t.hat(b + k * 0.5 + 0.25, vol=0.05, rng=rng)
        t.chord([hz(n) for n in chord], b, 0.5, wave_name="saw", vol=0.05, release=0.25)
        t.chord([hz(n) for n in chord], b + 2, 0.5, wave_name="saw", vol=0.05, release=0.25)
        line = riff[bar % 4]
        for k, n in enumerate(line):
            t.note(hz(n), b + k * 0.5, 0.45, "pulse", vol=0.065, release=0.1, vibrato=0.003)
    return t


def main():
    print("Building music in", OUT)
    for name, builder in (("menu", menu_track), ("dungeon", dungeon_track), ("boss", boss_track)):
        builder().save(name)


if __name__ == "__main__":
    main()
