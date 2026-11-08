"""
Generate audio files for the EQMS system.
Run: python generate_audio.py
"""
import math
import os
import re
import struct
import wave
from gtts import gTTS

from core.number_words import EN_WORDS, UR_WORDS

AUDIO_DIR = os.path.join(os.path.dirname(__file__), 'static', 'audio')
os.makedirs(AUDIO_DIR, exist_ok=True)

# Service prefixes to generate
SERIES = ['A', 'B', 'C', 'D']
DIGITS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']

# Natural Urdu voice — spoken back in its original accent
URDU_VOICE = 'ur-PK-UzmaNeural'


def counter_slug(label):
    """Match the slug used by static/js/main.js"""
    return re.sub(r'[^a-z0-9]+', '_', label.strip().lower())


def _setup_django():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eqms.settings')
    import django
    django.setup()

def generate_english():
    """Generate English audio files"""
    print("Generating English audio files...")
    
    # Prefix words
    prefix_words = {
        'A': 'A',
        'B': 'B', 
        'C': 'C',
        'D': 'D',
    }
    
    # Phrases
    phrases = {
        'ticket': 'Ticket number',
        'please_proceed_to': 'Please proceed to',
        'your_turn': 'Your turn',
        'waiting': 'Please wait for your turn',
    }
    
    for key, text in phrases.items():
        tts = gTTS(text=text, lang='en')
        tts.save(os.path.join(AUDIO_DIR, f'en_{key}.mp3'))
        print(f"  en_{key}.mp3")
    
    # Series letters
    for series in SERIES:
        tts = gTTS(text=prefix_words[series], lang='en')
        tts.save(os.path.join(AUDIO_DIR, f'en_{series}.mp3'))
        print(f"  en_{series}.mp3")
    
    # Digits
    for digit in DIGITS:
        tts = gTTS(text=digit, lang='en')
        tts.save(os.path.join(AUDIO_DIR, f'en_{digit}.mp3'))
        print(f"  en_{digit}.mp3")

def _trim_silence(path):
    """Strip leading/trailing silence with ffmpeg so clips run back-to-back."""
    import subprocess
    tmp = path + '.trim.mp3'
    cmd = [
        'ffmpeg', '-y', '-i', path,
        '-af',
        'silenceremove=start_periods=1:start_duration=0.02:start_threshold=-45dB:start_silence=0,'
        'areverse,'
        'silenceremove=start_periods=1:start_duration=0.02:start_threshold=-45dB:start_silence=0,'
        'areverse',
        '-codec:a', 'libmp3lame', '-b:a', '128k',
        tmp,
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode == 0 and os.path.exists(tmp):
        os.replace(tmp, path)
        return True
    if os.path.exists(tmp):
        os.remove(tmp)
    return False


def _edge_save(text, voice, path):
    """Save an MP3 with Microsoft's natural neural voice, trailing silence trimmed."""
    import asyncio
    from edge_tts import Communicate
    # Normal speech pace (silence already trimmed separately)
    comm = Communicate(text, voice, pitch='-20Hz')
    asyncio.run(comm.save(path))
    _trim_silence(path)


def generate_urdu():
    """Generate Urdu audio files with the natural Urdu neural voice."""
    print("Generating Urdu audio files...")

    phrases = {
        'ticket': 'ٹکٹ نمبر',
        'please_proceed_to': 'برائے مہربانی',
        'go_to': 'پر جائے',
        'your_turn': 'آپ کی باری ہے',
        'waiting': 'براہ کرم اپنی باری کا انتظار کریں',
    }

    for key, text in phrases.items():
        _edge_save(text, URDU_VOICE, os.path.join(AUDIO_DIR, f'ur_{key}.mp3'))
        print(f"  ur_{key}.mp3")

    for series in SERIES:
        # Letters spoken as English "A/B/C/D" (not the Urdu letter name "اے")
        _edge_save(series, 'en-US-AriaNeural', os.path.join(AUDIO_DIR, f'ur_{series}.mp3'))
        print(f"  ur_{series}.mp3")

    for digit in DIGITS:
        _edge_save(UR_WORDS[digit], URDU_VOICE, os.path.join(AUDIO_DIR, f'ur_{digit}.mp3'))
        print(f"  ur_{digit}.mp3")


def generate_number_words():
    """Generate the word clips used to speak ticket numbers as whole numbers.

    Every token in ``EN_WORDS`` / ``UR_WORDS`` becomes ``{lang}_n_{token}.mp3``
    (e.g. ``en_n_20.mp3`` = "twenty", ``ur_n_21.mp3`` = "اکیس").
    """
    print("Generating number word clips...")
    for lang, words, voice in (
        ('en', EN_WORDS, None),
        ('ur', UR_WORDS, URDU_VOICE),
    ):
        for token, word in words.items():
            path = os.path.join(AUDIO_DIR, f'{lang}_n_{token}.mp3')
            if voice:
                _edge_save(word, voice, path)
            else:
                tts = gTTS(text=word, lang='en')
                tts.save(path)
                _trim_silence(path)
            print(f"  {lang}_n_{token}.mp3")


def _render_counter_audio(counter):
    """Generate the EN + UR name announcement files for one Counter."""
    label = counter.display_name or counter.name
    slug = counter_slug(label)
    for lang in ('en', 'ur'):
        filename = f'{lang}_counter_{slug}.mp3'
        path = os.path.join(AUDIO_DIR, filename)
        if lang == 'ur':
            _edge_save(label, URDU_VOICE, path)
        else:
            tts = gTTS(text=label, lang='en')
            tts.save(path)
        print(f"  {filename}")


def generate_counter_names():
    """Generate counter name files for all counters currently in the DB."""
    _setup_django()
    from core.models import Counter
    print("Generating counter name audio files...")
    for counter in Counter.objects.all():
        _render_counter_audio(counter)


def regenerate_counter_audio(counter_id):
    """Regenerate audio for a single counter (used by admin on save)."""
    _setup_django()
    from core.models import Counter
    counter = Counter.objects.get(id=counter_id)
    _render_counter_audio(counter)

def _synth_bell(fundamental, duration=0.9, amp=1.0):
    """Synthesize a single natural bell strike using inharmonic partials.

    Real bells have overtones at non-integer ratios (Helmholtz modes) with
    slightly detuned neighbours that create a metallic shimmer.
    Returns a list of mono float samples.
    """
    sr = 44100
    n = int(sr * duration)
    # Bell partial ratios, amplitudes, and decay rates (relative to fundamental)
    modes = [
        (1.0,   0.40, 2.0),
        (2.0,   0.22, 3.0),
        (2.76,  0.18, 4.5),   # inharmonic (Helmholtz mode)
        (3.0,   0.12, 5.0),
        (4.24,  0.08, 6.5),   # inharmonic
        (5.40,  0.05, 8.0),   # inharmonic
        (5.55,  0.04, 9.0),   # close neighbour → metallic beating
    ]
    samples = []
    for i in range(n):
        t = i / sr
        # Attack envelope: short noise burst to simulate hammer strike
        attack = 1.0 - math.exp(-t * 80.0)
        smp = 0.0
        for ratio, a, decay in modes:
            freq = fundamental * ratio
            # Slight random detuning per partial (±2 Hz) adds realism
            f_off = freq + (hash((fundamental, ratio)) % 5 - 2)
            smp += a * math.sin(2 * math.pi * f_off * t) * math.exp(-decay * t)
        samples.append(amp * attack * smp)
    return samples


def generate_chime():
    """Generate a natural two-tone bell chime (ding-dong) used before announcements."""
    sr = 44100
    ding = _synth_bell(1047.0, duration=0.9, amp=0.7)   # C6
    dong = _synth_bell(784.0,  duration=1.2, amp=0.55)  # G5

    # Overlap region: dong fades in while ding fades out
    overlap = int(sr * 0.25)
    gap = int(sr * 0.10)   # slight gap between strikes

    total = len(ding) + gap + len(dong) - overlap
    out = [0.0] * total

    # Place ding
    for i, s in enumerate(ding):
        out[i] += s

    # Fade out tail of ding over the overlap region
    for i in range(overlap):
        idx = len(ding) - overlap + i
        if 0 <= idx < len(out):
            fade = 1.0 - (i / overlap)
            out[idx] *= fade

    # Place dong after gap, overlapping with ding tail
    dong_start = len(ding) + gap - overlap
    for i, s in enumerate(dong):
        pos = dong_start + i
        if pos < total:
            # Fade in at the start of dong
            if i < overlap:
                s *= i / overlap
            out[pos] += s

    # Normalise
    peak = max(abs(s) for s in out) or 1.0
    out = [s / peak for s in out]

    path = os.path.join(AUDIO_DIR, 'chime.wav')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b''.join(
            struct.pack('<h', int(max(-1.0, min(1.0, s)) * 32767)) for s in out
        ))
    print(f"  chime.wav")


if __name__ == '__main__':
    generate_chime()
    generate_english()
    generate_urdu()
    generate_number_words()
    generate_counter_names()
    print(f"\nAll audio files generated in {AUDIO_DIR}")
