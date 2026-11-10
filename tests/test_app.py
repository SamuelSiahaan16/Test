import asyncio
import unittest
from main import Runner, video_id, parse_views, short_target, ended_success


class Tests(unittest.TestCase):
    def test_shorts_urls(self):
        for host in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
            self.assertEqual(video_id(f'https://{host}/shorts/abcdefghijk/?si=example'), 'abcdefghijk')
        for url in ('https://youtube.com/shorts/abcdefghijk/extra', 'https://youtube.com/shorts/abc', 'https://youtube.com.evil/shorts/abcdefghijk'):
            with self.assertRaises(ValueError):
                video_id(url)

    def test_short_duration(self):
        self.assertEqual(short_target(30, 12, True), 12)
        self.assertEqual(short_target(5, 12, True), 5)
        self.assertEqual(short_target(30, 12, False), 30)
        for duration in (None, 0, float('nan'), float('inf')):
            self.assertEqual(short_target(30, duration, True), 30)
        self.assertTrue(ended_success(11.6, 12))
        self.assertFalse(ended_success(2, 12))
        self.assertFalse(ended_success(0, .5))

    def test_url(self):
        self.assertEqual(video_id('https://youtu.be/abcdefghijk?t=4'), 'abcdefghijk')
        for url in ('https://youtube.com.evil/watch?v=abcdefghijk', 'http://youtu.be/abcdefghijk', 'https://youtube.com/playlist?list=x'):
            with self.assertRaises(ValueError):
                video_id(url)

    def test_count(self):
        self.assertEqual(parse_views('1,234 views 2 days ago'), 1234)
        self.assertEqual(parse_views('0 views'), 0)
        self.assertIsNone(parse_views('1.2K views'))
        self.assertIsNone(parse_views('1.234 tayangan'))

    def test_simulated_accounting(self):
        runner = Runner(dict(total=5, windows=2, duration=.01, simulation=True, monitor=False))
        runner.log = lambda message: None
        asyncio.run(runner.workload(None))
        self.assertEqual(runner.counts, dict(completed=5, failed=0, cancelled=0, active=0))

    def test_cancel(self):
        runner = Runner(dict(total=5, windows=2, duration=10, simulation=True, monitor=False))
        runner.log = lambda message: None
        async def check():
            task = asyncio.create_task(runner.workload(None))
            await asyncio.sleep(.05)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        asyncio.run(check())
        self.assertEqual(runner.counts['cancelled'], 5)
        self.assertEqual(runner.counts['active'], 0)


if __name__ == '__main__':
    unittest.main()
