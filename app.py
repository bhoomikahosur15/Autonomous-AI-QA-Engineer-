import streamlit as st
import asyncio
import os
from urllib.parse import urljoin
from playwright.async_api import async_playwright

os.makedirs("screenshots", exist_ok=True)

# ================= MANUAL STEALTH =================
async def apply_stealth(page):
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });

        window.chrome = { runtime: {} };

        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });

        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
    """)

# ================= BUG DETECTION =================
async def detect_bugs(page):
    bugs = []
    try:
        body = await page.inner_text("body")
        body_lower = body.lower()

        if "something went wrong" in body_lower:
            bugs.append("Page crashed / blocked")

        if "404" in body:
            bugs.append("Broken page (404)")

    except Exception as e:
        bugs.append(f"Analysis failed: {str(e)}")

    return bugs

# ================= HUMAN SCROLL =================
async def human_scroll(page):
    for _ in range(3):
        await page.mouse.wheel(0, 2000)
        await page.wait_for_timeout(700)

# ================= AI PRIORITIZATION =================
async def prioritize_elements(page):
    elements = await page.query_selector_all("a, button, input, select")
    scored = []

    for el in elements:
        try:
            text = (await el.inner_text() or "").lower()
            tag = await el.evaluate("el => el.tagName.toLowerCase()")

            score = 0
            if "login" in text or "sign" in text:
                score += 10
            if "next" in text or "submit" in text:
                score += 8
            if tag == "input":
                score += 7
            if tag == "button":
                score += 5

            scored.append((score, el, text))

        except:
            continue

    scored.sort(reverse=True, key=lambda x: x[0])
    return [el for _, el, _ in scored[:6]]

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

# ================= ELEMENT TESTING =================
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

# ================= LINK EXTRACTION =================
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
async def explore(context, start_url, max_pages=4):
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
            await apply_stealth(page)   # 🔥 manual stealth
            await page.goto(url, timeout=20000)

            await human_scroll(page)

            test_case = [
                "Page Load Validation",
                "UI Interaction Testing",
                "Dynamic Content Handling",
                "AI-based Exploration"
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
            queue.extend(new_links[:2])

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
            headless=True,   # Render safe
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            viewport={"width": 1280, "height": 800}
        )

        results = await explore(context, url)

        await browser.close()
    return results

# ================= UI =================
st.set_page_config(page_title="AI QA Agent", layout="wide")
st.title("🤖 Autonomous AI QA Agent")

url = st.text_input("🌐 Enter Website URL")

if st.button("Run Agent"):

    if not url:
        st.warning("Enter a URL")

    else:
        st.info("Running agent...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(run_agent(url))

        for i, r in enumerate(results):
            st.markdown(f"## 🌐 Page {i+1}")
            st.markdown(f"🔗 {r['url']}")

            st.markdown("### 🧪 Test Cases:")
            for t in r["test_case"]:
                st.markdown(f"- {t}")

            if r["actions"]:
                st.markdown("### ⚡ Actions:")
                for a in r["actions"]:
                    st.markdown(f"- {a}")

            if r["bugs"]:
                st.error(f"{len(r['bugs'])} issue(s)")
                for b in r["bugs"]:
                    st.markdown(f"- ⚠️ {b}")
            else:
                st.success("No issues")

            if r["screenshot"]:
                st.image(r["screenshot"])

            st.divider()
