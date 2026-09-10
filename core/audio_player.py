"""Server-side announcement playback.

Plays the chime + English + Urdu announcement sequence on the machine
running the server (must have ffplay from ffmpeg available).
"""
import os
import queue
import re
import shutil
import subprocess
import sys
import threading

AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'audio')
CHIME = os.path.join(AUDIO_DIR, 'chime.wav')

_queue = queue.Queue()
_player_thread = None
_worker_lock = threading.Lock()


def _slug(name):
    return re.sub(r'[^a-z0-9]+', '_', name.strip().lower())


def _build_file_list(ticket_number, counter_name, lang):
    series = ticket_number[0] if ticket_number else ''
    digits = ticket_number[1:] if ticket_number else ''
    files = [os.path.join(AUDIO_DIR, f'{lang}_ticket.mp3')]
    if series:
        files.append(os.path.join(AUDIO_DIR, f'{lang}_{series}.mp3'))
    for d in digits:
        files.append(os.path.join(AUDIO_DIR, f'{lang}_{d}.mp3'))
    files.append(os.path.join(AUDIO_DIR, f'{lang}_please_proceed_to.mp3'))
    files.append(os.path.join(AUDIO_DIR, f'{lang}_counter_{_slug(counter_name)}.mp3'))
    return files


def _ensure_worker():
    global _player_thread
    with _worker_lock:
        if _player_thread is None or not _player_thread.is_alive():
            _player_thread = threading.Thread(target=_worker, daemon=True)
            _player_thread.start()


def _worker():
    while True:
        files = _queue.get()
        for path in files:
            if not os.path.exists(path):
                continue
            _play_wait(path)


def _play_wait(path):
    player = shutil.which('ffplay')
    if not player:
        return
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform == 'win32' else 0
    try:
        subprocess.run(
            [player, '-nodisp', '-autoexit', '-loglevel', 'quiet', path],
            creationflags=flags,
            check=False,
        )
    except Exception:
        pass


def announce(ticket_number, counter_name):
    """Queue the chime + English announcement for a ticket call."""
    files = [CHIME]
    files += _build_file_list(ticket_number, counter_name, 'en')
    _queue.put(files)
    _ensure_worker()