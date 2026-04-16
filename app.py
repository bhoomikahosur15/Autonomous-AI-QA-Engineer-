import streamlit as st
import asyncio
import os
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright

# Create screenshots folder
os.makedirs("screenshots", exist_ok=True)


# ================= BUG DETECTION =================
async def detect_bugs(page):
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
        bugs.append(f"Analysis failed: {str(e)}")

    return bugs


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
            # Load page
            await page.goto(url, timeout=10000, wait_until="domcontentloaded")

            # Detect bugs
            bugs = await detect_bugs(page)

            # Screenshot
            screenshot_path = f"screenshots/page_{len(visited)}.png"
            await page.screenshot(path=screenshot_path)

            results.append({
                "url": url,
                "bugs": bugs,
                "screenshot": screenshot_path
            })

            # Extract links
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
                "bugs": [f"Page failed: {str(e)}"],
                "screenshot": None
            })

        finally:
            await page.close()

    return results


# ================= RUN AGENT =================
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


# ================= STREAMLIT UI =================
st.set_page_config(page_title="AI QA Agent", layout="wide")

st.title("🤖 Multi-Page AI QA Testing Agent")

url = st.text_input("🌐 Enter Website URL")

if st.button("Run QA Agent"):

    if not url:
        st.warning("Please enter a URL")

    else:
        st.info("Exploring multiple pages...")

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

                if r["bugs"]:
                    st.error("Issues found")
                    for b in r["bugs"]:
                        st.markdown(f"- ⚠️ {b}")
                else:
                    st.success("No issues")

                if r["screenshot"]:
                    st.image(r["screenshot"])

                st.divider()

        except Exception as e:
            st.error(f"App crashed: {str(e)}")
