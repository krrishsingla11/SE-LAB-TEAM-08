# Creates three short .wav sound effects in assets/sounds/.
# Standard library only (wave, struct, math). Run it once:
#     python generate_sounds.py

import math
import os
import struct
import wave

SAMPLE_RATE = 22050  # samples per second (fine for simple effects)

# Save next to THIS script, so it works from any folder.
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sounds")


def write_wav(filename, samples):
    """Save a list of samples (floats from -1.0 to 1.0) as a 16-bit mono .wav file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)

    # Convert each float to a 16-bit integer and pack it as bytes.
    frames = b"".join(
        struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)) for s in samples
    )

    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)          # mono
        wav_file.setsampwidth(2)          # 16-bit
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(frames)
    print("Created", path)


def make_fire_sound():
    """Short 'pew': a square-ish tone sliding from high to low pitch."""
    duration = 0.15
    total = int(SAMPLE_RATE * duration)
    samples = []
    phase = 0.0
    for i in range(total):
        progress = i / total                       # 0.0 -> 1.0
        freq = 900 - 600 * progress                # slides 900 Hz -> 300 Hz
        phase += 2 * math.pi * freq / SAMPLE_RATE
        wave_value = 1.0 if math.sin(phase) >= 0 else -1.0   # square wave
        envelope = 1.0 - progress                  # fades out
        samples.append(wave_value * envelope * 0.3)
    return samples


def make_explosion_sound():
    """Short 'boom': noise that fades out quickly."""
    duration = 0.35
    total = int(SAMPLE_RATE * duration)
    samples = []
    seed = 12345        # simple pseudo-random generator (no extra imports)
    previous = 0.0
    for i in range(total):
        seed = (seed * 1103515245 + 12345) % 2147483648
        noise = (seed / 2147483648) * 2 - 1        # random value -1..1
        # Average with the previous sample to soften it (deeper rumble).
        smooth = (noise + previous) / 2
        previous = smooth
        progress = i / total
        envelope = (1.0 - progress) ** 2           # fast fade out
        samples.append(smooth * envelope * 0.9)
    return samples


def make_game_over_sound():
    """Sad descending notes."""
    notes = [(440, 0.20), (370, 0.20), (311, 0.20), (220, 0.55)]  # (Hz, seconds)
    samples = []
    for freq, length in notes:
        total = int(SAMPLE_RATE * length)
        for i in range(total):
            progress = i / total
            # Fade out over the last 40% of each note so notes don't click.
            envelope = 1.0 if progress < 0.6 else (1.0 - progress) / 0.4
            t = i / SAMPLE_RATE
            samples.append(math.sin(2 * math.pi * freq * t) * envelope * 0.4)
    return samples


if __name__ == "__main__":
    write_wav("fire.wav", make_fire_sound())
    write_wav("explosion.wav", make_explosion_sound())
    write_wav("game_over.wav", make_game_over_sound())
    print("Done! Sounds are in:", OUTPUT_DIR)