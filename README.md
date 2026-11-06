# صَوْت | Sawt

تطبيق تواصل عربي مبسّط يحوّل النص إلى كلام باستخدام أصوات عربية سعودية عبر Edge TTS.

## المزايا
- صوت رجل سعودي وصوت امرأة سعودية.
- تحويل أي نص مكتوب إلى كلام مع خيارات سرعة ونبرة.
- جمل جاهزة مصنفة حسب الاحتياجات والمشاعر والأسئلة والمحادثة والصحة.
- حفظ الجمل المفضلة وحذفها.
- اقتراحات محلية مبنية على الاستخدام.
- مساعد Gemini اختياري لاقتراح الجمل وإعادة صياغتها.
- تشغيل الصوت وتحميله بصيغة MP3.
- واجهة عربية متجاوبة.

## التشغيل محليًا
يتطلب Python 3.10+ واتصال إنترنت لتوليد الصوت.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

ثم افتح http://localhost:8501

## تشغيل المساعد الذكي (اختياري)
أضف مفتاح Gemini في متغير البيئة `GEMINI_API_KEY` أو في Streamlit Secrets:

```toml
GEMINI_API_KEY = "YOUR_API_KEY"
GEMINI_MODEL = "gemini-2.5-flash"
```

لا ترفع المفتاح إلى GitHub. التطبيق يعمل بدون Gemini.

## النشر على Streamlit Community Cloud
1. افتح https://share.streamlit.io/
2. اختر هذا المستودع والفرع `main`.
3. اختر `app.py` كملف رئيسي ثم Deploy.
4. أضف Gemini key من App settings → Secrets عند الحاجة.

## ملاحظات
- Edge TTS يحتاج اتصال إنترنت.
- البيانات المحفوظة تُخزّن في `data.json` محليًا. على Streamlit Cloud قد لا تبقى البيانات بعد إعادة تشغيل التطبيق أو إعادة النشر.
- لا تشارك مفتاح Gemini علنًا.
