import os

from django.test import SimpleTestCase, TestCase

from core.audio_player import _build_file_list
from core.number_words import english_tokens, number_tokens, urdu_tokens


class NumberWordTests(SimpleTestCase):
    def test_english_whole_number(self):
        self.assertEqual(english_tokens(321), ['3', '100', 'and', '20', '1'])
        self.assertEqual(english_tokens(12), ['12'])
        self.assertEqual(english_tokens(100), ['1', '100'])
        self.assertEqual(english_tokens(101), ['1', '100', 'and', '1'])
        self.assertEqual(english_tokens(1000), ['1', '1000'])
        self.assertEqual(english_tokens(1234), ['1', '1000', '2', '100', 'and', '30', '4'])
        self.assertEqual(english_tokens(0), ['0'])

    def test_urdu_whole_number(self):
        self.assertEqual(urdu_tokens(321), ['3', '100', '21'])
        self.assertEqual(urdu_tokens(12), ['12'])
        self.assertEqual(urdu_tokens(99), ['99'])
        self.assertEqual(urdu_tokens(100), ['1', '100'])
        self.assertEqual(urdu_tokens(1000), ['1', '1000'])
        self.assertEqual(urdu_tokens(0), ['0'])

    def test_number_tokens_picks_language(self):
        self.assertEqual(number_tokens(321, 'en'), english_tokens(321))
        self.assertEqual(number_tokens(321, 'ur'), urdu_tokens(321))


class AnnouncementFileTests(SimpleTestCase):
    def test_announcement_uses_word_clips_not_digits(self):
        files = [os.path.basename(f) for f in _build_file_list('A321', 'Cash Counter', 'en')]

        self.assertEqual(files[:7], [
            'en_ticket.mp3',
            'en_A.mp3',
            'en_n_3.mp3',
            'en_n_100.mp3',
            'en_n_and.mp3',
            'en_n_20.mp3',
            'en_n_1.mp3',
        ])
        self.assertEqual(files[7:], [
            'en_please_proceed_to.mp3',
            'en_counter_cash_counter.mp3',
        ])

    def test_urdu_announcement_uses_urdu_word_clips(self):
        files = [os.path.basename(f) for f in _build_file_list('A321', 'Cash Counter', 'ur')]

        self.assertEqual(files[:6], [
            'ur_ticket.mp3',
            'ur_A.mp3',
            'ur_n_3.mp3',
            'ur_n_100.mp3',
            'ur_n_21.mp3',
            'ur_please_proceed_to.mp3',
        ])


class AudioFileExistenceTests(TestCase):
    def test_all_number_words_have_clips(self):
        """Guards against forgetting to run ``python generate_audio.py``."""
        from core.number_words import EN_WORDS, UR_WORDS

        audio_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static', 'audio')
        missing = []
        for lang, words in (('en', EN_WORDS), ('ur', UR_WORDS)):
            for token in words:
                path = os.path.join(audio_dir, f'{lang}_n_{token}.mp3')
                if not os.path.exists(path):
                    missing.append(os.path.basename(path))
        self.assertEqual(missing, [])
