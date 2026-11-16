import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.venv/Lib/site-packages'))
from playwright.sync_api import sync_playwright

out = ROOT / 'artifacts/command-center'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':1920,'height':1080}, device_scale_factor=1)
    errors=[]
    page.on('pageerror', lambda e: errors.append(str(e)))
    points=[{'series_id':key,'label':key,'value':v,'previous':prev,'change':v-prev,'observed_at':'2026-11-01','unit':''} for key,v,prev in [('SP500',7580.1,7620),('DGS10',4.94,4.98),('DEXUSEU',1.1166,1.12),('DCOILWTICO',104.1,102)]]
    page.route('**/city/api/market-snapshot', lambda r:r.fulfill(json={'points':points}))
    page.route('**/city/api/internship-highlight', lambda r:r.fulfill(json={'featured_offer':{'title':'Stage - Assistant Sales Fixed Income et produits structures internationaux','company':'Banque de demonstration','location':'Paris, France','url':'https://example.com/job'},'total_count':1}))
    page.goto('http://127.0.0.1:7878/city/')
    page.wait_for_selector('.console-overview')
    page.wait_for_timeout(1800)
    assert page.locator('.level-card').count()==0
    assert not page.get_by_text('Chargement du bureau impossible',exact=False).count()
    for w,h in [(1920,1080),(1366,768)]:
        page.set_viewport_size({'width':w,'height':h})
        page.wait_for_timeout(600)
        page.screenshot(path=str(out/f'console-{w}.png'))
        print(w, page.locator('.command-console').evaluate('(el)=>({width:el.clientWidth,scrollWidth:el.scrollWidth,height:el.clientHeight,scrollHeight:el.scrollHeight})'))
        send=page.get_by_role('button',name='Envoyer',exact=True).bounding_box()
        assert send and send['y']+send['height']<=h, send
    page.locator('.overview-task').first.click()
    page.wait_for_timeout(300)
    assert page.get_by_text('Registre des missions',exact=True).is_visible()
    assert page.locator('.level-card').count()==0
    page.get_by_role('button',name='Chat',exact=True).click()
    page.locator('.overview-event').first.click()
    page.wait_for_timeout(300)
    assert page.locator('.mission-results-window').count()
    print('PASS: overview navigation, result opening, no levels, composer visible; errors:',errors)
    assert not errors
    browser.close()
