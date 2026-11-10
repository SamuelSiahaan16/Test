"""Read public page metadata; never infer exact values from abbreviations."""
import re
from datetime import datetime


def parse_snapshot(raw, locale='en-US'):
    raw = ' '.join(raw.split())
    unit = r'(?:views?|tayangan|(?:kali |x )?ditonton|penayangan)'
    match = re.search(r'(?<![\w.,])([0-9][0-9.,\s\u00a0]*?(?:\s*(?:rb|jt|miliar|[KMB]))?)\s+' + unit + r'\b', raw, re.I)
    result = dict(raw=raw, locale=locale, precision='unavailable', value=None,
                  checked_at=datetime.now().astimezone().isoformat(timespec='seconds'))
    if not match:
        return result
    number = match[1].strip()
    if re.search(r'[a-z]', number, re.I):
        result['precision'] = 'abbreviated'
        return result
    separator = '.' if locale.lower().startswith('id') else ','
    if re.fullmatch(r'\d+|\d{1,3}(?:' + re.escape(separator) + r'\d{3})+', number):
        result.update(value=int(number.replace(separator, '')), precision='exact')
    return result


class PageBlocked(RuntimeError):
    pass


async def check_page(page, expected_id):
    from app.utils.validators import video_id
    try:
        if video_id(page.url) != expected_id:
            raise ValueError()
    except ValueError:
        raise PageBlocked('Halaman berpindah / consent / login; URL video tidak sesuai')
    for selector in ('#error-screen', 'ytd-enforcement-message-view-model', 'form[action*="/sorry/"]'):
        element = page.locator(selector).first
        if await element.is_visible():
            reason = (await element.inner_text())[:200]
            raise PageBlocked(reason or 'Video dibatasi atau tidak tersedia')


async def read_snapshot(page, expected_id):
    await check_page(page, expected_id)
    locale = await page.locator('html').get_attribute('lang') or 'en-US'
    selectors = ('#description-inline-expander #info-container',
                 '#description #info-container', '#info-container',
                 'ytd-watch-metadata #view-count', '#count .view-count')
    best = parse_snapshot('', locale)
    for expanded in (False, True):
        for selector in selectors:
            locator = page.locator(selector).first
            if not await locator.is_visible():
                continue
            for raw in (await locator.inner_text(), await locator.get_attribute('title') or ''):
                result = parse_snapshot(raw, locale)
                result['selector'] = selector
                if result['raw'] and best['precision'] == 'unavailable':
                    best = result
                if result['precision'] == 'exact':
                    return result
                if result['precision'] == 'abbreviated':
                    best = result
            # Hover can expose a complete count through the element's title.
            await locator.hover(timeout=1500)
            result = parse_snapshot(await locator.get_attribute('title') or '', locale)
            if result['precision'] == 'exact':
                result['selector'] = selector + '[title]'
                return result
        if not expanded:
            more = page.locator('#description-inline-expander #expand').first
            if await more.is_visible():
                await more.click(timeout=1500)
    return best
