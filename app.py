import streamlit as st
import asyncio
import os
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright

os.makedirs("screenshots", exist_ok=True)


# ================= BUG DETECTION =================
async def detect_bugs(page):
    bugs = []

    try:
        body = await page.inner_text("body")
        body_lower = body.lower()

        # Ignore login-related "error"
        if "login" not in body_lower and "error" in body_lower:
            bugs.append("Unexpected error message")

        if "404" in body:
            bugs.append("Broken page (404)")

        if len(body.strip()) < 80:
            bugs.append("Page content too small")

    except Exception as e:
        bugs.append(f"Analysis failed: {str(e)}")

    return bugs


# ================= ELEMENT TESTING =================
async def test_elements(page):
    actions = []
    bugs = []

    try:
        elements = await page.query_selector_all("a, button")

        for el in elements[:2]:  # limit for speed
            try:
                text = (await el.inner_text()).strip()
                prev_url = page.url

                await el.click(timeout=3000)
                await page.wait_for_load_state("domcontentloaded")

                if page.url == prev_url:
                    bugs.append(f"No navigation after clicking '{text}'")

                actions.append(f"Clicked '{text}'")

            except Exception as e:
                bugs.append(f"Interaction failed: {str(e)}")

    except:
        bugs.append("Element detection failed")

    return actions, bugs


# ================= LINK VALIDATION =================
def is_valid_link(base_url, link):
    if not link:
        return False

    base = urlparse(base_url)
    target = urlparse(link)

    return (
        target.scheme in ["http", "https"]
        and base.netloc == target.netloc
    )


# ================= MAIN AGENT =================
async def explore(context, start_url, max_pages=3):

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

            # 🧠 TEST CASE DESCRIPTION
            test_case = [
                "Page Load Validation",
                "UI Content Validation",
                "Element Interaction Testing"
            ]

            # 🔍 Page-level bugs
            page_bugs = await detect_bugs(page)

            # 🖱 Element-level testing
            actions, element_bugs = await test_elements(page)

            all_bugs = page_bugs + element_bugs

            screenshot = f"screenshots/page_{len(visited)}.png"
            await page.screenshot(path=screenshot)

            results.append({
                "url": url,
                "test_case": test_case,
                "actions": actions,
                "bugs": all_bugs,
                "screenshot": screenshot
            })

            # 🔗 Extract links
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
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        context = await browser.new_context()

        results = await explore(context, url)

        await browser.close()

    return results


# ================= UI =================
st.set_page_config(page_title="AI QA Agent", layout="wide")

st.title("🤖 Smart AI QA Testing Agent")

url = st.text_input("🌐 Enter Website URL")

if st.button("Run QA Agent"):

    if not url:
        st.warning("Please enter a URL")

    else:
        st.info("Running combined UI + interaction testing...")

        try:
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

                # 🧠 Test case description
                st.markdown("### 🧪 Test Case:")
                for t in r["test_case"]:
                    st.markdown(f"- {t}")

                # 🖱 Actions
                if r["actions"]:
                    st.markdown("### ⚡ Actions Performed:")
                    for a in r["actions"]:
                        st.markdown(f"- {a}")

                # 🚨 Bugs
                if r["bugs"]:
                    st.error(f"{len(r['bugs'])} issue(s) found")
                    for b in r["bugs"]:
                        st.markdown(f"- ⚠️ {b}")
                else:
                    st.success("No issues")

                if r["screenshot"]:
                    st.image(r["screenshot"])

                st.divider()

        except Exception as e:
            st.error(f"App crashed: {str(e)}")
