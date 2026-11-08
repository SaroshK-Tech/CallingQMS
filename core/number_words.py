"""Spoken forms of ticket numbers for the announcement system.

Ticket numbers look like ``A012``: a letter prefix followed by digits.
The digits are read as a whole number ("twelve", not "zero one two").

Each number is split into a list of *tokens*.  A token is the key of a
pre-generated audio clip (``static/audio/en_n_<token>.mp3``), which lets
us build any number from a small vocabulary of word clips.

English example: 321 -> ["3", "100", "and", "20", "1"]
Urdu example:    321 -> ["3", "100", "21"]
"""

# English word pieces
EN_WORDS = {
    '0': 'zero',
    '1': 'one',
    '2': 'two',
    '3': 'three',
    '4': 'four',
    '5': 'five',
    '6': 'six',
    '7': 'seven',
    '8': 'eight',
    '9': 'nine',
    '10': 'ten',
    '11': 'eleven',
    '12': 'twelve',
    '13': 'thirteen',
    '14': 'fourteen',
    '15': 'fifteen',
    '16': 'sixteen',
    '17': 'seventeen',
    '18': 'eighteen',
    '19': 'nineteen',
    '20': 'twenty',
    '30': 'thirty',
    '40': 'forty',
    '50': 'fifty',
    '60': 'sixty',
    '70': 'seventy',
    '80': 'eighty',
    '90': 'ninety',
    '100': 'hundred',
    '1000': 'thousand',
    'and': 'and',
}

# Urdu uses a distinct word for every number below 100 (e.g. 21 = اکیس),
# so all of 0-99 are vocabulary entries.
UR_WORDS = {
    '0': 'صفر',
    '1': 'ایک',
    '2': 'دو',
    '3': 'تین',
    '4': 'چار',
    '5': 'پانچ',
    '6': 'چھ',
    '7': 'سات',
    '8': 'آٹھ',
    '9': 'نو',
    '10': 'دس',
    '11': 'گیارہ',
    '12': 'بارہ',
    '13': 'تیرہ',
    '14': 'چودہ',
    '15': 'پندرہ',
    '16': 'سولہ',
    '17': 'سترہ',
    '18': 'اٹھارہ',
    '19': 'انیس',
    '20': 'بیس',
    '21': 'اکیس',
    '22': 'بائیس',
    '23': 'تئیس',
    '24': 'چوبیس',
    '25': 'پچیس',
    '26': 'چھبیس',
    '27': 'ستائیس',
    '28': 'اٹھائیس',
    '29': 'انتیس',
    '30': 'تیس',
    '31': 'اکتیس',
    '32': 'بتیس',
    '33': 'تینتیس',
    '34': 'چونتیس',
    '35': 'پینتیس',
    '36': 'چھتیس',
    '37': 'سینتیس',
    '38': 'اڑتیس',
    '39': 'انتالیس',
    '40': 'چالیس',
    '41': 'اکتالیس',
    '42': 'بیالیس',
    '43': 'تینتالیس',
    '44': 'چوالیس',
    '45': 'پینتالیس',
    '46': 'چھیالیس',
    '47': 'سینتالیس',
    '48': 'اڑتالیس',
    '49': 'انچاس',
    '50': 'پچاس',
    '51': 'اکاون',
    '52': 'باون',
    '53': 'ترپن',
    '54': 'چون',
    '55': 'پچپن',
    '56': 'چھپن',
    '57': 'ستاون',
    '58': 'اٹھاون',
    '59': 'انسٹھ',
    '60': 'ساٹھ',
    '61': 'اکسٹھ',
    '62': 'باسٹھ',
    '63': 'ترسٹھ',
    '64': 'چونسٹھ',
    '65': 'پینسٹھ',
    '66': 'چھیاسٹھ',
    '67': 'سڑسٹھ',
    '68': 'اڑسٹھ',
    '69': 'انہتر',
    '70': 'ستر',
    '71': 'اکہتر',
    '72': 'بہتر',
    '73': 'تہتر',
    '74': 'چوہتر',
    '75': 'پچہتر',
    '76': 'چھہتر',
    '77': 'ستتر',
    '78': 'اٹھہتر',
    '79': 'اناسی',
    '80': 'اسی',
    '81': 'اکیاسی',
    '82': 'بیاسی',
    '83': 'تراسی',
    '84': 'چوراسی',
    '85': 'پچاسی',
    '86': 'چھیاسی',
    '87': 'ستاسی',
    '88': 'اٹھاسی',
    '89': 'نواسی',
    '90': 'نوے',
    '91': 'اکانوے',
    '92': 'بانوے',
    '93': 'ترانوے',
    '94': 'چورانوے',
    '95': 'پچانوے',
    '96': 'چھیانوے',
    '97': 'ستانوے',
    '98': 'اٹھانوے',
    '99': 'ننانوے',
    '100': 'سو',
    '1000': 'ہزار',
}


def english_tokens(number):
    """Return the English word tokens for a non-negative integer."""
    n = int(number)
    if n <= 0:
        return ['0']

    tokens = []
    if n >= 1000:
        tokens += english_tokens(n // 1000) + ['1000']
        n %= 1000
        if n and n < 100:
            tokens.append('and')
    if n >= 100:
        tokens += english_tokens(n // 100) + ['100']
        n %= 100
        if n:
            tokens.append('and')
    if n >= 20:
        tokens.append(str(n // 10 * 10))
        n %= 10
    if n:
        tokens.append(str(n))
    return tokens


def urdu_tokens(number):
    """Return the Urdu word tokens for a non-negative integer."""
    n = int(number)
    if n <= 0:
        return ['0']

    tokens = []
    if n >= 1000:
        tokens += urdu_tokens(n // 1000) + ['1000']
        n %= 1000
    if n >= 100:
        tokens += [str(n // 100), '100']
        n %= 100
    if n:
        tokens.append(str(n))
    return tokens


def number_tokens(number, lang):
    """Return word tokens for ``number`` in ``lang`` ('en' or 'ur')."""
    if lang == 'ur':
        return urdu_tokens(number)
    return english_tokens(number)


def vocabulary(lang):
    """Map of token -> spoken word for a language."""
    return UR_WORDS if lang == 'ur' else EN_WORDS
