import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import streamlit as st
import streamlit.components.v1 as components
from tools.db_tool import init_db, get_saved_jobs, update_job_status
from tools.apply_tool import get_pending_apply_job, execute_apply, clear_pending_apply
import importlib
import agent.orchestrator
importlib.reload(agent.orchestrator)
from agent.orchestrator import run_agent_loop

st.set_page_config(page_title="Local AI Job Agent", page_icon="💼", layout="wide")
init_db()

st.title("💼 Local AI Job Search & Apply Agent")
st.caption("Powered by 100% Local Ollama • LinkedIn • Indeed • Naukri")
st.markdown(
    "<small>💡 Try: *Find Python jobs in India* • *Search Naukri for Backend jobs in Chennai* • *Score these jobs against my resume* • *Apply to the best match*</small>",
    unsafe_allow_html=True
)

# Custom CSS for animated roller, sidebar buttons, and chat input dock
st.markdown("""
<style>
@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
.roller {
    display: inline-block;
    width: 16px;
    height: 16px;
    border: 3px solid rgba(255, 255, 255, 0.3);
    border-radius: 50%;
    border-top-color: #ff4b4b;
    animation: spin 0.8s linear infinite;
    vertical-align: middle;
    margin-left: 8px;
}
.processing-badge {
    display: inline-flex;
    align-items: center;
    background-color: #1e1e2f;
    border: 1px solid #33334d;
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 13px;
    color: #e0e0e0;
}

/* Prevent sidebar button text from breaking vertically */
div[data-testid="stSidebar"] button {
    white-space: nowrap !important;
    word-break: normal !important;
}

/* ── Antigravity-Style Docked + Chat Input Bar ── */
div[data-testid="stBottomBlockContainer"] {
    position: relative !important;
}

/* Position popover button on the far left inside the bottom bar */
[data-testid="stPopover"] {
    position: absolute !important;
    left: 12px !important;
    bottom: 18px !important;
    z-index: 1001 !important;
    margin: 0 !important;
    padding: 0 !important;
    width: 32px !important;
    height: 32px !important;
    pointer-events: none !important;
}

/* Chat Input Bar relative positioning */
[data-testid="stChatInput"],
.stChatInput,
[data-baseweb="base-input"] {
    position: relative !important;
}

/* Clear left space for the + button inside textarea without blocking user input */
[data-testid="stChatInput"] textarea,
[data-testid="stChatInputTextArea"],
.stChatInput textarea,
textarea[data-testid="stChatInput"] {
    padding-left: 54px !important;
    margin-left: 0px !important;
    pointer-events: auto !important;
    position: relative !important;
    z-index: 5 !important;
}

/* Allow clicking on the button itself and the popup body */
[data-testid="stPopover"] button,
[data-testid="stPopoverBody"] {
    pointer-events: auto !important;
}

/* Clean square + button matching Google Antigravity */
[data-testid="stPopover"] button,
[data-testid="stPopoverButton"],
button[aria-haspopup="dialog"] {
    width: 32px !important;
    height: 32px !important;
    min-width: 32px !important;
    max-width: 32px !important;
    min-height: 32px !important;
    max-height: 32px !important;
    padding: 0 !important;
    margin: 0 !important;
    border-radius: 8px !important;
    background-color: #2b2e3c !important;
    border: 1px solid #3e4357 !important;
    color: #e2e8f0 !important;
    box-shadow: none !important;
    cursor: pointer !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    overflow: hidden !important;
    transition: all 0.2s ease !important;
}

[data-testid="stPopover"] button > div,
button[aria-haspopup="dialog"] > div {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
    height: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    gap: 0 !important;
}

[data-testid="stPopover"] button:hover,
button[aria-haspopup="dialog"]:hover {
    background-color: #383d4f !important;
    border-color: #7b829a !important;
    color: #ffffff !important;
    transform: scale(1.04);
}

/* Hide the default dropdown chevron arrow completely across all font/SVG formats */
[data-testid="stPopover"] button [data-testid="stMarkdownContainer"] ~ *,
button[aria-haspopup="dialog"] [data-testid="stMarkdownContainer"] ~ *,
[data-testid="stPopover"] button span[data-testid="stIconMaterial"],
button[aria-haspopup="dialog"] span[data-testid="stIconMaterial"],
[data-testid="stPopover"] button .material-symbols-rounded,
button[aria-haspopup="dialog"] .material-symbols-rounded,
[data-testid="stPopover"] button svg,
button[aria-haspopup="dialog"] svg,
[data-testid="stPopoverButton"] svg {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    font-size: 0 !important;
    visibility: hidden !important;
    opacity: 0 !important;
}

[data-testid="stPopover"] button div[data-testid="stMarkdownContainer"] p,
[data-testid="stPopover"] button p {
    font-size: 20px !important;
    font-weight: 500 !important;
    line-height: 1 !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* Popover body / floating card styling */
div[data-testid="stPopoverBody"] {
    background-color: #1a1b26 !important;
    border: 1px solid #33334d !important;
    border-radius: 12px !important;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6) !important;
    padding: 16px !important;
    min-width: 340px !important;
    max-width: 420px !important;
}
</style>
""", unsafe_allow_html=True)

# ── Safe Alignment Script (Locks alignment and hides chevrons reliably) ──
components.html(
    """
    <script>
    (function() {
        function alignPlusButton() {
            try {
                const pDoc = (window.parent && window.parent.document) ? window.parent.document : document;
                if (!pDoc) return;
                
                const popover = pDoc.querySelector('[data-testid="stPopover"]');
                const chatBar = pDoc.querySelector('[data-testid="stChatInput"]')
                             || pDoc.querySelector('.stChatInput');
                
                if (popover && chatBar) {
                    const rect = chatBar.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        popover.style.setProperty('position', 'fixed', 'important');
                        popover.style.setProperty('left', (rect.left + 12) + 'px', 'important');
                        popover.style.setProperty('top', (rect.top + (rect.height - 32) / 2) + 'px', 'important');
                        popover.style.setProperty('bottom', 'auto', 'important');
                        popover.style.setProperty('z-index', '9999', 'important');
                        popover.style.setProperty('margin', '0px', 'important');
                        popover.style.setProperty('padding', '0px', 'important');
                        popover.style.setProperty('width', '32px', 'important');
                        popover.style.setProperty('height', '32px', 'important');
                        popover.style.setProperty('display', 'inline-flex', 'important');
                        popover.style.setProperty('align-items', 'center', 'important');
                        popover.style.setProperty('pointer-events', 'none', 'important');
                        
                        const btn = popover.querySelector('button');
                        if (btn) {
                            btn.style.setProperty('pointer-events', 'auto', 'important');
                            btn.style.setProperty('width', '32px', 'important');
                            btn.style.setProperty('height', '32px', 'important');
                            
                            // Hide any icon or element after the + text
                            const md = btn.querySelector('[data-testid="stMarkdownContainer"]') || btn.firstElementChild;
                            if (md) {
                                let sib = md.nextElementSibling;
                                while (sib) {
                                    sib.style.setProperty('display', 'none', 'important');
                                    sib = sib.nextElementSibling;
                                }
                            }
                            const extraIcons = btn.querySelectorAll('svg, [data-testid="stIconMaterial"], .material-symbols-rounded');
                            extraIcons.forEach(function(icon) {
                                icon.style.setProperty('display', 'none', 'important');
                            });
                        }

                        const textarea = chatBar.querySelector('textarea');
                        if (textarea) {
                            textarea.style.setProperty('padding-left', '54px', 'important');
                            textarea.style.setProperty('pointer-events', 'auto', 'important');
                        }
                    }
                }
            } catch(e) {}
        }

        // Run via both interval and RAF for continuous lock without browser throttling
        setInterval(alignPlusButton, 100);
        function loop() {
            alignPlusButton();
            requestAnimationFrame(loop);
        }
        requestAnimationFrame(loop);

        try {
            window.parent.addEventListener('resize', alignPlusButton);
            window.parent.addEventListener('scroll', alignPlusButton);
        } catch(e) {}
    })();
    </script>
    """,
    height=1,
    width=1
)
with st.sidebar:
    st.header("📄 Resume Status")
    resume_file_path = os.path.join(os.path.dirname(__file__), "data", "resume.pdf")
    if os.path.exists(resume_file_path):
        size_kb = os.path.getsize(resume_file_path) / 1024
        st.success(f"✅ `resume.pdf` ({size_kb:.1f} KB)")
    else:
        st.warning("⚠️ No resume uploaded yet.")
    st.divider()

    st.header("📌 Tracked Applications")
    has_jobs = False
    for status_label, status_key in [("Saved", "SAVED"), ("Applied", "APPLIED"), ("Interview", "INTERVIEW")]:
        jobs = get_saved_jobs(status=status_key)
        if jobs:
            has_jobs = True
            st.markdown(f"**{status_label} ({len(jobs)})**")
            for job in jobs:
                st.markdown(f"- **{job[1]}** at *{job[2]}*  \n  [Open]({job[3]})")
            st.divider()
    if not has_jobs:
        st.info("No saved jobs yet. Ask the agent to find opportunities.")

    st.divider()
    if st.button("🧹 Clear Chat", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

    # Human-in-the-Loop Apply Confirmation
    pending = get_pending_apply_job()
    if pending:
        st.divider()
        st.warning("⚠️ **Application Pending Confirmation**")
        st.markdown(f"**Role:** {pending.get('title')}")
        st.markdown(f"**Company:** {pending.get('company')}")
        if pending.get("url"):
            st.markdown(f"**Link:** [{pending.get('url')}]({pending.get('url')})")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirm & Apply", use_container_width=True):
                with st.spinner("Opening browser..."):
                    result = execute_apply(pending)
                    from tools.db_tool import save_job_to_db
                    save_job_to_db(
                        title=pending.get("title", ""),
                        company=pending.get("company", ""),
                        url=pending.get("url", ""),
                        description=pending.get("snippet", ""),
                        status="APPLIED"
                    )
                clear_pending_apply()
                st.success(result)
                st.rerun()
        with col2:
            if st.button("❌ Cancel", use_container_width=True):
                clear_pending_apply()
                st.info("Application cancelled.")
                st.rerun()

# ── Chat Session ───────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Deduplicate any consecutive duplicate messages in session history
cleaned_history = []
for msg in st.session_state.chat_history:
    role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
    content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
    if role in ["user", "assistant"] and content:
        # Skip if identical to the previous message
        if not cleaned_history or cleaned_history[-1].get("content") != content:
            cleaned_history.append({"role": role, "content": content})
            with st.chat_message(role):
                st.markdown(content)
st.session_state.chat_history = cleaned_history

# ── Popover Attachment (+ Menu Matching Google Antigravity) ───────────────────
resume_target = os.path.join(os.path.dirname(__file__), "data", "resume.pdf")

if hasattr(st, "bottom"):
    popover_area = st.bottom
else:
    popover_area = st.container()

with popover_area:
    with st.popover("+", help="Add files, photo, or tools"):
        st.markdown("#### 📎 Attach & Tools")
        tab_files, tab_media, tab_settings = st.tabs([
            "📄 Upload Resume",
            "📷 Photo / Media",
            "⚙️ Model & Tools"
        ])

        with tab_files:
            st.caption("Upload your resume or documents (PDF, DOCX, TXT):")
            if os.path.exists(resume_target):
                size_kb = os.path.getsize(resume_target) / 1024
                st.success(f"Active: `resume.pdf` ({size_kb:.1f} KB)")
            uploaded_doc = st.file_uploader(
                "Upload Resume",
                type=["pdf", "docx", "txt"],
                key="doc_uploader",
                label_visibility="collapsed"
            )
            if uploaded_doc is not None:
                os.makedirs(os.path.dirname(resume_target), exist_ok=True)
                with open(resume_target, "wb") as f:
                    f.write(uploaded_doc.getbuffer())
                st.success(f"✅ Saved `{uploaded_doc.name}` as active resume!")
                st.rerun()

        with tab_media:
            st.caption("Take a screenshot or upload image of job postings:")
            uploaded_media = st.file_uploader(
                "Upload Image",
                type=["png", "jpg", "jpeg", "webp"],
                key="media_uploader",
                label_visibility="collapsed"
            )
            if uploaded_media is not None:
                media_path = os.path.join(os.path.dirname(__file__), "data", uploaded_media.name)
                os.makedirs(os.path.dirname(media_path), exist_ok=True)
                with open(media_path, "wb") as f:
                    f.write(uploaded_media.getbuffer())
                st.success(f"✅ Uploaded `{uploaded_media.name}`")
                st.image(uploaded_media, width=200)

        with tab_settings:
            st.markdown("##### ⚙️ Agent Model & Tools")
            selected_model_label = st.selectbox(
                "Active LLM Model",
                options=["Qwen 2.5 (7B)", "Llama 3.2 (3B)"],
                index=0,
                key="model_selector_setting"
            )
            st.session_state.active_model_slug = "qwen2.5" if "Qwen" in selected_model_label else "llama3.2:3b"
            st.checkbox("🌐 Web Search (LinkedIn, Indeed, Naukri)", value=True, disabled=True)

# ── Native Bottom Chat Input ──────────────────────────────────────────────────
active_model = st.session_state.get("active_model_slug", "qwen2.5")

if user_prompt := st.chat_input("Write a message..."):
    st.session_state.chat_history.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    with st.chat_message("assistant"):
        status_placeholder = st.empty()
        status_placeholder.markdown(
            '<div class="processing-badge">🤖 AI Agent is thinking... <span class="roller"></span></div>',
            unsafe_allow_html=True
        )

        def show_tool_call(name: str, args: dict):
            labels = {
                "search_web_jobs": "🔍 Searching LinkedIn & Indeed...",
                "search_naukri_jobs": "🔍 Scraping Naukri...",
                "score_and_rank_jobs": "🧠 Scoring jobs against your resume...",
                "read_my_resume": "📄 Reading your resume...",
                "queue_job_for_apply": "📨 Queuing job for application...",
                "save_job_to_db": "💾 Saving job to tracker...",
                "get_saved_jobs": "📋 Fetching saved jobs...",
            }
            label_text = labels.get(name, f"⚙️ Running `{name}`...")
            status_placeholder.markdown(
                f'<div class="processing-badge">{label_text} <span class="roller"></span></div>',
                unsafe_allow_html=True
            )

        final_response = run_agent_loop(
            st.session_state.chat_history,
            tool_callback=show_tool_call,
            model_name=active_model
        )

        status_placeholder.empty()
        st.markdown(final_response)
