import asyncio
import unittest
from unittest.mock import patch
from app.core.runner import Runner
from app.core.playback_probe import PlaybackProbe
from app.core.view_count_monitor import parse_snapshot


class ProbeTests(unittest.TestCase):
    def test_youtube_overlay_is_error_even_when_media_has_no_error(self):
        probe = PlaybackProbe('abcdefghijk', 60)
        sample = self.sample(39, paused=True, error=False, error_message='Something went wrong. Refresh or try again later.')
        with self.assertRaisesRegex(RuntimeError, 'YouTube player: Something went wrong'):
            probe.feed(sample, 39)

    def sample(self, t, **changes):
        return dict(dict(id='abcdefghijk', t=t, paused=False, ready=4,
                         ended=False, duration=20, error=False, ad=False), **changes)

    def test_pause_buffer_seek_ad_wrong_video(self):
        probe = PlaybackProbe('abcdefghijk', 10)
        probe.feed(self.sample(0), 0)
        probe.feed(self.sample(1), 1)
        self.assertEqual(probe.played, 1)
        probe.feed(self.sample(2, paused=True), 2)
        probe.feed(self.sample(3), 3)
        probe.feed(self.sample(4, ready=1), 4)
        probe.feed(self.sample(5), 5)
        probe.feed(self.sample(15), 6)  # seek
        probe.feed(self.sample(16, ad=True), 7)
        probe.feed(self.sample(17, id='other'), 8)
        self.assertEqual(probe.played, 1)

    def test_short_end_and_early_end(self):
        probe = PlaybackProbe('abcdefghijk', 30, True)
        for t in range(5):
            done, _ = probe.feed(self.sample(t, duration=4, ended=t==4, paused=t==4), t)
        self.assertTrue(done)
        early = PlaybackProbe('abcdefghijk', 30, True)
        early.feed(self.sample(0, duration=4), 0)
        with self.assertRaises(RuntimeError):
            early.feed(self.sample(4, duration=4, ended=True), 1)

    def test_locale_counts(self):
        for raw, locale, value in [('1,234 views', 'en-US', 1234), ('1.234 tayangan', 'id', 1234), ('0 views', 'en', 0)]:
            self.assertEqual(parse_snapshot(raw, locale)['value'], value)
        self.assertEqual(parse_snapshot('1.234 x ditonton', 'id')['value'], 1234)
        for raw in ('1.2K views', '1,2 rb tayangan'):
            self.assertEqual(parse_snapshot(raw)['precision'], 'abbreviated')
        for raw in ('1.234 views', '1,23 views', '10 likes 2 comments'):
            self.assertEqual(parse_snapshot(raw)['precision'], 'unavailable')


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    def runner(self, **overrides):
        runner = Runner(dict(dict(total=5, windows=2, duration=.02, simulation=True, monitor=False), **overrides))
        runner.log = lambda message: None
        return runner

    async def test_stop_during_initial_monitor_accounts_all(self):
        runner = self.runner(simulation=False, monitor=True)
        entered = asyncio.Event()
        async def inspect(pw):
            entered.set()
            await asyncio.sleep(10)
        runner.inspect_views = inspect
        task = asyncio.create_task(runner.workload(None))
        await entered.wait()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.assertEqual(runner.counts['cancelled'], 5)

    async def test_monitor_shares_limit_and_no_overlap(self):
        runner = self.runner(simulation=False, monitor=True, monitor_interval=.01, total=7)
        active, peak, inspections = 0, 0, 0
        async def use_slot(pw, number=None):
            nonlocal active, peak, inspections
            active += 1
            peak = max(peak, active)
            if number is None:
                inspections += 1
            try:
                await asyncio.sleep(.03)
            finally:
                active -= 1
            if number is not None:
                runner.counts['completed'] += 1
        runner.session = use_slot
        runner.inspect_views = use_slot
        await runner.workload(None)
        self.assertLessEqual(peak, 2)
        self.assertGreater(inspections, 2)
        self.assertEqual(runner.counts['completed'], 7)

    async def test_cleanup_failure_halts_runner(self):
        runner = self.runner()
        class Broken:
            async def close(self):
                raise RuntimeError('cannot close')
        await runner.close_browser(None, Broken())
        self.assertTrue(runner.cleanup_failed)
        self.assertTrue(runner.stop_event.is_set())

    async def test_log_failure_requests_stop(self):
        runner = Runner(dict(total=1))
        class BrokenLogger:
            def info(self, message):
                raise OSError('disk full')
        runner.logger = BrokenLogger()
        runner.log('test')
        self.assertTrue(runner.stop_event.is_set())
        self.assertTrue(runner.log_failed)
