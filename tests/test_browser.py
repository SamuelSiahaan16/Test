"""Real Chromium, local fixtures only; no YouTube requests."""
import asyncio
import unittest
from playwright.async_api import async_playwright
from app.core.view_count_monitor import read_snapshot
from app.core.playback_probe import SAMPLE_JS, PlaybackProbe


class BrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_metadata_replaced_on_hover_does_not_need_hover(self):
        context = await self.browser.new_context()
        page = await self.page(context, '''<html lang="en"><div id="info-container"
            title="1,234 views" onmouseenter="this.remove()">1.2K views</div></html>''')
        snapshot = await read_snapshot(page, 'abcdefghijk')
        self.assertEqual(snapshot['value'], 1234)
        self.assertEqual(await page.locator('#info-container').count(), 1)
        await context.close()

    async def test_shorts_shared_player_without_active_attribute(self):
        context = await self.browser.new_context()
        page = await context.new_page()
        await page.route('**/*', lambda route: route.fulfill(content_type='text/html', body='''
            <div id="movie_player" class="html5-video-player" style="display:none"><video></video></div>
            <div id="shorts-player" class="html5-video-player"><video></video></div>
            <script>
            document.querySelector('#movie_player').getVideoData=()=>({video_id:'wrong'});
            document.querySelector('#shorts-player').getVideoData=()=>({video_id:'abcdefghijk'});
            </script>'''))
        await page.goto('https://www.youtube.com/shorts/abcdefghijk')
        sample = await page.evaluate(SAMPLE_JS)
        self.assertEqual(sample['id'], 'abcdefghijk')
        locator = page.locator('#shorts-player:visible video, ytd-reel-video-renderer[is-active] video:visible').first
        await locator.wait_for(state='visible', timeout=1000)
        await context.close()

    async def test_shorts_reads_active_player_only(self):
        context = await self.browser.new_context()
        page = await context.new_page()
        await page.route('**/*', lambda route: route.fulfill(content_type='text/html', body='''
            <ytd-reel-video-renderer><video></video><div class="html5-video-player" id="inactive"></div>
            <div class="ytp-error-content">Inactive error</div></ytd-reel-video-renderer>
            <ytd-reel-video-renderer is-active><video></video><div class="html5-video-player" id="active"></div></ytd-reel-video-renderer>
            <script>
            document.querySelector('#inactive').getVideoData=()=>({video_id:'wrong'});
            document.querySelector('#active').getVideoData=()=>({video_id:'abcdefghijk'});
            </script>'''))
        await page.goto('https://www.youtube.com/shorts/abcdefghijk')
        sample = await page.evaluate(SAMPLE_JS)
        self.assertEqual(sample['id'], 'abcdefghijk')
        self.assertIsNone(sample['error_message'])
        await page.locator('[is-active]').evaluate('(e)=>e.removeAttribute("is-active")')
        self.assertIsNone((await page.evaluate(SAMPLE_JS))['id'])
        await context.close()

    async def test_visible_error_overlay(self):
        context = await self.browser.new_context()
        page = await self.page(context, '<div class="ytp-error-content-wrap" style="display:none">Hidden error</div><div class="ytp-error-content">Something went wrong. Refresh or try again later.</div>')
        sample = await page.evaluate(SAMPLE_JS)
        self.assertFalse(sample['error'])
        self.assertIn('Something went wrong', sample['error_message'])
        with self.assertRaisesRegex(RuntimeError, 'Something went wrong'):
            PlaybackProbe('abcdefghijk', 60).feed(sample, 0)
        await context.close()

    async def asyncSetUp(self):
        self.pw = await async_playwright().start()
        self.browser = await self.pw.chromium.launch(headless=True)

    async def asyncTearDown(self):
        await self.browser.close()
        await self.pw.stop()

    async def page(self, context, html):
        page = await context.new_page()
        await page.route('**/*', lambda route: route.fulfill(body=html, content_type='text/html'))
        await page.goto('https://www.youtube.com/watch?v=abcdefghijk')
        return page

    async def test_metadata_expansion_and_storage_isolation(self):
        context = await self.browser.new_context()
        page = await self.page(context, '''<html lang="id"><div id="description-inline-expander">
        <div id="info-container">1,2 rb tayangan</div>
        <button id="expand" onclick="document.getElementById('info-container').textContent='1.234 tayangan'">Lainnya</button>
        </div></html>''')
        snapshot = await read_snapshot(page, 'abcdefghijk')
        self.assertEqual(snapshot['value'], 1234)
        await page.evaluate("localStorage.setItem('private', 'yes'); document.cookie='private=yes'")
        await context.close()
        fresh = await self.browser.new_context()
        page = await self.page(fresh, '<html>new session</html>')
        self.assertIsNone(await page.evaluate("localStorage.getItem('private')"))
        self.assertEqual(await fresh.cookies(), [])
        await fresh.close()

    async def test_real_video_pause_does_not_count(self):
        context = await self.browser.new_context()
        page = await self.page(context, '''<video muted autoplay></video><canvas></canvas><div id="movie_player"></div>
        <script>
        const canvas=document.querySelector('canvas'), ctx=canvas.getContext('2d');
        setInterval(()=>{ctx.fillStyle=Math.random()>.5?'red':'blue';ctx.fillRect(0,0,100,100)},40);
        document.querySelector('video').srcObject=canvas.captureStream(25);
        document.querySelector('#movie_player').getVideoData=()=>({video_id:'abcdefghijk'});
        </script>''')
        await page.locator('video').evaluate('(v)=>v.play()')
        probe = PlaybackProbe('abcdefghijk', 20)
        loop = asyncio.get_running_loop()
        for _ in range(8):
            probe.feed(await page.evaluate(SAMPLE_JS), loop.time())
            await asyncio.sleep(.15)
        self.assertGreater(probe.played, .3)
        await page.locator('video').evaluate('(v)=>v.pause()')
        before = probe.played
        for _ in range(3):
            probe.feed(await page.evaluate(SAMPLE_JS), loop.time())
            await asyncio.sleep(.15)
        self.assertEqual(probe.played, before)
        await context.close()
