"""Desktop playback lab. Run: python main.py."""
import asyncio
import logging
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QThread, Signal

from app.config import ROOT
from app.core.playback_probe import PlaybackProbe, SAMPLE_JS
from app.core.diagnostics import PlaybackDiagnostics
from app.core.view_count_monitor import read_snapshot, check_page, PageBlocked
from app.utils.logging_setup import CheckedFileHandler
import json

class Runner(QThread):
    line = Signal(str)
    progress = Signal(str)
    stats = Signal(str)
    counts_changed = Signal(dict)
    worker_changed = Signal(int, str, str)
    outcome = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.cfg = config
        self.stop_event = threading.Event()
        self.counts = dict(completed=0, failed=0, cancelled=0, active=0)
        self.baseline = None
        self.manual = config.get('manual', False)
        self.last_snapshot = config.get('last_snapshot')
        self.monitor_disabled = False
        self.cleanup_failed = False
        self.log_failed = False
        self.final_status = 'Selesai'
        self.blocked_reason = None

    def stop(self):
        self.stop_event.set()

    def halt_blocked(self, reason):
        self.blocked_reason = str(reason)
        self.monitor_disabled = True
        self.stop_event.set()
        self.log(f'Diblokir YouTube; run dihentikan, periksa halaman secara manual: {reason}')

    def log(self, message):
        if not self.log_failed:
            try:
                self.logger.info(message)
            except OSError as exc:
                self.log_failed = True
                self.stop_event.set()
                self.line.emit(f'ERROR LOG: {exc}; run dihentikan')
        self.line.emit(f'{datetime.now():%H:%M:%S} {message}')

    def run(self):
        handler = None
        try:
            folder = ROOT / 'log'
            folder.mkdir(exist_ok=True)
            path = folder / f'run_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.log'
            handler = CheckedFileHandler(path, encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
            self.logger = logging.Logger(str(path), logging.INFO)
            self.logger.addHandler(handler)
            self.log(f'Log: {path}')
            self.log(f'Konfigurasi: {self.cfg}')
            asyncio.run(self.execute())
        except Exception as exc:
            self.final_status = f'Gagal: {exc}'
            self.line.emit(f'ERROR: {exc}')
            if handler:
                try:
                    self.logger.exception('Run gagal')
                except OSError:
                    pass
        finally:
            if not self.manual:
                accounted = sum(self.counts[k] for k in ('completed', 'failed', 'cancelled'))
                self.counts['cancelled'] += max(0, self.cfg['total'] - accounted)
                self.report()
            if self.stop_event.is_set():
                self.final_status = 'Dihentikan'
            if self.blocked_reason:
                self.final_status = 'Diblokir YouTube - perlu pemeriksaan manual'
            if self.cleanup_failed or self.log_failed:
                self.final_status += ' — periksa error cleanup/log'
            self.outcome.emit(self.final_status)
            if handler:
                try:
                    handler.close()
                except OSError as exc:
                    self.line.emit(f'ERROR menutup log: {exc}')

    def report(self):
        c = self.counts
        self.progress.emit(f"Selesai {c['completed']}/{self.cfg['total']} | Gagal {c['failed']} | Dibatalkan {c['cancelled']} | Aktif {c['active']}")
        self.counts_changed.emit(dict(c, total=self.cfg['total']))

    async def close_browser(self, context, browser):
        try:
            if context:
                await asyncio.wait_for(context.close(), 8)
        except Exception as exc:
            self.cleanup_failed = True
            self.log(f'Peringatan cleanup context: {exc}')
        try:
            if browser:
                await asyncio.wait_for(browser.close(), 8)
                if browser.is_connected():
                    raise RuntimeError('Browser masih tersambung setelah close')
        except Exception as exc:
            self.stop_event.set()
            self.cleanup_failed = True
            self.log(f'Pembersihan tidak lengkap; menghentikan run: {exc}')

    async def open_browser(self, pw):
        channel = self.cfg.get('browser', 'chromium')
        options = dict(headless=False)
        if channel == 'chrome':
            options['channel'] = 'chrome'
        elif channel != 'chromium':
            raise ValueError('Pilihan browser tidak didukung')
        try:
            browser = await pw.chromium.launch(**options)
        except Exception as exc:
            if channel == 'chrome':
                raise RuntimeError('Google Chrome tidak dapat dibuka. Pastikan Chrome terpasang atau pilih Chromium bawaan.') from exc
            raise
        try:
            context = await browser.new_context(locale='en-US', accept_downloads=False)
            context.set_default_timeout(5000)
            # The first page is allowed; close unsolicited popups.
            pages = []
            def on_page(page):
                pages.append(page)
                if len(pages) > 1:
                    asyncio.create_task(page.close())
            context.on('page', on_page)
            return browser, context
        except BaseException:
            await browser.close()
            raise

    async def inspect_views(self, pw):
        browser = context = None
        self.worker_changed.emit(0, 'Monitor', 'Membaca halaman')
        try:
            async with asyncio.timeout(30):
                browser, context = await self.open_browser(pw)
                await context.add_init_script("""HTMLMediaElement.prototype.play = function(){return Promise.resolve()};
                    document.addEventListener('play', e => {if(e.target.pause) e.target.pause()}, true);""")
                page = await context.new_page()
                await page.goto(self.cfg['url'], wait_until='domcontentloaded', timeout=20000)
                await check_page(page, self.cfg['id'])
                # Wait for target metadata rather than a global load/network idle.
                await page.locator('#info-container, #count .view-count, ytd-watch-metadata #view-count').first.wait_for(state='visible', timeout=8000)
                if await page.locator('video').count():
                    await page.locator('video').first.evaluate('(v) => v.pause()')
                    if not await page.locator('video').first.evaluate('(v) => v.paused'):
                        raise RuntimeError('Tidak dapat menghentikan autoplay monitor')
                snapshot = await read_snapshot(page, self.cfg['id'])
                metadata_deadline = time.monotonic() + 8
                while snapshot['precision'] == 'unavailable' and time.monotonic() < metadata_deadline:
                    await asyncio.sleep(.5)
                    snapshot = await read_snapshot(page, self.cfg['id'])
                if snapshot['precision'] == 'unavailable':
                    self.log('Monitor metadata tidak terbaca: ' + json.dumps(snapshot, ensure_ascii=False))
                    raise RuntimeError('Angka views tidak tersedia atau format ambigu')
                value = snapshot['value']
                if self.initial_check:
                    self.baseline = value
                self.last_snapshot = snapshot
                delta = value - self.baseline if value is not None and self.baseline is not None else None
                status = ('Kenaikan teramati' if delta > 0 else 'Counter menurun' if delta < 0 else 'Belum berubah') if delta is not None else 'Selisih belum diketahui'
                self.stats.emit(f"Awal: {self.baseline if self.baseline is not None else '--'} | Terakhir: {value if value is not None else snapshot['raw']} | Selisih: {delta if delta is not None else '--'} | {status} | {snapshot['precision']} | {snapshot['checked_at']}")
                self.log('youtube_page ' + json.dumps(dict(snapshot, delta=delta, video_id=self.cfg['id']), ensure_ascii=False))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if isinstance(exc, PageBlocked):
                self.halt_blocked(exc)
            old = self.last_snapshot
            suffix = f" | Data lama: {old['raw']} ({old['checked_at']})" if old else ''
            self.stats.emit(f'Pembacaan gagal: {exc}{suffix}')
            self.log(f'Monitor gagal: {exc}')
        finally:
            self.worker_changed.emit(0, 'Monitor', 'Membersihkan')
            await self.close_browser(context, browser)
            self.worker_changed.emit(0, 'Monitor', 'Tidak aktif')

    async def session(self, pw, number):
        browser = context = None
        diagnostics = None
        sample = None
        self.counts['active'] += 1
        self.report()
        result = 'Gagal'
        failure_reason = ''
        def state(text, detail=''):
            self.worker_changed.emit(number, text, detail)
        try:
            self.log(f'Sesi {number}: mulai')
            state('Membuka')
            if self.cfg['simulation']:
                state('Simulasi', f"{self.cfg['duration']} detik")
                await asyncio.sleep(self.cfg['duration'])
            else:
                async with asyncio.timeout(self.cfg['duration'] * 3 + 120):
                    browser, context = await self.open_browser(pw)
                    self.log(f'Sesi {number}: browser={self.cfg.get("browser", "chromium")} version={browser.version}')
                    page = await context.new_page()
                    diagnostics = PlaybackDiagnostics(page)
                    playback_url = (f"https://www.youtube.com/shorts/{self.cfg['id']}" if self.cfg.get('shorts') else self.cfg['url'])
                    await page.goto(playback_url, wait_until='domcontentloaded', timeout=30000)
                    await check_page(page, self.cfg['id'])
                    state('Menunggu player')
                    video_selector = '#shorts-player:visible video, ytd-reel-video-renderer[is-active] video:visible' if self.cfg.get('shorts') else 'video'
                    video = page.locator(video_selector).first
                    await video.wait_for(timeout=20000)
                    await video.evaluate('(v) => {v.playbackRate=1; v.loop=false; return v.play()}')
                    probe = PlaybackProbe(self.cfg['id'], self.cfg['duration'], self.cfg.get('shorts', False))
                    last_state = None
                    while True:
                        sample = await asyncio.wait_for(page.evaluate(SAMPLE_JS), 5)
                        done, status = probe.feed(sample, time.monotonic())
                        state(status, f'{probe.played:.1f}/{probe.target:.1f}s | video={sample.get("id")}')
                        if status != last_state:
                            self.log(f'Sesi {number}: {status}')
                            last_state = status
                        if done:
                            self.log(f'Sesi {number}: played={probe.played:.2f} target={probe.target:.2f}')
                            break
                        await asyncio.sleep(.5)
            self.counts['completed'] += 1
            result = 'Selesai'
        except asyncio.CancelledError:
            self.counts['cancelled'] += 1
            result = 'Dibatalkan'
            raise
        except Exception as exc:
            self.counts['failed'] += 1
            failure_reason = f'{type(exc).__name__}: {exc}'
            if isinstance(exc, PageBlocked):
                self.halt_blocked(exc)
            if diagnostics:
                self.log(f'Sesi {number}: diagnostics=' + json.dumps(diagnostics.summary(), ensure_ascii=False))
            if sample:
                self.log(f'Sesi {number}: last_player_sample=' + json.dumps(sample, ensure_ascii=False))
            self.log(f'Sesi {number}: gagal ? {type(exc).__name__}: {exc}')
            state('Gagal', str(exc))
        finally:
            state(result, 'Membersihkan')
            before = self.cleanup_failed
            await self.close_browser(context, browser)
            cleanup = 'Pembersihan tidak lengkap' if self.cleanup_failed and not before else 'Context/browser ditutup'
            state(result, f'{failure_reason} | {cleanup}' if failure_reason else cleanup)
            self.log(f'Sesi {number}: {result}')
            self.counts['active'] -= 1
            self.report()

    async def workload(self, pw):
        self.initial_check = True
        if self.manual:
            self.baseline = self.cfg.get('baseline')
            self.initial_check = False
            await self.inspect_views(pw)
            return
        monitoring = self.cfg['monitor'] and not self.cfg['simulation']
        pending = list(range(1, self.cfg['total'] + 1))
        active = set()
        try:
            if monitoring:
                await self.inspect_views(pw)
            self.initial_check = False
            interval = self.cfg.get('monitor_interval', 120)
            next_check = time.monotonic() + interval
            waiting_logged = False
            while pending or active:
                finished = {t for t in active if t.done()}
                for task in finished:
                    task.result()
                active -= finished
                if self.stop_event.is_set():
                    raise asyncio.CancelledError()
                if not pending and not active:
                    break
                due = monitoring and not self.monitor_disabled and time.monotonic() >= next_check
                if due:
                    if len(active) < self.cfg['windows']:
                        self.log(f'Monitor: terlambat {time.monotonic() - next_check:.1f}s dari jadwal')
                        await self.inspect_views(pw)
                        next_check = time.monotonic() + interval
                        waiting_logged = False
                    elif not waiting_logged:
                        self.stats.emit('Menunggu slot pengecekan ? pembacaan sebelumnya tetap tersimpan di log')
                        self.log('Monitor menunggu slot')
                        waiting_logged = True
                while pending and len(active) < self.cfg['windows'] and not self.stop_event.is_set():
                    active.add(asyncio.create_task(self.session(pw, pending.pop(0))))
                await asyncio.sleep(.1)
            if monitoring and not self.monitor_disabled and not self.stop_event.is_set():
                await self.inspect_views(pw)
        finally:
            # Avoid interrupting a child for a second time during its cleanup.
            for task in active:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*active, return_exceptions=True)
            self.counts['cancelled'] += len(pending)
            self.report()
            self.log(f'Ringkasan: {self.counts}')

    async def execute(self):
        async def supervise(pw):
            if self.stop_event.is_set():
                if not self.manual:
                    self.counts['cancelled'] = self.cfg['total']
                    self.report()
                    self.log(f'Ringkasan: {self.counts}')
                return
            task = asyncio.create_task(self.workload(pw))
            # Let workload enter its try/finally before cancellation can arrive.
            await asyncio.sleep(0)
            while not task.done():
                if self.stop_event.is_set():
                    task.cancel()
                    break
                await asyncio.sleep(.1)
            await asyncio.gather(task, return_exceptions=False)
        try:
            if self.cfg['simulation']:
                await supervise(None)
            else:
                from playwright.async_api import async_playwright
                async with async_playwright() as pw:
                    if self.cfg.get('browser', 'chromium') == 'chromium' and not Path(pw.chromium.executable_path).is_file():
                        raise RuntimeError('Chromium belum terpasang. Jalankan: .venv\\Scripts\\python -m playwright install chromium')
                    await supervise(pw)
        except asyncio.CancelledError:
            self.log('Run dihentikan')
