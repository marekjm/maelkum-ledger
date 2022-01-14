try:
    import colored
except ImportError:
    colored = None


# Colorisation utilities.
def colorise_if_possible(color, s):
    s = str(s)
    if colored is None:
        return s
    return (colored.fg(color) + s + colored.attr('reset'))

def colorise(color, s):
    return colorise_if_possible(color, s)

def colorise_repr(color, s):
    s = repr(s)
    return s[0] + colorise_if_possible(color, s[1:-1]) + s[0]

COLOR_CATASTROPHE = 'red_3a'
COLOR_FATAL = 'red'
COLOR_WARNING = 'orange_red_1'
COLOR_OK = 'green'

COLOR_EXPENSES = 'orange_red_1'
COLOR_REVENUES = 'medium_spring_green'
COLOR_NEUTRAL = 'light_sea_green'

COLOR_SHARE_PRICE = 'wheat_1'
COLOR_SHARE_PRICE_AVG = 'khaki_1'
COLOR_SHARE_WORTH = 'white'
COLOR_SHARE_COUNT = 'navajo_white_1'

COLOR_DATETIME = 'white'
COLOR_PERIOD_NAME = 'white'

COLOR_EXCHANGE_RATE = 'light_yellow'

COLOR_BALANCE_ZERO = 'cyan'
COLOR_BALANCE_NEGATIVE = 'indian_red_1c'
COLOR_BALANCE_POSITIVE = 'spring_green_3a'
def COLOR_BALANCE(balance):
    if balance > 0:
        return COLOR_BALANCE_POSITIVE
    elif balance < 0:
        return COLOR_BALANCE_NEGATIVE
    else:
        return COLOR_BALANCE_ZERO
def colorise_balance(balance, fmt = '{:.2f}'):
    return colorise(COLOR_BALANCE(balance), fmt.format(balance))

RATIO_COLORS = (
    'pale_turquoise_1',
    'sky_blue_1',
    'steel_blue_1b',
    'turquoise_2',
    'dark_turquoise',
    'deep_sky_blue_1',
    'deep_sky_blue_2',
    'deep_sky_blue_3b',
    'deep_sky_blue_3a',
    'light_sea_green',
    'medium_spring_green',
    'spring_green_3b',
    'spring_green_3a',
    'spring_green_4',
    'green_3a',
    'green_3b',
    'chartreuse_3b',
    'chartreuse_2b',
    'chartreuse_2a',
    'chartreuse_1',
    'green_yellow',
    'dark_olive_green_2',
    'pale_green_1b',
    'light_goldenrod_1',
    'yellow_1',
    'yellow_2',
    'yellow_3b',
    'sandy_brown',
    'salmon_1',
    'orange_3',
    'dark_goldenrod',
    'dark_orange_3a',
    'indian_red_1b',
    'red_3b',
    'red_1',
    'deep_pink_2',
    'deep_pink_1b',
    'deep_pink_1a',
    'deep_pink_4c',
    'medium_violet_red',
)
_delta = (100.0 / len(RATIO_COLORS))
RATIO_COLORS = tuple(
    ((_delta * x, _delta * (x + 1)), c,)
    for x, c
    in zip(range(len(RATIO_COLORS)), RATIO_COLORS)
)

def COLOR_SPENT_RATIO(percent):
    for (low, high), colour in RATIO_COLORS:
        low_match = (percent >= low)
        high_match = (percent <= high)
        if low_match and high_match:
            break
    return colour

def COLOR_SPENT_RATIO_old(percentage_spent):
    # Monthly revenues allow living for...
    if percentage_spent >= 100.0:   # ...less than a month.
        return 'light_red'

    if percentage_spent <= 16.0:    # ...more than half a year.
        return 'green'
    elif percentage_spent <= 25.0:  # ...four months to half a year.
        return 'light_green'
    elif percentage_spent <= 33.0:  # ...three to four months.
        return 'dark_olive_green_3b'
    elif percentage_spent <= 50.0:  # ...two to three months.
        return 'green_yellow'
    elif percentage_spent <= 66.0:  # ...a month to month and a half.
        return 'red'
    elif percentage_spent <= 75.0:  # ...slightly more than a month to month and a half.
        return 'red_3b'

    return 'red_3a'
