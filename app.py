import streamlit as st
import asyncio
import os
from urllib.parse import urljoin
from playwright.async_api import async_playwright

os.makedirs("screenshots", exist_ok=True)

# ================= BUG DETECTION =================
async def detect_bugs(page):
    bugs = []
    try:
        body = await page.inner_text("body")
        body_lower = body.lower()

        if "login" not in body_lower and "error" in body_lower:
            bugs.append("Unexpected error message")

        if "404" in body:
            bugs.append("Broken page (404)")

        if len(body.strip()) < 100:
            bugs.append("Page content too small")

    except Exception as e:
        bugs.append(f"Analysis failed: {str(e)}")

    return bugs


# ================= HUMAN SCROLL =================
async def human_scroll(page):
    for _ in range(4):
        await page.mouse.wheel(0, 2500)
        await page.wait_for_timeout(800)


# ================= AI DECISION ENGINE =================
async def prioritize_elements(page):
    elements = await page.query_selector_all("a, button, input, select")

    scored = []

    for el in elements:
        try:
            text = (await el.inner_text() or "").lower()
            tag = await el.evaluate("el => el.tagName.toLowerCase()")

            score = 0

            # 🎯 AI-like scoring
            if "login" in text or "sign" in text:
                score += 10
            if "submit" in text or "next" in text:
                score += 8
            if tag == "input":
                score += 7
            if "menu" in text or "category" in text:
                score += 6
            if tag == "button":
                score += 5

            scored.append((score, el, text))

        except:
            continue

    scored.sort(reverse=True, key=lambda x: x[0])

    return [el for _, el, _ in scored[:8]]


# ================= INTERACTION =================
async def interact(page, el):
    try:
        tag = await el.evaluate("el => el.tagName.toLowerCase()")

        if tag == "input":
            await el.fill("test123")
            return "Filled input"

        elif tag == "select":
            options = await el.query_selector_all("option")
            if options:
                val = await options[0].get_attribute("value")
                await el.select_option(val)
                return "Selected dropdown"

        else:
            try:
                async with page.expect_navigation(timeout=4000):
                    await el.click()
            except:
                await el.click()

            return "Clicked element"

    except Exception as e:
        return f"Failed: {str(e)}"


# ================= TEST ELEMENTS =================
async def test_elements(page):
    actions = []
    bugs = []

    try:
        elements = await prioritize_elements(page)

        for el in elements:
            try:
                text = (await el.inner_text() or "").strip()[:40]
                prev_url = page.url

                action = await interact(page, el)

                await page.wait_for_load_state("domcontentloaded")

                if page.url == prev_url and "Clicked" in action:
                    bugs.append(f"No navigation after '{text}'")

                actions.append(f"{action}: '{text}'")

            except Exception as e:
                bugs.append(f"Interaction failed: {str(e)}")

    except:
        bugs.append("Element detection failed")

    return actions, bugs


# ================= EXTRACT LINKS =================
async def extract_links(page, base_url, visited):
    links = set()

    anchors = await page.query_selector_all("a")

    for a in anchors:
        try:
            href = await a.get_attribute("href")

            if href and "javascript" not in href:
                full_url = urljoin(base_url, href)

                if full_url.startswith("http") and full_url not in visited:
                    links.add(full_url)

        except:
            continue

    return list(links)


# ================= MAIN AGENT =================
async def explore(context, start_url, max_pages=5):
    visited = set()
    queue = [start_url]
    results = []

    while queue and len(visited) < max_pages:
        url = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)
        page = await context.new_page()

        try:
            await page.goto(url, timeout=15000, wait_until="domcontentloaded")

            await human_scroll(page)

            test_case = [
                "Page Load Validation",
                "UI Content Validation",
                "AI-driven Interaction Testing",
                "Dynamic Content Handling"
            ]

            page_bugs = await detect_bugs(page)
            actions, element_bugs = await test_elements(page)

            screenshot = f"screenshots/page_{len(visited)}.png"
            await page.screenshot(path=screenshot)

            results.append({
                "url": url,
                "test_case": test_case,
                "actions": actions,
                "bugs": page_bugs + element_bugs,
                "screenshot": screenshot
            })

            new_links = await extract_links(page, url, visited)
            queue.extend(new_links[:3])

        except Exception as e:
            results.append({
                "url": url,
                "test_case": ["Page Load"],
                "actions": [],
                "bugs": [f"Page failed: {str(e)}"],
                "screenshot": None
            })

        finally:
            await page.close()

    return results


# ================= RUN =================
async def run_agent(url):
    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0"
        )

        results = await explore(context, url)

        await browser.close()

    return results


# ================= UI =================
st.set_page_config(page_title="AI QA Agent", layout="wide")
st.title("🤖 AI QA Agent (Smart Exploration)")

url = st.text_input("🌐 Enter Website URL")

if st.button("Run Agent"):

    if not url:
        st.warning("Enter a URL")

    else:
        st.info("Running AI Agent...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(run_agent(url))

        for r in results:
            st.markdown(f"## 🌐 {r['url']}")

            for a in r["actions"]:
                st.markdown(f"- ⚡ {a}")

            if r["bugs"]:
                st.error("Issues found:")
                for b in r["bugs"]:
                    st.markdown(f"- ⚠️ {b}")
            else:
                st.success("No issues")

            if r["screenshot"]:
                st.image(r["screenshot"])

            st.divider()
