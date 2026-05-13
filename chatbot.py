"""
utils/chatbot.py
AI analyst chatbot powered by Groq (llama-3.3-70b-versatile).
Renders as a floating bubble overlay — no sidebar, no inline section.

secrets.toml:
    [groq]
    api_key = "gsk_..."
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


# ── System prompt ──────────────────────────────────────────────────────────────

def _build_system_prompt(df: pd.DataFrame) -> str:
    lines = [
        "You are an expert cybersecurity and incident intelligence analyst.",
        "You are embedded in a live incident monitoring dashboard.",
        "Answer questions concisely and accurately using the data context below.",
        "If asked to analyse trends or make predictions, reason step by step.",
        "",
        "=== CURRENT DASHBOARD DATA SUMMARY ===",
        f"Total incidents: {len(df)}",
    ]

    def top5(col):
        if col in df.columns:
            return df[col].value_counts().head(5).to_dict()
        return {}

    for label, col in [
        ("Top categories",        "category"),
        ("Top incident types",    "incident_type"),
        ("Top countries",         "country"),
        ("Impact breakdown",      "impact"),
        ("Top sources",           "source"),
        ("Top entities affected", "entity_affected"),
    ]:
        d = top5(col)
        if d:
            lines.append(f"{label}: {json.dumps(d)}")

    if "incident_date" in df.columns:
        dated = df.dropna(subset=["incident_date"])
        if not dated.empty:
            lines.append(
                f"Date range: {dated['incident_date'].min().date()} "
                f"to {dated['incident_date'].max().date()} (GMT+8)"
            )

    lines += [
        "===",
        "",
        "Respond in clear English. Use bullet points for lists.",
        "If asked about predictions, clarify they are analytical estimates.",
        "Keep responses under 300 words unless more detail is specifically requested.",
    ]
    return "\n".join(lines)


# ── Groq client ────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _get_client():
    if not GROQ_AVAILABLE:
        return None, "package_missing"
    if "groq" not in st.secrets or "api_key" not in st.secrets["groq"]:
        return None, "missing_key"
    try:
        client = Groq(api_key=st.secrets["groq"]["api_key"])
        return client, "ok"
    except Exception as e:
        return None, str(e)


# ── Floating bubble UI ─────────────────────────────────────────────────────────

def chatbot_ui(df: pd.DataFrame):
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # ── Inject CSS + HTML floating panel ──────────────────────────────────────
    st.markdown("""
<style>
/* Floating Action Button */
#groq-fab {
    position: fixed; bottom: 28px; right: 28px;
    width: 58px; height: 58px;
    background: linear-gradient(135deg, #f55036 0%, #f97316 100%);
    border-radius: 50%;
    box-shadow: 0 4px 20px rgba(245,80,54,0.45);
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; z-index: 9999;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    border: none; outline: none;
}
#groq-fab:hover { transform: scale(1.08); box-shadow: 0 6px 28px rgba(245,80,54,0.6); }
#groq-fab svg { pointer-events: none; }

#groq-badge {
    position: fixed; bottom: 74px; right: 24px;
    background: #3fb950; color: #0d1117;
    font-size: 10px; font-weight: 700;
    border-radius: 10px; padding: 2px 6px;
    z-index: 10000; display: none;
    font-family: monospace;
}

/* Chat panel */
#groq-panel {
    position: fixed; bottom: 100px; right: 28px;
    width: 380px; max-height: 580px;
    background: #0d1117; border: 1px solid #30363d;
    border-radius: 16px;
    box-shadow: 0 12px 48px rgba(0,0,0,0.6);
    display: flex; flex-direction: column;
    z-index: 9998; overflow: hidden;
    transition: opacity 0.2s ease, transform 0.25s cubic-bezier(.34,1.56,.64,1);
    font-family: 'IBM Plex Sans', sans-serif;
}
#groq-panel.hidden { opacity: 0; transform: translateY(24px) scale(0.95); pointer-events: none; }

.gp-header {
    background: linear-gradient(135deg, #161b22 0%, #1c2128 100%);
    border-bottom: 1px solid #21262d;
    padding: 14px 16px 12px;
    display: flex; align-items: center; gap: 10px; flex-shrink: 0;
}
.gp-avatar {
    width: 32px; height: 32px;
    background: linear-gradient(135deg, #f55036, #f97316);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 15px; flex-shrink: 0;
}
.gp-title { font-weight: 600; font-size: 14px; color: #f0f6fc; }
.gp-subtitle { font-size: 11px; color: #8b949e; margin-top: 1px; }
.gp-close {
    margin-left: auto; background: none; border: none;
    color: #8b949e; font-size: 18px; cursor: pointer;
    padding: 2px 7px; border-radius: 4px;
    transition: color 0.15s, background 0.15s;
}
.gp-close:hover { color: #f0f6fc; background: #21262d; }

.gp-messages {
    flex: 1; overflow-y: auto;
    padding: 14px 14px 6px;
    display: flex; flex-direction: column; gap: 10px;
    scrollbar-width: thin; scrollbar-color: #30363d transparent;
}
.gp-messages::-webkit-scrollbar { width: 4px; }
.gp-messages::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }

.gp-empty {
    text-align: center; padding: 24px 16px;
    color: #484f58; font-size: 13px; line-height: 1.6;
}
.gp-empty-icon { font-size: 32px; margin-bottom: 8px; }

.gp-msg { display: flex; flex-direction: column; max-width: 88%; }
.gp-msg.user { align-self: flex-end; align-items: flex-end; }
.gp-msg.bot  { align-self: flex-start; align-items: flex-start; }
.gp-bubble {
    padding: 10px 13px; border-radius: 14px;
    font-size: 13px; line-height: 1.55; color: #c9d1d9;
}
.gp-msg.user .gp-bubble {
    background: #1f3349; border: 1px solid #2d4a6e; border-bottom-right-radius: 4px;
}
.gp-msg.bot .gp-bubble {
    background: #161b22; border: 1px solid #21262d; border-bottom-left-radius: 4px;
}
.gp-role {
    font-size: 10px; font-weight: 600; letter-spacing: 0.07em;
    text-transform: uppercase; margin-bottom: 3px; color: #484f58;
}
.gp-msg.user .gp-role { color: #388bfd; }
.gp-msg.bot  .gp-role { color: #f55036; }

.gp-suggestions {
    padding: 8px 14px 4px;
    display: flex; flex-wrap: wrap; gap: 6px;
    border-top: 1px solid #161b22; flex-shrink: 0;
}
.gp-chip {
    background: #161b22; border: 1px solid #30363d;
    color: #8b949e; font-size: 11px; padding: 4px 9px;
    border-radius: 20px; cursor: pointer;
    transition: border-color 0.15s, color 0.15s;
}
.gp-chip:hover { border-color: #f55036; color: #f0f6fc; }

.gp-input-row {
    padding: 10px 12px; border-top: 1px solid #21262d;
    display: flex; gap: 8px; align-items: center;
    flex-shrink: 0; background: #0d1117;
}
.gp-input {
    flex: 1; background: #161b22; border: 1px solid #30363d;
    color: #c9d1d9; font-size: 13px; padding: 8px 12px;
    border-radius: 20px; outline: none; transition: border-color 0.15s;
    font-family: inherit;
}
.gp-input::placeholder { color: #484f58; }
.gp-input:focus { border-color: #f55036; }
.gp-send {
    width: 34px; height: 34px;
    background: linear-gradient(135deg, #f55036, #f97316);
    border: none; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    cursor: pointer; flex-shrink: 0;
    transition: transform 0.15s, opacity 0.15s;
}
.gp-send:hover { transform: scale(1.1); }
.gp-send:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }

.gp-typing { display: flex; gap: 4px; align-items: center; padding: 4px 2px; }
.gp-dot {
    width: 6px; height: 6px; background: #f55036;
    border-radius: 50%; animation: gp-bounce 1.2s infinite;
}
.gp-dot:nth-child(2) { animation-delay: 0.2s; }
.gp-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes gp-bounce {
    0%, 60%, 100% { transform: translateY(0); }
    30% { transform: translateY(-5px); }
}
</style>

<button id="groq-fab" title="Ask Groq AI Analyst" onclick="toggleGroqPanel()">
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"
              stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
              fill="rgba(255,255,255,0.15)"/>
    </svg>
</button>
<div id="groq-badge"></div>

<div id="groq-panel" class="hidden">
    <div class="gp-header">
        <div class="gp-avatar">⚡</div>
        <div>
            <div class="gp-title">Groq AI Analyst</div>
            <div class="gp-subtitle">Llama 3.3 · Free tier · Incident Intelligence</div>
        </div>
        <button class="gp-close" onclick="toggleGroqPanel()">✕</button>
    </div>
    <div class="gp-messages" id="gp-messages">
        <div class="gp-empty" id="gp-empty">
            <div class="gp-empty-icon">🛡️</div>
            <strong style="color:#8b949e">Groq Analyst ready</strong><br>
            Ask about incidents, trends,<br>or threat intelligence.
        </div>
    </div>
    <div class="gp-suggestions">
        <span class="gp-chip" onclick="groqChip(this)">Top critical incidents</span>
        <span class="gp-chip" onclick="groqChip(this)">Countries with most incidents</span>
        <span class="gp-chip" onclick="groqChip(this)">Emerging trends</span>
        <span class="gp-chip" onclick="groqChip(this)">Main threat categories</span>
    </div>
    <div class="gp-input-row">
        <input class="gp-input" id="gp-input" type="text"
               placeholder="Ask the analyst…"
               onkeydown="if(event.key==='Enter') groqSend()">
        <button class="gp-send" id="gp-send" onclick="groqSend()">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z"
                      stroke="white" stroke-width="2.2"
                      stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
        </button>
    </div>
</div>

<script>
(function(){
    var _open = false;

    window.toggleGroqPanel = function(){
        _open = !_open;
        var p = document.getElementById('groq-panel');
        _open ? p.classList.remove('hidden') : p.classList.add('hidden');
        if(_open){ document.getElementById('gp-input').focus(); updateBadge(); }
    };

    window.groqChip = function(el){
        document.getElementById('gp-input').value = el.textContent;
        groqSend();
    };

    window.groqSend = function(){
        var inp = document.getElementById('gp-input');
        var txt = inp.value.trim();
        if(!txt) return;
        inp.value = '';
        groqAppend('user','You', txt);
        showTyping();
        // Write to the hidden Streamlit input and dispatch change
        var st_inp = window.parent.document.querySelector('input[aria-label="groq_hidden_input"]');
        if(st_inp){
            var nativeInput = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
            nativeInput.set.call(st_inp, txt);
            st_inp.dispatchEvent(new Event('input', {bubbles:true}));
        }
    };

    window.groqAppend = function(role, label, content){
        var empty = document.getElementById('gp-empty');
        if(empty) empty.style.display='none';
        var msgs = document.getElementById('gp-messages');
        var d = document.createElement('div');
        d.className = 'gp-msg '+role;
        d.innerHTML = '<div class="gp-role">'+label+'</div>'
                    + '<div class="gp-bubble">'+content.replace(/\n/g,'<br>')+'</div>';
        msgs.appendChild(d);
        msgs.scrollTop = msgs.scrollHeight;
        updateBadge();
    };

    window.showTyping = function(){
        var msgs = document.getElementById('gp-messages');
        var d = document.createElement('div');
        d.id = 'gp-typing-ind'; d.className = 'gp-msg bot';
        d.innerHTML = '<div class="gp-role">Groq Analyst</div>'
                    + '<div class="gp-bubble"><div class="gp-typing">'
                    + '<div class="gp-dot"></div><div class="gp-dot"></div><div class="gp-dot"></div>'
                    + '</div></div>';
        msgs.appendChild(d);
        msgs.scrollTop = msgs.scrollHeight;
        document.getElementById('gp-send').disabled = true;
    };

    window.removeTyping = function(){
        var el = document.getElementById('gp-typing-ind');
        if(el) el.remove();
        var btn = document.getElementById('gp-send');
        if(btn) btn.disabled = false;
    };

    window.updateBadge = function(){
        var badge = document.getElementById('groq-badge');
        if(!badge) return;
        var count = document.querySelectorAll('#gp-messages .gp-msg').length;
        if(count > 0 && !_open){ badge.style.display='block'; badge.textContent=count; }
        else { badge.style.display='none'; }
    };
})();
</script>
    """, unsafe_allow_html=True)

    # ── Hidden Streamlit text input wired to JS ────────────────────────────────
    question_raw = st.text_input(
        "groq_hidden_input",
        key="groq_hidden_widget",
        label_visibility="hidden",
    )
    # Hide it via CSS targeting the label text
    st.markdown("""
    <style>
    label[data-testid="stWidgetLabel"]:has(+ div input[aria-label="groq_hidden_input"]),
    div:has(> label + div > input[aria-label="groq_hidden_input"]) {
        position:fixed!important; opacity:0!important;
        pointer-events:none!important; height:0!important; overflow:hidden!important;
    }
    </style>
    """, unsafe_allow_html=True)

    question = question_raw.strip() if question_raw else None

    # ── Generate Groq response ─────────────────────────────────────────────────
    if question and (
        not st.session_state.chat_history
        or st.session_state.chat_history[-1].get("content") != question
        or st.session_state.chat_history[-1].get("role") != "user"
    ):
        st.session_state.chat_history.append({"role": "user", "content": question})
        client, status = _get_client()

        if status == "package_missing":
            answer = "❌ `groq` package not installed. Run: `pip install groq`"
        elif status == "missing_key":
            answer = "❌ Groq API key missing. Add `[groq]` section with `api_key` to `.streamlit/secrets.toml`."
        elif client is None:
            answer = f"❌ Groq init failed: {status}"
        else:
            try:
                messages = [{"role": "system", "content": _build_system_prompt(df)}]
                for m in st.session_state.chat_history:
                    role = "assistant" if m["role"] == "assistant" else "user"
                    messages.append({"role": role, "content": m["content"]})

                with st.spinner(""):
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=messages,
                        max_tokens=1024,
                        temperature=0.4,
                    )
                answer = response.choices[0].message.content
            except Exception as e:
                answer = f"❌ Groq error: {e}"

        st.session_state.chat_history.append({"role": "assistant", "content": answer})

        # Push latest bot reply into the floating bubble via JS
        safe_answer = answer.replace("\\", "\\\\").replace("`", "\\`").replace("</", "<\\/")
        components.html(f"""
        <script>
        (function(){{
            var p = window.parent;
            if(p.removeTyping) p.removeTyping();
            if(p.groqAppend) p.groqAppend('bot','Groq Analyst',`{safe_answer}`);
        }})();
        </script>
        """, height=0)
