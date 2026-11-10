"""Record bounded diagnostics without cookies or signed media URL parameters."""
from collections import deque
from urllib.parse import urlsplit


def safe_endpoint(url):
    parsed = urlsplit(url)
    return f'{parsed.scheme}://{parsed.hostname or "unknown"}{parsed.path}'


class PlaybackDiagnostics:
    def __init__(self, page):
        self.events = deque(maxlen=15)
        page.on('requestfailed', self.failed)
        page.on('response', self.response)
        page.on('pageerror', lambda error: self.events.append('JavaScript error (detail sengaja tidak direkam)'))

    def failed(self, request):
        if request.resource_type in ('media', 'document', 'fetch', 'xhr'):
            # Failure strings are browser error codes, not response bodies.
            self.events.append(f'{request.failure} {safe_endpoint(request.url)}')

    def response(self, response):
        if response.status >= 400 and response.request.resource_type in ('media', 'document', 'fetch', 'xhr'):
            self.events.append(f'HTTP {response.status} {safe_endpoint(response.url)}')

    def summary(self):
        return list(self.events)
