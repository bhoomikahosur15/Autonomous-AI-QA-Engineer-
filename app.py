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


# ================= HUMAN SCROLL =================
async def human_scroll(page):
    for _ in range(2):
        await page.mouse.wheel(0, 2000)
        await page.wait_for_timeout(500)


# ================= PRIORITIZE ELEMENTS =================
async def prioritize_elements(page):
    elements = await page.query_selector_all("a, button, input, select")
    return elements[:5]  # keep it simple + fast


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
                async with page.expect_navigation(timeout=3000):
                    await el.click()
            except:
                await el.click()

            return "Clicked element"

    except Exception as e:
        return f"Failed: {str(e)}"


# ================= ELEMENT TESTING =================
async def test_elements(page):
    results = []

    try:
        elements = await page.query_selector_all("a, button, input, select")

        for el in elements[:5]:
            try:
                text = (await el.inner_text() or "").strip()[:30]
                tag = await el.evaluate("el => el.tagName.toLowerCase()")
                prev_url = page.url

                if tag == "input":
                    await el.fill("test123")
                    results.append({
                        "action": f"Fill input '{text}'",
                        "status": "PASS",
                        "reason": "Input accepted"
                    })

                else:
                    try:
                        async with page.expect_navigation(timeout=3000):
                            await el.click()
                    except:
                        await el.click()

                    await page.wait_for_timeout(1000)

                    if page.url != prev_url:
                        results.append({
                            "action": f"Click '{text}'",
                            "status": "PASS",
                            "reason": "Navigation successful"
                        })
                    else:
                        results.append({
                            "action": f"Click '{text}'",
                            "status": "FAIL",
                            "reason": "No navigation happened"
                        })

            except Exception as e:
                results.append({
                    "action": f"Interact '{text}'",
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
            # ✅ FIXED NAVIGATION
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            await human_scroll(page)

            test_case = [
                "Page Load Validation",
                "UI Interaction Testing",
                "Element Navigation Testing"
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
            # ✅ FIXED FALLBACK (DOES NOT BREAK FLOW)
            results.append({
                "url": url,
                "test_case": [
                    "Page Load Validation",
                    "Fallback Handling"
                ],
                "actions": [],
                "bugs": [f"Handled error: {str(e)}"],
                "screenshot": None
            })
            continue

        finally:
            await page.close()

    return results


# ================= RUN =================
async def run_agent(url):
    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )

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

            # 🧪 Test Cases
            st.markdown("### 🧪 Test Cases:")
            for t in r["test_case"]:
                st.markdown(f"- {t}")

            # ⚡ Action Results (UPDATED)
            st.markdown("### ⚡ Action Results:")

            if r["actions"]:
                for res in r["actions"]:
                    if res["status"] == "PASS":
                        st.success(f"✅ {res['action']} → {res['reason']}")
                    else:
                        st.error(f"❌ {res['action']} → {res['reason']}")
            else:
                st.info("No actions performed")

            # 🚨 Issues (UPDATED)
            if r["bugs"]:
                st.markdown("### 🚨 Issues Found:")
                for b in r["bugs"]:
                    st.error(f"⚠️ {b}")
            else:
                st.success("No issues")

            # 📸 Screenshot
            if r["screenshot"]:
                st.image(r["screenshot"])

            st.divider()
