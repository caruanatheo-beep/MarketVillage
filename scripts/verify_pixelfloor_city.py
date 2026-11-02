"""Browser smoke check for the isolated PixelFloor City integration."""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.getenv("VISUAL_TEST_URL", "http://127.0.0.1:7863")
OUT = Path(__file__).resolve().parents[1] / "artifacts" / "pixelfloor_city"
OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    for width, height in [(1920, 1080), (1366, 768), (390, 844)]:
        page = context.new_page()
        page.set_viewport_size({"width": width, "height": height})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        response=page.goto(f"{BASE}/city/")
        if response and response.status==401 or "/login" in page.url:
            page.goto(f"{BASE}/login")
            page.locator("#u").fill(os.getenv("VISUAL_TEST_USER", "visualtest"))
            page.locator("#p").fill(os.getenv("VISUAL_TEST_PASSWORD", "visual-test-only-2026"))
            page.get_by_role("button", name="Se connecter").click()
            page.wait_for_url("**/city/")
        iframe = page.locator("iframe[title='PixelFloor MarketDesk City']")
        iframe.wait_for(timeout=10000)
        page.wait_for_function("""() => {
          const w=document.querySelector('iframe')?.contentWindow;
          return w?._pixelFloorInstance && Object.keys(w._pixelFloorInstance.getAgents()).length===7;
        }""", timeout=10000)
        page.wait_for_timeout(700)
        assert not errors, errors
        assert page.evaluate("document.documentElement.scrollHeight<=innerHeight && document.documentElement.scrollWidth<=innerWidth")
        page.screenshot(path=str(OUT / f"city_{width}x{height}.png"))
        if width == 1366:
            for agent_id, name in [("market_analyst","Mira"),("finance_tutor","Noé"),
                                   ("job_hunter","Jules"),("desk_manager","Desk Manager"),
                                   ("networker","Lina"),("outreach_agent","Iris"),("developer","Axel")]:
                point=page.evaluate("""id => {
                  const frame=document.querySelector('iframe');
                  const w=frame.contentWindow, c=w.document.querySelector('#office');
                  const a=w._pixelFloorInstance.getAgent(id), f=frame.getBoundingClientRect(), r=c.getBoundingClientRect();
                  return {x:f.x+r.x+(a.x+.5)*48*r.width/c.width,
                          y:f.y+r.y+(a.y+.5)*48*r.height/c.height};
                }""",agent_id)
                page.mouse.move(point["x"],point["y"])
                page.mouse.click(point["x"],point["y"])
                page.locator(".agent-panel h2").filter(has_text=name).wait_for(timeout=3000)
                page.locator(".agent-panel").get_by_role("button",name="Fermer").click()
            page.get_by_role("button",name="Missions",exact=False).first.click()
            assert page.locator(".game-mission-control").is_visible()
            page.locator(".game-mission-control").get_by_role("button",name="Fermer").click()
            workflow=page.evaluate("""async () => {
              const r=await fetch('/city/api/workflows',{method:'POST',
                headers:{'Content-Type':'application/json','X-MarketDesk-City':'1'},
                body:JSON.stringify({template:'source_review',request:'Review cached market sources',focus:'Markets',priority:1})});
              return {status:r.status,body:await r.json()};
            }""")
            assert workflow["status"]==201,workflow
            page.wait_for_function("""() => {
              const w=document.querySelector('iframe')?.contentWindow;
              const a=w?._pixelFloorInstance?.getAgent('desk_manager');
              return a?.route?.length>0 &&
                (Math.abs(a.x-a.deskX)>0.1 || Math.abs(a.y-a.deskY)>0.1);
            }""",timeout=20000)
            manager=page.evaluate("""() => {
              const a=document.querySelector('iframe').contentWindow._pixelFloorInstance.getAgent('desk_manager');
              return {x:a.x,y:a.y,route:a.route.length};
            }""")
            assert manager["route"]>0,manager
            page.screenshot(path=str(OUT / "city_workflow_handoff.png"))
            workflow_id=workflow["body"]["workflow"]["id"]
            page.wait_for_function("""async id => {
              const r=await fetch('/city/api/state');
              const s=await r.json();
              return s.workflows.find(w=>w.id===id)?.status==='completed';
            }""",arg=workflow_id,timeout=20000)
            print("workflow completed",workflow_id,"manager route",manager["route"])
        print(width, height, "7 original sprites, no scroll, no script errors")
        page.close()
    browser.close()
