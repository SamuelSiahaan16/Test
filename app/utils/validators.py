import re
import math
from urllib.parse import urlparse, parse_qs

def video_id(url):
    p = urlparse(url.strip())
    if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Gunakan URL HTTPS YouTube.')
    if p.hostname == 'youtu.be':
        value = p.path.strip('/')
    elif p.hostname in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        if p.path == '/watch':
            value = parse_qs(p.query).get('v', [''])[0]
        elif re.fullmatch(r'/shorts/[A-Za-z0-9_-]{11}/?', p.path):
            value = p.path.strip('/').split('/')[1]
        else:
            raise ValueError('Gunakan tautan watch?v=, shorts/VIDEO_ID, atau youtu.be.')
    else:
        raise ValueError('Gunakan tautan watch?v=, shorts/VIDEO_ID, atau youtu.be.')
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', value):
        raise ValueError('Video ID tidak valid.')
    return value


def short_target(requested, duration, is_short):
    if is_short and isinstance(duration, (int, float)) and math.isfinite(duration) and duration > 0:
        return min(requested, duration)
    return requested


def ended_success(played, target):
    # Allow only a small sampling gap, never accept a seek to the ending.
    return played >= target - min(.75, target * .1)


def parse_views(text):
    """Only accept unambiguous English full counts; retain original text otherwise."""
    match = re.search(r'(?<![\w.,])(\d{1,3}(?:,\d{3})+|\d+)\s+views?\b', text, re.I)
    if match:
        return int(match[1].replace(',', ''))
    return None
