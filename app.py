from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import edge_tts
import streamlit as st

DATA_FILE = Path(__file__).with_name("data.json")

st.set_page_config(page_title="صَوْت | Sawt", page_icon="🔊", layout="centered")

st.markdown("""
<style>
.stApp { direction: rtl; }
textarea { direction: rtl !important; font-size: 22px !important; }
input { direction: rtl; }
.stButton > button { min-height: 3rem; width: 100%; border-radius: 12px; white-space: normal; }
div[data-testid="stAudio"] { direction: ltr; }
</style>
""", unsafe_allow_html=True)

VOICES = {
    "👨 رجل سعودي": "ar-SA-HamedNeural",
    "👩 امرأة سعودية": "ar-SA-ZariyahNeural",
}
DELIVERY = {
    "طبيعي": ("+0%", "+0Hz"),
    "أبطأ": ("-12%", "+0Hz"),
    "أسرع قليلًا": ("+8%", "+0Hz"),
    "نبرة أعلى": ("+0%", "+15Hz"),
    "نبرة أخفض": ("+0%", "-12Hz"),
}
PHRASES = {
    "احتياجات": ["أبي ماء", "أبي أكل", "أبي أروح الحمام", "أحتاج مساعدة", "أبي أنام", "أبي دوائي", "أنا تعبان", "أبي أطلع برا"],
    "مشاعر": ["أنا مبسوط", "أنا زعلان", "أنا خايف", "أنا متضايق", "أحبك", "شكرًا", "آسف", "أنا مرتاح"],
    "أسئلة": ["وش الوقت؟", "وين رايح؟", "متى نوصل؟", "من هذا؟", "ممكن تعيد؟", "ممكن تساعدني؟"],
    "محادثة": ["السلام عليكم", "وعليكم السلام", "كيف حالك؟", "الحمد لله بخير", "نعم", "لا", "ما فهمت", "انتظر شوي", "مع السلامة"],
    "ألم وصحة": ["أحس بألم", "رأسي يعورني", "بطني يعورني", "أحس بدوخة", "أحتاج أروح المستشفى", "نادوا الطبيب", "أحتاج أرتاح"],
}

def load_data() -> dict[str, Any]:
    try:
        raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Invalid data")
        return {
            "saved": raw.get("saved", []) if isinstance(raw.get("saved", []), list) else [],
            "history": raw.get("history", {}) if isinstance(raw.get("history", {}), dict) else {},
        }
    except (OSError, ValueError, json.JSONDecodeError):
        return {"saved": [], "history": {}}

def save_data() -> None:
    try:
        DATA_FILE.write_text(
            json.dumps({"saved": st.session_state.saved, "history": st.session_state.history},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        st.warning("تعذر حفظ البيانات على الخادم. يمكنك الاستمرار باستخدام التطبيق.")

def gemini_key() -> str | None:
    key = os.getenv("GEMINI_API_KEY")
    if key:
        return key.strip()
    try:
        return str(st.secrets.get("GEMINI_API_KEY", "")).strip() or None
    except Exception:
        return None

def ask_gemini(prompt: str) -> str:
    key = gemini_key()
    if not key:
        raise RuntimeError("أضف GEMINI_API_KEY أولًا")
    from google import genai
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    response = genai.Client(api_key=key).models.generate_content(model=model, contents=prompt)
    answer = getattr(response, "text", None)
    if not answer:
        raise RuntimeError("لم يرجع المساعد الذكي إجابة")
    return answer.strip()

def parse_list(raw: str, limit: int = 6) -> list[str]:
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    left, right = cleaned.find("["), cleaned.rfind("]")
    if left >= 0 and right > left:
        cleaned = cleaned[left:right + 1]
    values = json.loads(cleaned)
    if not isinstance(values, list):
        raise ValueError("AI response is not a list")
    return [str(x).strip() for x in values if str(x).strip()][:limit]

@st.cache_data(show_spinner=False, max_entries=200)
def text_to_speech(text: str, voice: str, rate: str, pitch: str) -> bytes:
    async def generate() -> bytes:
        communicator = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
        audio = bytearray()
        async for chunk in communicator.stream():
            if chunk.get("type") == "audio":
                audio.extend(chunk["data"])
        if not audio:
            raise RuntimeError("لم يتم استلام ملف صوتي")
        return bytes(audio)
    return asyncio.run(generate())

def select_phrase(value: str) -> None:
    st.session_state.message = value

def queue_speech() -> None:
    st.session_state.pending = st.session_state.message.strip()

def clear_message() -> None:
    st.session_state.message = ""

def save_message() -> None:
    value = st.session_state.message.strip()
    if value and value not in st.session_state.saved:
        st.session_state.saved.insert(0, value)
        save_data()

if "ready" not in st.session_state:
    data = load_data()
    st.session_state.ready = True
    st.session_state.saved = data["saved"]
    st.session_state.history = data["history"]
    st.session_state.message = ""
    st.session_state.pending = ""
    st.session_state.audio = None
    st.session_state.ai_phrases = []

st.title("صَوْت 🔊")
st.caption("اكتب ما تريد قوله، وسيقوم صَوْت بنطقه بصوت سعودي واضح.")
st.divider()

st.text_area("اكتب هنا", key="message", height=125, placeholder="اكتب الجملة التي تريد قولها...", label_visibility="collapsed")
c1, c2, c3 = st.columns([3, 1, 1])
c1.button("🔊 تكلم", type="primary", on_click=queue_speech)
c2.button("مسح", on_click=clear_message)
c3.button("⭐ حفظ", on_click=save_message)

# Quick suggestions are ranked by previous use and saved phrases.
query = st.session_state.message.strip()
scores = {phrase: 0 for group in PHRASES.values() for phrase in group}
for phrase in st.session_state.saved:
    scores[phrase] = scores.get(phrase, 0) + 2
for phrase, count in st.session_state.history.items():
    scores[phrase] = scores.get(phrase, 0) + int(count or 0)
if query:
    quick = [p for p in scores if query in p and p != query]
else:
    quick = [p for p, score in scores.items() if score > 0]
quick = sorted(quick, key=lambda p: scores[p], reverse=True)[:6]
if quick:
    st.markdown("**اقتراحات سريعة**")
    cols = st.columns(2)
    for i, phrase in enumerate(quick):
        cols[i % 2].button(phrase, key=f"quick_{i}", on_click=select_phrase, args=(phrase,))

st.subheader("إعدادات الصوت")
voice_name = st.radio("اختر الصوت", list(VOICES), horizontal=True)
delivery_name = st.selectbox("طريقة الإلقاء", list(DELIVERY))
rate, pitch = DELIVERY[delivery_name]

with st.expander("✨ المساعد الذكي (اختياري)"):
    if not gemini_key():
        st.info("التطبيق يعمل بدون ذكاء اصطناعي. لتفعيل Gemini أضف GEMINI_API_KEY في Secrets.")
    else:
        other = st.text_input("وش قال لك الطرف الثاني؟ (اختياري)")
        context = st.selectbox("الموقف", ["غير محدد", "البيت", "المستشفى", "المطعم", "السوق", "المدرسة/الجامعة", "السيارة"])
        a, b = st.columns(2)
        if a.button("💡 اقترح جملًا"):
            prompt = (
                "أنت مساعد تواصل لشخص يفهم ويكتب لكنه لا يستطيع الكلام. استخدم لهجة سعودية بسيطة. "
                f"الموقف: {context}. الطرف الآخر قال: {other or 'غير معروف'}. "
                f"الجملة المكتوبة: {query or 'لا شيء'}. اقترح 6 جمل قصيرة قد يحتاج قولها. "
                "أعد مصفوفة JSON نصية فقط."
            )
            try:
                with st.spinner("جاري التفكير..."):
                    st.session_state.ai_phrases = parse_list(ask_gemini(prompt))
            except Exception as exc:
                st.error(f"تعذر تشغيل المساعد: {exc}")
        if b.button("✍️ حسّن جملتي", disabled=not bool(query)):
            prompt = (
                "أعد صياغة الجملة باللهجة السعودية مع الحفاظ على المعنى. "
                "أعطني 3 صيغ: قصيرة، مهذبة، وعفوية. أعد مصفوفة JSON فقط.\n"
                f"الجملة: {query}"
            )
            try:
                with st.spinner("جاري تحسين الجملة..."):
                    st.session_state.ai_phrases = parse_list(ask_gemini(prompt), 3)
            except Exception as exc:
                st.error(f"تعذر تشغيل المساعد: {exc}")
        for i, phrase in enumerate(st.session_state.ai_phrases):
            st.button(phrase, key=f"ai_{i}", on_click=select_phrase, args=(phrase,))

st.subheader("جمل جاهزة")
tabs = st.tabs(list(PHRASES) + ["⭐ المحفوظة"])
for tab, (category, phrases) in zip(tabs, PHRASES.items()):
    with tab:
        cols = st.columns(2)
        for i, phrase in enumerate(phrases):
            cols[i % 2].button(phrase, key=f"{category}_{i}", on_click=select_phrase, args=(phrase,))

with tabs[-1]:
    if not st.session_state.saved:
        st.caption("لا توجد جمل محفوظة. اكتب جملة واضغط ⭐ حفظ.")
    for i, phrase in enumerate(list(st.session_state.saved)):
        left, right = st.columns([5, 1])
        left.button(phrase, key=f"saved_{i}", on_click=select_phrase, args=(phrase,))
        if right.button("🗑", key=f"delete_{i}"):
            st.session_state.saved.pop(i)
            save_data()
            st.rerun()

# Generate audio after all widgets have updated the current session state.
if st.session_state.pending:
    phrase = st.session_state.pending
    st.session_state.pending = ""
    st.session_state.history[phrase] = int(st.session_state.history.get(phrase, 0)) + 1
    save_data()
    try:
        with st.spinner("جاري تجهيز الصوت..."):
            st.session_state.audio = text_to_speech(phrase, VOICES[voice_name], rate, pitch)
    except Exception as exc:
        st.session_state.audio = None
        st.error(f"تعذر توليد الصوت. تحقق من الإنترنت وحاول مجددًا. التفاصيل: {exc}")

if st.session_state.audio:
    st.subheader("الصوت الناتج")
    st.audio(st.session_state.audio, format="audio/mp3")
    st.download_button("⬇️ تحميل الصوت MP3", st.session_state.audio, "sawt.mp3", "audio/mpeg")

st.divider()
st.caption("صَوْت | يتطلب اتصال إنترنت لتوليد الصوت. التخزين المحلي قد يُمسح عند إعادة تشغيل Streamlit Cloud.")
