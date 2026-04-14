import streamlit as st
import asyncio

from langchain_community.llms import Ollama
from playwright.async_api import async_playwright

# ================= LLM =================
llm = Ollama(model="llama3")


# ================= QA EXECUTION =================
async def execution_agent(url):
    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto(url, timeout=30000)
        except:
            pass

        inputs = await page.query_selector_all("input")
        buttons = await page.query_selector_all("button")

        username_field = None
        password_field = None
        login_button = None

        # 🔍 Detect elements
        for inp in inputs:
            name = (await inp.get_attribute("name") or "").lower()
            type_attr = (await inp.get_attribute("type") or "").lower()

            if "user" in name or "email" in name:
                username_field = inp
            elif "pass" in name or type_attr == "password":
                password_field = inp

        for btn in buttons:
            text = (await btn.inner_text()).lower()
            if "login" in text or "sign in" in text:
                login_button = btn

        # ================= VALID LOGIN =================
        try:
            if username_field and password_field and login_button:
                await username_field.fill("standard_user")
                await password_field.fill("secret_sauce")
                await login_button.click()

                await page.wait_for_timeout(1000)

                if "inventory" in page.url or "dashboard" in page.url:
                    results.append({
                        "test_name": "Valid Login Test",
                        "status": "passed"
                    })
                else:
                    results.append({
                        "test_name": "Valid Login Test",
                        "status": "failed",
                        "error": "No redirect after login"
                    })
            else:
                results.append({
                    "test_name": "Login Detection",
                    "status": "failed",
                    "error": "Login elements not found"
                })

        except Exception as e:
            results.append({
                "test_name": "Valid Login Test",
                "status": "failed",
                "error": str(e)
            })

        # ================= INVALID LOGIN =================
        try:
            await page.goto(url)

            if username_field and password_field and login_button:
                await username_field.fill("wrong_user")
                await password_field.fill("wrong_pass")
                await login_button.click()

                await page.wait_for_timeout(1000)

                body = await page.inner_text("body")

                if "error" in body.lower():
                    results.append({
                        "test_name": "Invalid Login Test",
                        "status": "passed"
                    })
                else:
                    results.append({
                        "test_name": "Invalid Login Test",
                        "status": "failed",
                        "error": "No error message shown"
                    })

        except Exception as e:
            results.append({
                "test_name": "Invalid Login Test",
                "status": "failed",
                "error": str(e)
            })

        # ================= EMPTY INPUT =================
        try:
            await page.goto(url)

            if login_button:
                await login_button.click()

                await page.wait_for_timeout(1000)

                body = await page.inner_text("body")

                if "error" in body.lower() or "required" in body.lower():
                    results.append({
                        "test_name": "Empty Input Test",
                        "status": "passed"
                    })
                else:
                    results.append({
                        "test_name": "Empty Input Test",
                        "status": "failed",
                        "error": "No validation for empty fields"
                    })

        except Exception as e:
            results.append({
                "test_name": "Empty Input Test",
                "status": "failed",
                "error": str(e)
            })

        await browser.close()

    return results


# ================= AI ANALYSIS =================
def analyze_results(results):
    prompt = f"""
    You are a QA expert.

    Analyze these test results:
    {results}

    Explain:
    - What issues are found
    - Overall system health
    - Severity of problems
    """

    return llm.invoke(prompt)


# ================= UI =================

st.set_page_config(page_title="AI QA System", layout="wide")

st.title("🤖 AI QA Testing Dashboard")

url = st.text_input("🌐 Enter Website URL")

if st.button(" Run Testing"):

    if url:
        st.info("Running automated QA tests...")

        results = asyncio.run(execution_agent(url))
        analysis = analyze_results(results)

        # ================= METRICS =================
        passed = sum(1 for r in results if r["status"] == "passed")
        failed = sum(1 for r in results if r["status"] == "failed")

        col1, col2, col3 = st.columns(3)

        col1.metric("✅ Passed", passed)
        col2.metric("❌ Failed", failed)
        col3.metric("🧪 Total Tests", len(results))

        st.divider()

        # ================= TEST CARDS =================
        st.subheader(" Test Results")

        for r in results:
            with st.container():
                cols = st.columns([3, 1])

                cols[0].markdown(f"### {r['test_name']}")

                if r["status"] == "passed":
                    cols[1].success("Passed")
                else:
                    cols[1].error("Failed")

                if r["status"] == "failed":
                    st.markdown(f"**⚠️ Issue:** {r.get('error')}")

                st.divider()

        # ================= AI ANALYSIS =================
        st.subheader("QA Summary")

        st.markdown(
    f"""
    <div style='padding:20px; border-radius:12px; background-color:#1e1e1e; color:white; font-size:16px; line-height:1.6'>
    {analysis}
    </div>
    """,
    unsafe_allow_html=True

        )

    else:
        st.warning("Please enter a valid URL")
