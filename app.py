import streamlit as st
import asyncio
import os
from playwright.async_api import async_playwright

os.makedirs("screenshots", exist_ok=True)


# ================= GET ALL INTERACTIVE ELEMENTS =================
async def get_all_elements(page):
    elements = await page.query_selector_all("*")

    valid = []

    for el in elements:
        try:
            visible = await el.is_visible()
            if not visible:
                continue

            tag = await el.evaluate("(e) => e.tagName")
            text = (await el.inner_text()).strip() if tag != "INPUT" else "input field"

            if text or tag == "INPUT":
                valid.append((el, tag, text))

        except:
            continue

    return valid[:15]  # limit for speed


# ================= SMART PRIORITY =================
def score_element(tag, text):
    text = text.lower()

    score = 0

    if any(k in text for k in ["login", "sign", "submit", "next", "buy"]):
        score += 5

    if tag == "INPUT":
        score += 4

    if any(k in text for k in ["menu", "home", "product"]):
        score += 3

    if text:
        score += 1

    return score


# ================= BUG DETECTION =================
async def detect_bugs(page, prev_url):
    bugs = []

    try:
        body = await page.inner_text("body")

        if page.url == prev_url:
            bugs.append("No navigation or state change after action")

        if "error" in body.lower():
            bugs.append("Error message visible")

        if "404" in body:
            bugs.append("Broken link (404)")

        if len(body.strip()) < 50:
            bugs.append("Page appears empty")

    except:
        bugs.append("Page analysis failed")

    return bugs


# ================= TEST CASE =================
def create_test_case(action, bugs):
    return {
        "title": f"Verify {action}",
        "status": "Failed" if bugs else "Passed",
        "bugs": bugs
    }


# ================= MAIN EXPLORATION =================
async def explore(browser, url, max_steps=10):
    page = await browser.new_page()
    await page.goto(url)

    visited_actions = set()
    results = []

    for step in range(max_steps):

        elements = await get_all_elements(page)

        if not elements:
            break

        # 🔥 prioritize elements
        scored = sorted(
            [(score_element(tag, text), el, tag, text) for el, tag, text in elements],
            reverse=True,
            key=lambda x: x[0]
        )

        selected = None

        for score, el, tag, text in scored:
            action_id = f"{page.url}-{text}"

            if action_id not in visited_actions:
                selected = (el, tag, text)
                visited_actions.add(action_id)
                break

        if not selected:
            break

        el, tag, text = selected

        prev_url = page.url

        try:
            if tag == "INPUT":
                await el.fill("test123")
                action = f"enter input in field"

            else:
                await el.click(timeout=3000)
                action = f"click '{text[:30]}'"

            await page.wait_for_load_state("domcontentloaded")

            bugs = await detect_bugs(page, prev_url)

            screenshot = None
            if bugs:
                filename = f"screenshots/step_{step}.png"
                await page.screenshot(path=filename)
                screenshot = filename

            results.append({
                "step": step + 1,
                "action": action,
                "test_case": create_test_case(action, bugs),
                "screenshot": screenshot
            })

        except Exception as e:
            results.append({
                "step": step + 1,
                "action": "interaction failed",
                "test_case": {
                    "title": "Interaction Test",
                    "status": "Failed",
                    "bugs": [str(e)]
                },
                "screenshot": None
            })

    await page.close()
    return results


# ================= RUN AGENT =================
async def run_agent(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        results = await explore(browser, url)

        await browser.close()

    return results


# ================= UI =================
st.set_page_config(page_title="AI QA Agent", layout="wide")

st.title("AI QA Testing Agent")


url = st.text_input("🌐 Enter Website URL")

if st.button("Run QA Agent"):

    if not url:
        st.warning("Enter URL")
    else:
        st.info("Exploring UI and detecting issues...")

        results = asyncio.run(run_agent(url))

        total = len(results)
        failed = sum(1 for r in results if r["test_case"]["status"] == "Failed")
        passed = total - failed

        col1, col2, col3 = st.columns(3)
        col1.metric("Passed", passed)
        col2.metric("Failed", failed)
        col3.metric("Total Tests", total)

        st.divider()

        for r in results:
            st.markdown(f"## 🔍 Step {r['step']}")

            st.markdown(f"👉 Action: {r['action']}")

            tc = r["test_case"]

            if tc["status"] == "Passed":
                st.success("Test Passed")
            else:
                st.error("Test Failed")

            st.markdown(f"📋 Test Case: {tc['title']}")

            if tc["bugs"]:
                st.markdown("⚠️ Bugs Found:")
                for b in tc["bugs"]:
                    st.markdown(f"- {b}")

            if r["screenshot"]:
                st.image(r["screenshot"])

            st.divider()
