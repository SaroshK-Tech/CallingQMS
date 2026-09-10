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

AUDIO_DIR = os.path.join(os.path.dirname(__file__), 'static', 'audio')
os.makedirs(AUDIO_DIR, exist_ok=True)

# Service prefixes to generate
SERIES = ['A', 'B', 'C', 'D']
DIGITS = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']


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

def generate_urdu():
    """Generate Urdu audio files"""
    print("Generating Urdu audio files...")
    
    prefix_words = {
        'A': 'اے',
        'B': 'بی',
        'C': 'سی',
        'D': 'ڈی',
    }
    
    phrases = {
        'ticket': 'ٹکٹ نمبر',
        'please_proceed_to': 'براہ کرم جائیں',
        'your_turn': 'آپ کی باری ہے',
        'waiting': 'براہ کرم اپنی باری کا انتظار کریں',
    }
    
    for key, text in phrases.items():
        tts = gTTS(text=text, lang='ur')
        tts.save(os.path.join(AUDIO_DIR, f'ur_{key}.mp3'))
        print(f"  ur_{key}.mp3")
    
    for series in SERIES:
        tts = gTTS(text=prefix_words[series], lang='ur')
        tts.save(os.path.join(AUDIO_DIR, f'ur_{series}.mp3'))
        print(f"  ur_{series}.mp3")
    
    for digit in DIGITS:
        # Urdu digits
        urdu_digits = {
            '0': 'صفر', '1': 'ایک', '2': 'دو', '3': 'تین', '4': 'چار',
            '5': 'پانچ', '6': 'چھ', '7': 'سات', '8': 'آٹھ', '9': 'نو'
        }
        tts = gTTS(text=urdu_digits[digit], lang='ur')
        tts.save(os.path.join(AUDIO_DIR, f'ur_{digit}.mp3'))
        print(f"  ur_{digit}.mp3")


def _render_counter_audio(counter):
    """Generate the EN + UR name announcement files for one Counter."""
    label = counter.display_name or counter.name
    slug = counter_slug(label)
    for lang in ('en', 'ur'):
        filename = f'{lang}_counter_{slug}.mp3'
        tts = gTTS(text=label, lang=lang)
        tts.save(os.path.join(AUDIO_DIR, filename))
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

def generate_chime():
    """Generate a bell/chime alert sound (WAV) used before announcements"""
    sample_rate = 44100
    duration = 1.2
    partials = [
        (880.0, 0.55, 3.2),
        (1318.5, 0.30, 4.2),
        (1760.0, 0.20, 5.5),
    ]
    frames = bytearray()
    for i in range(int(sample_rate * duration)):
        t = i / sample_rate
        smp = sum(amp * math.sin(2 * math.pi * freq * t) * math.exp(-decay * t)
                  for freq, amp, decay in partials)
        smp = max(-1.0, min(1.0, smp))
        frames += struct.pack('<h', int(smp * 32767))
    path = os.path.join(AUDIO_DIR, 'chime.wav')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(bytes(frames))
    print(f"  chime.wav")


if __name__ == '__main__':
    generate_chime()
    generate_english()
    generate_urdu()
    generate_counter_names()
    print(f"\nAll audio files generated in {AUDIO_DIR}")
    print("Note: For production, use a professional voice service for better quality.")
