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

        if "something went wrong" in body_lower:
            bugs.append("Page crashed")

        if "404" in body:
            bugs.append("Broken page (404)")

    except Exception as e:
        bugs.append(f"Analysis failed: {str(e)}")

    return bugs


# ================= INTERACTION =================
async def interact(page, el):
    try:
        tag = await el.evaluate("el => el.tagName.toLowerCase()")

        if tag == "input":
            await el.fill("test123")
            return ("Fill input", "PASS", "Input accepted")

        else:
            prev_url = page.url

            try:
                async with page.expect_navigation(timeout=3000):
                    await el.click()
            except:
                await el.click()

            await page.wait_for_timeout(1000)

            if page.url != prev_url:
                return ("Click element", "PASS", "Navigation happened")
            else:
                return ("Click element", "FAIL", "No navigation")

    except Exception as e:
        return ("Interaction", "FAIL", str(e))


# ================= ELEMENT TESTING =================
async def test_elements(page):
    results = []

    try:
        elements = await page.query_selector_all("a, button, input, select")

        for el in elements[:5]:
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
                    "action": "Element interaction",
                    "status": "FAIL",
                    "reason": str(e)
                })

    except Exception as e:
        results.append({
            "action": "Element detection",
            "status": "FAIL",
            "reason": str(e)
        })

    return results


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
async def explore(context, start_url, max_pages=2):
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
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            test_case = [
                "Page Load Validation",
                "UI Interaction Testing",
                "Element Navigation Testing"
            ]

            page_bugs = await detect_bugs(page)
            actions = await test_elements(page)

            screenshot = f"screenshots/page_{len(visited)}.png"
            await page.screenshot(path=screenshot)

            results.append({
                "url": url,
                "test_case": test_case,
                "actions": actions,
                "bugs": page_bugs,
                "screenshot": screenshot
            })

            new_links = await extract_links(page, url, visited)
            queue.extend(new_links[:1])

        except Exception as e:
            results.append({
                "url": url,
                "test_case": ["Page Load Validation"],
                "actions": [],
                "bugs": [f"Handled error: {str(e)}"],
                "screenshot": None
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

            st.markdown("### 🧪 Test Cases:")
            for t in r["test_case"]:
                st.markdown(f"- {t}")

            st.markdown("### ⚡ Action Results:")
            if r["actions"]:
                for res in r["actions"]:
                    if res["status"] == "PASS":
                        st.success(f"✅ {res['action']} → {res['reason']}")
                    else:
                        st.error(f"❌ {res['action']} → {res['reason']}")
            else:
                st.info("No actions performed")

            if r["bugs"]:
                st.markdown("### 🚨 Issues Found:")
                for b in r["bugs"]:
                    st.error(f"⚠️ {b}")
            else:
                st.success("No issues")

            if r["screenshot"]:
                st.image(r["screenshot"])

            st.divider()
