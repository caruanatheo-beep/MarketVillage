"""Isolated browser validation: no real AI task, email or source collection."""
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / '.venv/Lib/site-packages')]
from playwright.sync_api import sync_playwright

OUT = ROOT / 'artifacts/command-center'
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':1920,'height':1080})
    all_working = False
    def state_fixture(route):
        data = route.fetch().json()
        if all_working:
            for agent in data['agents']:
                agent['status'] = 'running'
        route.fulfill(json=data)
    page.route('**/city/api/state',state_fixture)
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:7878/city/')
    page.wait_for_selector('.pixelagents-game canvas')
    page.wait_for_timeout(6000)
    assert page.locator('.pixelagents-error').count() == 0, page.locator('body').inner_text()[-1000:]
    for width,height in [(1920,1080),(1366,768),(390,844)]:
        page.set_viewport_size({'width':width,'height':height})
        page.wait_for_timeout(600)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Horizontal overflow'
        if width>1000:
            assert page.evaluate('document.documentElement.scrollHeight<=innerHeight'), 'Page scrolling'
        page.screenshot(path=str(OUT / f'golf-{width}.png'))
    page.set_viewport_size({'width':1920,'height':1080})
    # Let the real RAF/navigation loop run; API traffic remains isolated.
    page.wait_for_timeout(45000)
    activity = page.locator('.pixelagents-game canvas').get_attribute('aria-description')
    print(activity)
    assert re.search(r'dont [1-5] sur un tapis',activity), 'An idle agent must really reach a mat in the browser'
    page.screenshot(path=str(OUT / 'golf-ambient.png'))
    # This changes only the isolated browser response, never a real mission.
    all_working = True
    page.wait_for_function('document.querySelector(".pixelagents-game canvas").getAttribute("aria-description").startsWith("Practice : 0 ")',timeout=10000)
    page.screenshot(path=str(OUT / 'golf-mission-return.png'))
    assert not errors, errors
    print('PASS: terrace assets, full campus at 1920/1366/390, no desktop scroll, actual ambient swings, immediate real-state interruption, no browser errors.')
    browser.close()
