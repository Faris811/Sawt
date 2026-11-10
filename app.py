from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import quote_plus
from pathlib import Path
from typing import Any

import edge_tts
import streamlit as st

DATA_FILE = Path(__file__).with_name("data.json")

st.set_page_config(page_title="صَوْت | Sawt", page_icon="🔊", layout="centered")

st.markdown("""
<style>
.stApp { direction: rtl; }
.block-container { max-width: 820px; padding-top: 2rem; padding-bottom: 3rem; }
textarea { direction: rtl !important; font-size: 20px !important; line-height: 1.8 !important; }
input { direction: rtl; }
.stButton > button, .stDownloadButton > button, [data-testid="stLinkButton"] a {
    min-height: 2.9rem; width: 100%; border-radius: 14px;
    white-space: normal; font-weight: 600; transition: transform .15s ease, box-shadow .15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    transform: translateY(-1px); box-shadow: 0 5px 16px rgba(0,0,0,.08);
}
div[data-testid="stAudio"] { direction: ltr; border-radius: 14px; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 18px; }
h1, h2, h3 { letter-spacing: -.35px; }
[data-testid="stCaptionContainer"] { line-height: 1.7; }
@media (max-width: 640px) {
    .block-container { padding: 1rem .8rem 2rem; }
    textarea { font-size: 18px !important; }
}
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

def gemini_tts(text: str, voice: str, delivery: str) -> bytes:
    """Generate natural speech with Gemini TTS. Returns a complete WAV file."""
    key = gemini_key()
    if not key:
        raise RuntimeError("أضف GEMINI_API_KEY لتفعيل صوت Gemini")
    model = os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
    pace = {
        "طبيعي": "at a natural conversational pace",
        "أبطأ": "slightly slower, calm and clear",
        "أسرع قليلًا": "slightly quicker but still clear and natural",
        "نبرة أعلى": "with a slightly brighter, lively tone",
        "نبرة أخفض": "with a slightly lower, calm tone",
    }.get(delivery, "at a natural conversational pace")
    speaker = "a native Saudi male speaker" if voice == "Puck" else "a native Saudi female speaker"
    style = (
        f"Speak as {speaker}, using clear, natural Saudi colloquial Arabic (a neutral Saudi dialect). "
        "Pronounce every Arabic word accurately as a whole word, never spell it letter by letter. "
        "Articulate Arabic consonants clearly, especially ع، ح، خ، غ، ق، ص، ض، ط، ظ، ث، ذ, "
        "and keep their correct Arabic sounds. Do not replace them with unrelated sounds or omit them. "
        "Use natural Saudi vowel sounds and connected speech, with smooth syllables and no clipped endings. "
        "Sound warm, fluent and human, like an everyday conversation, not a formal newsreader. "
        "Avoid stuttering, repeated syllables, hesitation sounds, vocal glitches, robotic cadence, "
        "and unnecessary pauses. Read punctuation naturally. "
        "Speak only the exact supplied words: do not add, omit, translate, or paraphrase anything. "
        + pace + "."
    )
    payload = {
        "model": model,
        "input": [{
            "type": "user_input",
            "content": [{
                "type": "text",
                "text": text,
                "annotations": [{
                    "type": "speech_metadata",
                    "style": style,
                }],
            }],
        }],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }
    request = urllib.request.Request(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini TTS API ({exc.code}): {details[:700]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"تعذر الاتصال بخدمة Gemini: {exc.reason}") from exc

    audio_data = (result.get("output_audio") or {}).get("data")
    if not audio_data:
        raise RuntimeError("Gemini لم يُرجع ملفًا صوتيًا")
    return base64.b64decode(audio_data)


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
def text_to_speech(
    text: str, engine: str, voice: str, delivery: str,
    rate: str, pitch: str, api_key: str = "",
) -> tuple[bytes, str]:
    if engine == "Gemini TTS":
        return gemini_tts(text, voice, delivery), "audio/wav"

    async def generate() -> bytes:
        communicator = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
        audio = bytearray()
        async for chunk in communicator.stream():
            if chunk.get("type") == "audio":
                audio.extend(chunk["data"])
        if not audio:
            raise RuntimeError("لم يتم استلام ملف صوتي")
        return bytes(audio)
    return asyncio.run(generate()), "audio/mp3"

def select_phrase(value: str) -> None:
    st.session_state.message = value

def queue_speech() -> None:
    st.session_state.pending = st.session_state.message.strip()
    st.session_state.audio_version = int(st.session_state.get("audio_version", 0)) + 1

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
    st.session_state.audio_version = 0
    st.session_state.ai_phrases = []

st.title("صَوْت 🔊")
st.caption("اكتب ما تريد قوله، وسيقوم صَوْت بنطقه بصوت سعودي واضح.")
st.divider()

st.text_area("اكتب هنا", key="message", height=125, placeholder="اكتب الجملة التي تريد قولها...", label_visibility="collapsed")

# Saudi Sign Language helper: point to the Saudi Association's verified sign library.
sign_text = st.session_state.message.strip()
if sign_text:
    st.subheader("🤟 لغة الإشارة السعودية")
    st.caption("ابحث عن كل كلمة في مكتبة الجمعية السعودية للإعاقة السمعية. النتائج تفتح صور الإشارة الأصلية عند توفرها.")
    sign_words = list(dict.fromkeys(re.findall(r"[\u0621-\u064A\u0660-\u0669]+", sign_text)))
    if sign_words:
        sign_cols = st.columns(2)
        for i, word in enumerate(sign_words[:8]):
            image_search = "https://www.google.com/search?tbm=isch&q=" + quote_plus(
                f'site:sshi.sa/category "{word}" لغة الإشارة السعودية'
            )
            sign_cols[i % 2].link_button(f"🖼️ إشارة: {word}", image_search, use_container_width=True)
        if len(sign_words) > 8:
            st.caption("تم عرض أول ٨ كلمات. ابحث عن بقية الكلمات من المكتبة.")
    st.link_button("📚 فتح مكتبة لغة الإشارة السعودية", "https://sshi.sa/", use_container_width=True)
    st.caption("إذا لم توجد للكلمة إشارة مستقلة، يمكن تهجئتها بحروف الأصابع.")
    st.image(
        "https://sshi.sa/assets/%D8%A3%D8%A8%D8%AC%D8%AF%D9%8A%D8%A9%20%D8%A7%D9%84%D8%A7%D8%B4%D8%A7%D8%B1%D8%A9%20%D8%A7%D9%84%D8%B9%D8%B1%D8%A8%D9%8A%D8%A9-c3f05c67.webp",
        caption="أبجدية الأصابع العربية — من مكتبة لغة الإشارة السعودية",
        use_container_width=True,
    )

c1, c2, c3 = st.columns([3, 1, 1])
c1.button("🔊 تكلم", type="primary", on_click=queue_speech, disabled=not bool(st.session_state.message.strip()))
c2.button("مسح", on_click=clear_message, disabled=not bool(st.session_state.message.strip()))
c3.button("⭐ حفظ", on_click=save_message, disabled=not bool(st.session_state.message.strip()))

# Keep the generated player directly below the main controls, not at the bottom of the page.
audio_placeholder = st.container()

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
gemini_ready = bool(gemini_key())
# Prefer the dedicated Saudi Arabic voices by default; Gemini remains available as an alternative.
engine_options = ["Microsoft السعودي (نطق سعودي واضح)"]
if gemini_ready:
    engine_options.append("Gemini الطبيعي (تجريبي)")
engine_label = st.radio(
    "محرك الصوت",
    engine_options,
    horizontal=False,
    help="Gemini يولّد صوتًا أكثر تعبيرًا. صوت Microsoft يستخدم أصواتًا سعودية محددة.",
)
use_gemini_tts = engine_label.startswith("Gemini")
if use_gemini_tts:
    voice_options = {"👨 صوت رجالي": "Puck", "👩 صوت نسائي": "Kore"}
else:
    voice_options = VOICES
voice_name = st.radio("اختر الصوت", list(voice_options), horizontal=True)
delivery_name = st.selectbox("طريقة الإلقاء", list(DELIVERY))
rate, pitch = DELIVERY[delivery_name]
if use_gemini_tts:
    st.caption("جرّب هذا المحرك إذا أردت إلقاءً تعبيريًا؛ لأوضح نطق سعودي مباشر، اختر Microsoft السعودي.")

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
            engine = "Gemini TTS" if use_gemini_tts else "Edge TTS"
            st.session_state.audio, st.session_state.audio_format = text_to_speech(
                phrase,
                engine,
                voice_options[voice_name],
                delivery_name,
                rate,
                pitch,
                gemini_key() or "",
            )
    except Exception as exc:
        st.session_state.audio = None
        st.error(f"تعذر توليد الصوت. تحقق من اتصال الإنترنت ومفتاح Gemini ثم حاول مجددًا. التفاصيل: {exc}")

with audio_placeholder:
    if st.session_state.audio:
        st.subheader("🎧 الصوت الناتج")
        audio_format = st.session_state.get("audio_format", "audio/mp3")
        st.audio(
            st.session_state.audio,
            format=audio_format,
            autoplay=True,
            alt=f"الصوت الناتج، تشغيل رقم {st.session_state.audio_version}",
        )
        extension = "wav" if audio_format == "audio/wav" else "mp3"
        mime = "audio/wav" if extension == "wav" else "audio/mpeg"
        st.download_button(
            f"⬇️ تحميل الصوت {extension.upper()}",
            st.session_state.audio,
            f"sawt.{extension}",
            mime,
        )

# A small, useful recent-history view; most-used phrases remain easy to find.
recent_history = sorted(
    st.session_state.history.items(),
    key=lambda item: int(item[1] or 0),
    reverse=True,
)[:8]
if recent_history:
    with st.expander("🕘 سجل العبارات المستخدمة"):
        st.caption("تُرتّب العبارات حسب عدد مرات الاستخدام المسجّلة.")
        history_cols = st.columns(2)
        for i, (phrase, count) in enumerate(recent_history):
            history_cols[i % 2].button(
                f"{phrase}  ·  {count}×",
                key=f"history_{i}",
                on_click=select_phrase,
                args=(phrase,),
            )

st.divider()
st.caption("صَوْت | يتطلب اتصال إنترنت لتوليد الصوت. التخزين المحلي قد يُمسح عند إعادة تشغيل Streamlit Cloud.")
