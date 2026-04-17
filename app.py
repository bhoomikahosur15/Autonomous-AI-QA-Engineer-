import streamlit as st
import asyncio
import os
from urllib.parse import urljoin
from playwright.async_api import async_playwright

# ================= CONFIG ================
MAX_PAGES = 2
MAX_ELEMENTS = 10

# ================= PRIORITIZATION =================
async def prioritize_elements(page):
    elements = await page.query_selector_all("a, button, input")

    scored = []

    for el in elements:
        try:
            text = (await el.inner_text() or "").lower()

            score = 0

            # 🔥 Smart scoring
            if any(k in text for k in ["login", "sign", "submit"]):
                score += 5
            if "button" in await el.get_attribute("class") or "":
                score += 2
            if len(text) > 0:
                score += 1

            scored.append((score, el))

        except:
            continue

    scored.sort(reverse=True, key=lambda x: x[0])

    return [el for _, el in scored[:MAX_ELEMENTS]]


# ================= BUG DETECTION =================
async def detect_bugs(page):
    bugs = []
    try:
        body = await page.inner_text("body")
        body_lower = body.lower()

        if "something went wrong" in body_lower:
            bugs.append("Page crashed")

        if "404" in body:
            bugs.append("Broken page")

        if len(body.strip()) < 50:
            bugs.append("Empty UI")

    except Exception as e:
        bugs.append(str(e))

    return bugs


# ================= INTERACTION =================
async def interact(page, el):
    try:
        tag = await el.evaluate("el => el.tagName.toLowerCase()")

        prev_url = page.url
        prev_dom = await page.evaluate("document.body.innerText.length")

        api_called = {"value": False}

        def handle_request(req):
            if req.resource_type in ["xhr", "fetch"]:
                api_called["value"] = True

        page.on("request", handle_request)

        # INPUT
        if tag == "input":
            await el.fill("test123")
            page.remove_listener("request", handle_request)
            return ("Fill input", "PASS", "Input working")

        # CLICK
        try:
            async with page.expect_navigation(timeout=2000):
                await el.click()
        except:
            await el.click()

        await page.wait_for_timeout(800)

        new_url = page.url
        new_dom = await page.evaluate("document.body.innerText.length")

        page.remove_listener("request", handle_request)

        # 🔥 Smart detection
        if new_url != prev_url:
            return ("Click", "PASS", "Navigation")

        elif api_called["value"]:
            return ("Click", "PASS", "API triggered")

        elif new_dom != prev_dom:
            return ("Click", "PASS", "UI updated")

        else:
            return ("Click", "FAIL", "No effect")

    except Exception as e:
        return ("Interaction", "FAIL", str(e))


# ================= TEST ELEMENTS =================
async def test_elements(page):
    results = []

    elements = await prioritize_elements(page)

    for el in elements:
        try:
            text = (await el.inner_text() or "").strip()[:30]

            action, status, reason = await interact(page, el)

            results.append({
                "action": f"{action} '{text}'",
                "status": status,
                "reason": reason
            })

        except Exception as e:
            results.append({
                "action": "Element",
                "status": "FAIL",
                "reason": str(e)
            })

    return results


# ================= LINKS =================
async def extract_links(page, base_url, visited):
    links = set()

    anchors = await page.query_selector_all("a")

    for a in anchors:
        try:
            href = await a.get_attribute("href")
            if href:
                full = urljoin(base_url, href)
                if full.startswith("http") and full not in visited:
                    links.add(full)
        except:
            continue

    return list(links)


# ================= MAIN =================
async def explore(context, url):
    visited = set()
    queue = [url]
    results = []

    while queue and len(visited) < MAX_PAGES:
        current = queue.pop(0)

        if current in visited:
            continue

        visited.add(current)
        page = await context.new_page()

        try:
            await page.goto(current, timeout=30000, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)

            bugs = await detect_bugs(page)
            actions = await test_elements(page)

            results.append({
                "url": current,
                "actions": actions,
                "bugs": bugs
            })

            new_links = await extract_links(page, current, visited)
            queue.extend(new_links[:1])

        except Exception as e:
            results.append({
                "url": current,
                "actions": [],
                "bugs": [str(e)]
            })

        finally:
            await page.close()

    return results


# ================= RUN =================
async def run_agent(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context()

        results = await explore(context, url)

        await browser.close()

    return results


# ================= UI =================
st.title("🤖 Smart AI QA Agent")

url = st.text_input("Enter URL")

if st.button("Run"):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    results = loop.run_until_complete(run_agent(url))

    for r in results:
        st.subheader(r["url"])

        for a in r["actions"]:
            if a["status"] == "PASS":
                st.success(f"{a['action']} → {a['reason']}")
            else:
                st.error(f"{a['action']} → {a['reason']}")

        if r["bugs"]:
            for b in r["bugs"]:
                st.error(b)
        else:
            st.success("No issues")
