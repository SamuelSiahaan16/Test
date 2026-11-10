"""Pure playback accounting, separately testable without network access."""
from app.utils.validators import short_target, ended_success

SAMPLE_JS = """() => {
 const shorts=location.pathname.startsWith('/shorts/');
 const visible=e=>!!e && !!e.getClientRects().length && getComputedStyle(e).visibility!=='hidden';
 const shortsPlayer=[...document.querySelectorAll('#shorts-player')].find(visible);
 const scope=shorts ? (shortsPlayer || document.querySelector('ytd-reel-video-renderer[is-active]')) : document;
 const v=scope?.querySelector('video'), p=scope?.matches?.('.html5-video-player') ? scope : scope?.querySelector('#movie_player, .html5-video-player');
 const d=p?.getVideoData?.();
 const errorNode=[...(scope?.querySelectorAll('.ytp-error-content-wrap, .ytp-error-content, ytd-player-error-message-renderer, #error-screen') || [])]
   .find(e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden' && e.innerText.trim());
 return {id:d?.video_id || null, t:v?.currentTime || 0, paused:v?.paused ?? true,
 ready:v?.readyState || 0, ended:v?.ended || false, duration:v?.duration || null,
 error:!!v?.error, error_message:errorNode?.innerText?.trim().slice(0,500) || null,
 media_error_code:v?.error?.code || null, ad:!!p?.classList.contains('ad-showing'),
 live:!!d?.isLive, seeking:v?.seeking || false,
 frames:v?.getVideoPlaybackQuality?.().totalVideoFrames ?? null};
}"""


class PlaybackProbe:
    def __init__(self, ident, requested, shorts=False):
        self.ident, self.requested, self.shorts = ident, requested, shorts
        self.played = 0.0
        self.previous = None
        self.stamp = None
        self.frames = None
        self.target = requested

    def feed(self, sample, now):
        if sample.get('error_message'):
            raise RuntimeError('YouTube player: ' + sample['error_message'])
        if sample.get('error'):
            raise RuntimeError(f"Player media error (code={sample.get('media_error_code')})")
        matches = sample.get('id') == self.ident and not sample.get('ad')
        if matches and sample.get('live'):
            raise RuntimeError('Live stream belum didukung')
        if matches:
            self.target = short_target(self.requested, sample.get('duration'), self.shorts)
        valid = matches and not sample.get('seeking') and (not sample.get('paused') or sample.get('ended')) and sample.get('ready', 0) >= 2
        status = 'Belum terverifikasi'
        if sample.get('ad'):
            status = 'Iklan — tidak dihitung'
        elif matches:
            status = 'Pause' if sample.get('paused') else 'Buffering'
        if valid and self.previous is not None and self.stamp is not None:
            advance, elapsed = sample['t'] - self.previous, now - self.stamp
            frames = sample.get('frames')
            frame_ok = frames is None or self.frames is None or frames > self.frames or sample.get('ended')
            if 0 < advance <= elapsed * 1.5 + .2 and frame_ok:
                self.played += min(advance, elapsed)
                status = 'Memutar terverifikasi'
        self.previous = sample.get('t') if valid else None
        self.frames = sample.get('frames') if valid else None
        self.stamp = now
        done = matches and (self.played >= self.target or (sample.get('ended') and ended_success(self.played, self.target)))
        if matches and sample.get('ended') and not done:
            raise RuntimeError('Video berakhir sebelum durasi terverifikasi terpenuhi')
        return done, status
