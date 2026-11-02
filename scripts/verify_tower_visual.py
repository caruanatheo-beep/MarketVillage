"""Browser checks against the isolated :7878 preview, with explicit test data.

Never launches collections, sends messages, or calls an LLM.
"""
import asyncio
import json
import re
import os
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parents[1] / 'artifacts'
OFFERS = [dict(company=f'Entreprise de test {letter}', title=f'Stage Assistant Sales Fixed Income et produits structures - validation {letter}',
               location='Paris — fixture locale', url=f'https://example.invalid/test-{letter}',
               kind='Stage', source='Fixture locale') for letter in ['A', 'B']]


async def main():
    OUT.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for width, height, dpr in [(1920, 1080, 1), (1366, 768, 1), (1366, 768, 2)]:
            page = await browser.new_page(viewport=dict(width=width, height=height), device_scale_factor=dpr)
            errors = []
            failed_assets = []
            loaded_assets = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: (
                failed_assets.append(response.url) if response.status >= 400 else loaded_assets.append(response.url)
            ) if '/pixel-assets/' in response.url else None)
            # Inspect the actual cached floor surface, before skyline compositing.
            await page.add_init_script('''(() => {
                const create=document.createElement.bind(document);
                window.__floorSurfaces=[];
                document.createElement=function(name,...args){
                    const element=create(name,...args);
                    if(name==='canvas')window.__floorSurfaces.push(element);
                    return element;
                };
            })()''')

            async def fixture(route):
                response = await route.fetch()
                data = await response.json()
                if route.request.url.endswith('/state'):
                    data['tasks'].append(dict(id='fixture-panel-pagination', agent_id='networker',
                        status='completed', description='Validation locale des panneaux',
                        created_at='2026-11-01T12:00:00Z', result=dict(offers=OFFERS)))
                elif route.request.url.endswith('/internship-highlight'):
                    data = dict(featured_offer=OFFERS[0], total_count=2)
                elif route.request.url.endswith('/market-snapshot'):
                    data = dict(points=[dict(series_id=key, label=key, value=value, previous=previous,
                        change=value-previous, unit=unit, observed_at='2026-11-01', source='Fixture locale')
                        for key, value, previous, unit in [('SP500', 7500, 7550, 'Index'),
                            ('DGS10', 4.94, 4.98, '%'), ('DEXUSEU', 1.1166, 1.12, 'USD'),
                            ('DCOILWTICO', 104.1, 101.8, 'USD')]])
                await route.fulfill(response=response, body=json.dumps(data), content_type='application/json')

            await page.route(re.compile(r'/city/api/(state|internship-highlight|market-snapshot)$'), fixture)
            await page.goto(f"http://127.0.0.1:{os.getenv('CITY_PREVIEW_PORT', '7878')}/city/")
            canvas = page.locator('.pixelagents-game canvas')
            await canvas.wait_for()
            await page.wait_for_timeout(3500)
            assert not await page.locator('.pixelagents-error').count(), 'Office failed to load'
            assert not failed_assets, failed_assets
            for name in ['md_entry_glass', 'md_entry_jamb', 'md_slab_edge'] + [f'md_partition_{mask:02x}' for mask in range(16)]:
                assert any(f'/{name}.png' in url for url in loaded_assets), f'Missing architectural asset: {name}'
            assert not any('md_glass_corridor_' in url for url in loaded_assets), 'Obsolete stretched corridor still loaded'
            assert not any('md_corridor_pier.png' in url or 'md_glass_transom.png' in url for url in loaded_assets), 'Flat wall overlay still loaded'
            holes = await page.evaluate('''() => {
                const floor=window.__floorSurfaces.find(c=>c.width===896&&c.height===736);
                if(!floor)return ['Cached floor surface not found'];
                const ctx=floor.getContext('2d'),holes=[];
                for(const [x0,x1,y0,y1]of [[1,12,11,17],[16,31,11,17],[0,13,20,28],[16,31,20,28],
                    [33,46,20,28],[14,14,11,28],[0,46,18,19]])
                    for(let y=y0;y<=y1;y++)for(let x=x0;x<=x1;x++)
                        if(ctx.getImageData(64+x*16+8,64+y*16+8,1,1).data[3]<250)holes.push([x,y]);
                return holes;
            }''')
            assert not holes, f'Transparent floor/corridor holes: {holes}'
            box = await canvas.bounding_box()
            size = await canvas.evaluate('(c)=>({w:c.width,h:c.height})')
            cols = int(await canvas.get_attribute('data-world-cols'))
            rows = int(await canvas.get_attribute('data-world-rows'))
            view = await canvas.evaluate('(c)=>({s:+c.dataset.viewScale,x:+c.dataset.viewX,y:+c.dataset.viewY})')
            scale, ox, oy = view['s'], view['x'], view['y']

            def point(col, row, projected=False):
                x, y = ox + col * 16 * scale, oy + row * 16 * scale
                centre = ox + 24 * 16 * scale
                if projected:
                    x = centre + (x-centre) * (.72 + .28 * max(0, min(1, row/rows)))
                return dict(x=box['x'] + x * box['width'] / size['w'],
                            y=box['y'] + y * box['height'] / size['h'])

            async def hover_offer():
                await page.mouse.move(**point(42, 3.5))
                return await canvas.get_attribute('title')

            assert 'test A' in await hover_offer()
            await page.mouse.click(**point(35 + 13 - 1.48 + .44, 1.8 + 4.35))
            await page.wait_for_timeout(120)
            assert 'test B' in await hover_offer(), 'Next offer hit area is misaligned'
            await page.mouse.click(**point(35 + 13 - 2.62 + .44, 1.8 + 4.35))
            await page.wait_for_timeout(120)
            assert 'test A' in await hover_offer(), 'Previous offer hit area is misaligned'
            await canvas.focus()
            await page.keyboard.press('ArrowRight')
            await page.wait_for_timeout(120)
            await page.mouse.move(**point(41.8, 3.5))
            assert 'test B' in await canvas.get_attribute('title'), 'Keyboard paging failed'
            await page.mouse.move(**point(2, 3))
            assert 'Fixture locale' in await canvas.get_attribute('title'), 'Market metadata missing'
            await page.mouse.click(**point(3, 13.6, projected=True))
            await page.wait_for_timeout(120)
            assert await page.locator('.agent-choice.market_analyst').get_attribute('aria-pressed') == 'true', 'Projected workstation selection failed'
            await page.mouse.click(**point(24, 4, projected=True))
            await page.wait_for_timeout(120)
            assert await page.locator('.agent-choice.desk_manager').get_attribute('aria-pressed') == 'true', 'Projected penthouse selection failed'
            frame_ms = await page.evaluate("""()=>new Promise(resolve=>{
                const times=[];let last=performance.now();
                function step(now){times.push(now-last);last=now;if(times.length<30)requestAnimationFrame(step);
                    else resolve(Math.round(times.slice(1).reduce((a,b)=>a+b,0)/29));}
                requestAnimationFrame(step);
            })""")
            # Make the test context unambiguous in exported validation screenshots.
            await page.evaluate("""()=>{const tag=document.createElement('div');
                tag.textContent='APERÇU LOCAL · DONNÉES DE TEST';
                tag.style='position:fixed;bottom:8px;right:16px;background:#091726;color:#cadce8;padding:5px 9px;font:10px sans-serif;z-index:99999';
                document.body.append(tag)}""")
            await page.mouse.move(0, 0)
            suffix = '-2x' if dpr == 2 else ''
            await page.screenshot(path=str(OUT / f'tower-raised-partitions-{width}{suffix}.png'))
            assert not errors, errors
            print(f'{width}x{height} DPR {dpr}: native structure assets loaded; no floor/corridor hole; next/previous/keyboard paging; projected agent selection; no browser error; {frame_ms} ms/frame')
            await page.unroute_all(behavior='wait')
            await page.close()
        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
