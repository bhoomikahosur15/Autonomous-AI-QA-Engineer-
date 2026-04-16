import streamlit as st
import asyncio
import os
from playwright.async_api import async_playwright

os.makedirs("screenshots", exist_ok=True)


# ================= ELEMENT EXTRACTION =================
async def get_all_elements(page):
    elements = await page.query_selector_all("a, button, input")

    valid = []

    for el in elements:
        try:
            box = await el.bounding_box()
            if not box:
                continue

            text = (await el.inner_text()).strip()

            if len(text) > 1:
                valid.append((el, text))

        except:
            continue

    return valid[:6]  # 🔥 limit for speed


# ================= SCORING =================
def score_element(text):
    text = text.lower()
    score = 0

    if any(k in text for k in ["login", "sign", "submit", "next", "buy"]):
        score += 5

    if len(text) < 20:
        score += 2

    if text:
        score += 1

    return score


# ================= LOGIN DETECTION =================
async def is_login_page(page):
    try:
        body = (await page.inner_text("body")).lower()
        return any(k in body for k in ["login", "sign in", "password"])
    except:
        return False


# ================= BUG DETECTION =================
async def detect_bugs(page, prev_url):
    bugs = []

    try:
        body = await page.inner_text("body")

        if page.url == prev_url:
            bugs.append("No navigation after action")

        if "error" in body.lower():
            bugs.append("Error message visible")

        if "404" in body:
            bugs.append("Broken page (404)")

    except Exception as e:
        bugs.append(str(e))

    return bugs


# ================= MAIN EXPLORATION =================
async def explore(context, url, max_steps=3):

    page = await context.new_page()

    try:
        await page.goto(url, timeout=10000, wait_until="domcontentloaded")
    except:
        return [{
            "step": 0,
            "action": "Page load failed",
            "bugs": ["Timeout / Bot protection"],
            "screenshot": None
        }]

    # Skip login pages
    if await is_login_page(page):
        return [{
            "step": 0,
            "action": "Login page detected",
            "bugs": ["Login required - skipping"],
            "screenshot": None
        }]

    visited = set()
    results = []

    for step in range(max_steps):

        elements = await get_all_elements(page)

        if not elements:
            break

        elements = sorted(elements, key=lambda x: score_element(x[1]), reverse=True)

        selected = None

        for el, text in elements:
            key = f"{page.url}-{text}"

            if key not in visited:
                selected = (el, text)
                visited.add(key)
                break

        if not selected:
            break

        el, text = selected
        prev_url = page.url

        try:
            # fast click with timeout
            await asyncio.wait_for(el.click(force=True), timeout=3)

            await page.wait_for_load_state("domcontentloaded")

            bugs = await detect_bugs(page, prev_url)

            filename = f"screenshots/step_{step}.png"
            await page.screenshot(path=filename)

            results.append({
                "step": step + 1,
                "action": f"click '{text[:30]}'",
                "bugs": bugs,
                "screenshot": filename
            })

        except Exception as e:
            results.append({
                "step": step + 1,
                "action": "interaction failed",
                "bugs": [str(e)],
                "screenshot": None
            })

    await page.close()
    return results


# ================= RUN AGENT =================
async def run_agent(url):
    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36"
        )

        results = await explore(context, url)

        await browser.close()

    return results


# ================= STREAMLIT UI =================
st.set_page_config(page_title="Fast AI QA Agent", layout="wide")

st.title("⚡ Fast Smart AI QA Testing Agent")

url = st.text_input("🌐 Enter Website URL")

if st.button("Run QA Agent"):

    if not url:
        st.warning("Enter a URL")
    else:
        st.info("Running fast UI exploration...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(run_agent(url))

        total = len(results)
        failed = sum(1 for r in results if r["bugs"])
        passed = total - failed

        col1, col2, col3 = st.columns(3)
        col1.metric("Passed", passed)
        col2.metric("Failed", failed)
        col3.metric("Total", total)

        st.divider()

        for r in results:
            st.markdown(f"## 🔍 Step {r['step']}")
            st.markdown(f"👉 Action: {r['action']}")

            if r["bugs"]:
                st.error("Issues found")
                for b in r["bugs"]:
                    st.markdown(f"- ⚠️ {b}")
            else:
                st.success("No issues")

            if r["screenshot"]:
                st.image(r["screenshot"])

            st.divider()
