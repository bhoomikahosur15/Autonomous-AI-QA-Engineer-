
import streamlit as st
import asyncio
import os
from playwright.async_api import async_playwright

os.makedirs("screenshots", exist_ok=True)


# ================= GET ELEMENTS (FAST) =================
async def get_all_elements(page):
    elements = await page.query_selector_all("a, button, input")
    valid = []

    for el in elements[:20]:   # ✅ small cap for speed
        try:
            if not await el.is_visible():
                continue

            tag = await el.evaluate("(e) => e.tagName")

            if tag == "INPUT":
                text = "input"
            else:
                text = (await el.inner_text() or "").strip()

            if text or tag == "INPUT":
                valid.append((el, tag, text))

        except:
            continue

    return valid


# ================= SIMPLE PRIORITY =================
def score_element(tag, text):
    text = text.lower()

    if "login" in text or "sign" in text:
        return 5
    if tag == "INPUT":
        return 4
    return 1


# ================= FAST BUG CHECK =================
async def detect_bugs(page, prev_url):
    bugs = []

    try:
        if page.url == prev_url:
            bugs.append("No navigation")

        title = await page.title()

        if "error" in title.lower():
            bugs.append("Error page")

    except:
        bugs.append("Check failed")

    return bugs


# ================= CORE =================
async def explore(browser, url, max_steps=5):   # ✅ reduced steps
    page = await browser.new_page()

    try:
        # ✅ FAST LOAD
        await page.goto(url, timeout=30000, wait_until="domcontentloaded")
    except:
        return [{"step": 1, "action": "Page failed to load", "test_case": {"status": "Failed", "bugs": ["Timeout"]}, "screenshot": None}]

    visited = set()
    results = []

    for step in range(max_steps):

        elements = await get_all_elements(page)

        if not elements:
            break

        elements = sorted(
            [(score_element(tag, text), el, tag, text) for el, tag, text in elements],
            reverse=True
        )

        selected = None

        for _, el, tag, text in elements:
            key = f"{page.url}-{text}"

            if key not in visited:
                selected = (el, tag, text)
                visited.add(key)
                break

        if not selected:
            break

        el, tag, text = selected
        prev_url = page.url

        try:
            if tag == "INPUT":
                await el.fill("test")
                action = "fill input"
            else:
                await el.click()
                action = f"click {text[:20]}"

            # ✅ SMALL WAIT (FAST)
            await page.wait_for_timeout(1500)

            bugs = await detect_bugs(page, prev_url)

        except Exception as e:
            bugs = [str(e)]
            action = "failed"

        results.append({
            "step": step + 1,
            "action": action,
            "test_case": {
                "title": action,
                "status": "Failed" if bugs else "Passed",
                "bugs": bugs
            },
            "screenshot": None
        })

    await page.close()
    return results


# ================= RUN =================
async def run_agent(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        results = await explore(browser, url)

        await browser.close()

    return results


# ================= UI =================
st.set_page_config(page_title="AI QA Agent", layout="wide")

st.title("⚡ Fast AI QA Agent")

url = st.text_input("Enter URL")

if st.button("Run"):

    if not url:
        st.warning("Enter URL")
    else:
        st.info("Running fast test...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(run_agent(url))

        total = len(results)
        failed = sum(1 for r in results if r["test_case"]["status"] == "Failed")

        st.metric("Total", total)
        st.metric("Failed", failed)

        for r in results:
            st.markdown(f"### Step {r['step']}")
            st.write("Action:", r["action"])

            if r["test_case"]["status"] == "Passed":
                st.success("Passed")
            else:
                st.error("Failed")

            for b in r["test_case"]["bugs"]:
                st.write("-", b)
