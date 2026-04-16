import streamlit as st
import asyncio
import os
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright

os.makedirs("screenshots", exist_ok=True)


# ================= BUG DETECTION =================
async def detect_bugs(page, prev_url):
    bugs = []

    try:
        body = await page.inner_text("body")

        if "error" in body.lower():
            bugs.append("Error message visible")

        if "404" in body:
            bugs.append("Broken page (404)")

        if len(body.strip()) < 80:
            bugs.append("Page content too small")

    except Exception as e:
        bugs.append(f"Page analysis failed: {str(e)}")

    return bugs


# ================= GET INTERNAL LINKS =================
def is_valid_link(base, link):
    if not link:
        return False

    parsed_base = urlparse(base)
    parsed_link = urlparse(link)

    return (
        parsed_link.scheme in ["http", "https"] and
        parsed_base.netloc == parsed_link.netloc
    )


# ================= MULTI-PAGE EXPLORATION =================
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
            await page.goto(url, timeout=10000, wait_until="domcontentloaded")
        except:
            await page.close()
            continue

        # Detect bugs
        bugs = await detect_bugs(page, url)

        # Screenshot
        screenshot = f"screenshots/page_{len(visited)}.png"
        await page.screenshot(path=screenshot)

        results.append({
            "url": url,
            "bugs": bugs,
            "screenshot": screenshot
        })

        # Extract links
        try:
            anchors = await page.query_selector_all("a")

            for a in anchors:
                try:
                    href = await a.get_attribute("href")

                    if not href:
                        continue

                    full_url = urljoin(url, href)

                    if is_valid_link(start_url, full_url) and full_url not in visited:
                        queue.append(full_url)

                except:
                    continue

        except:
            pass

        await page.close()

    return results


# ================= RUN AGENT =================
async def run_agent(url):
    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        context = await browser.new_context()

        results = await explore(context, url)

        await browser.close()

    return results


# ================= STREAMLIT UI =================
st.set_page_config(page_title="AI QA Agent", layout="wide")

st.title("🤖 Multi-Page AI QA Testing Agent")

url = st.text_input("🌐 Enter Website URL")

if st.button("Run QA Agent"):

    if not url:
        st.warning("Please enter a URL")
    else:
        st.info("Exploring multiple pages...")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(run_agent(url))

        total = len(results)
        failed = sum(1 for r in results if r["bugs"])
        passed = total - failed

        col1, col2, col3 = st.columns(3)
        col1.metric("Passed", passed)
        col2.metric("Failed", failed)
        col3.metric("Pages Tested", total)

        st.divider()

        for i, r in enumerate(results):
            st.markdown(f"## 🌐 Page {i+1}")
            st.markdown(f"🔗 {r['url']}")

            if r["bugs"]:
                st.error("Issues found")
                for b in r["bugs"]:
                    st.markdown(f"- ⚠️ {b}")
            else:
                st.success("No issues")

            if r["screenshot"]:
                st.image(r["screenshot"])

            st.divider()
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
