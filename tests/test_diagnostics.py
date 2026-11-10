import unittest
from types import SimpleNamespace
from app.core.diagnostics import safe_endpoint, PlaybackDiagnostics


class DiagnosticsTests(unittest.TestCase):
    def test_signed_query_and_userinfo_not_logged(self):
        self.assertEqual(safe_endpoint('https://user:password@video.example/videoplayback?token=SECRET#secret'), 'https://video.example/videoplayback')

    def test_buffer_bounded(self):
        diag = PlaybackDiagnostics(SimpleNamespace(on=lambda *args: None))
        for _ in range(30):
            diag.failed(SimpleNamespace(resource_type='media', failure='net::ERR_CONNECTION_RESET', url='https://video.example/media?secret=value'))
        self.assertEqual(len(diag.summary()), 15)
        self.assertNotIn('secret', str(diag.summary()))
