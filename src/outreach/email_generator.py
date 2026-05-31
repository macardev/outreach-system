from __future__ import annotations

import logging
from typing import Any

from google import genai
from google.genai import types

from src.outreach.config import settings

logger = logging.getLogger(__name__)

_SPAM_WORDS = [
    "ücretsiz",
    "garanti",
    "hemen",
    "fırsat",
    "kampanya",
    "indirim",
    "acele",
    "bedava",
    "kaçırma",
]

_SYSTEM_PROMPT = "Sen Türkiye'nin en iyi B2B email copywriter'ısın. Samimi, profesyonel ve spam olmayan mailler yazarsın. Türkçe yaz."


def generate_email(business_data: dict[str, Any]) -> dict[str, str]:
    name = business_data.get("name", "İşletme")
    city = business_data.get("city", "")
    biz_type = business_data.get("type", "")
    rating = business_data.get("rating")
    review_count = business_data.get("review_count", 0)
    website_quality = business_data.get("website_quality", "none")
    pain_point = settings.BUSINESS_PAIN_POINTS.get(
        biz_type, settings.BUSINESS_PAIN_POINTS.get("default", "")
    )

    personalization = []
    if rating and rating >= 4.0:
        personalization.append(
            f"Google'da {rating} puanınız var — harika bir başlangıç"
        )
    if review_count > 20:
        personalization.append(
            f"{review_count} yorumunuz var, bu güveni web sitenize taşıyalım"
        )
    if website_quality in ("wix", "poor", "wordpress_basic", "blogger"):
        personalization.append(
            "Mevcut sitenizi fark ettim, daha güçlü bir yapıya taşıyabiliriz"
        )

    personalization_text = ". ".join(personalization)
    if personalization_text:
        personalization_text = f"\n\nKişisel not: {personalization_text}."

    user_prompt = f"""İşletme: {name}
Şehir: {city}
Tür: {settings.BUSINESS_TYPES_TR.get(biz_type, biz_type)}
Ağrı Noktası: {pain_point}{personalization_text}

ŞİMDİ YUKARIDAKİ İŞLETME İÇİN BİR E-POSTA YAZ.

ÖNCE KONU SATIRINI YAZ, SATIR BAŞINA "KONU: " KOY.
SONRA ALT SATIRA "---" KOY.
SONRA E-POSTA İÇERİĞİNİ YAZ.

Kurallar:
- Konu maksimum 50 karakter
- İçerik maksimum 120 kelime
- Samimi ve profesyonel Türkçe
- Net bir CTA olsun (telefon görüşmesi teklif et)
- Spam kelimeleri kullanma
- İmza kısmını da ekle:
{settings.SENDER_NAME}
{settings.COMPANY_NAME}
{settings.WEBSITE}
{settings.SENDER_PHONE}"""

    try:
        result = _call_gemini(user_prompt)
        subject, body = _parse_gemini_response(result)
    except Exception as e:
        logger.warning("Gemini API error, using template: %s", e)
        subject, body = _template_email(business_data)

    if not subject or not body:
        subject, body = _template_email(business_data)

    subject = _clean_spam_words(subject)
    subject = subject[:50] if len(subject) > 50 else subject

    return {"subject": subject, "body": body}


def generate_subject_lines(business_data: dict[str, Any]) -> str:
    name = business_data.get("name", "")
    city = business_data.get("city", "")

    alternatives = [
        f"{name} için bir fikir?",
        f"{city}'de dijital görünürlük",
        f"{name}, Google'da sizi bulamadım",
    ]

    try:
        prompt = f"""{_SYSTEM_PROMPT}

Bu işletme için 3 farklı email konusu (subject line) üret:
İşletme: {name}
Şehir: {city}
Tür: {settings.BUSINESS_TYPES_TR.get(business_data.get("type", ""), "")}

Her konuyu yeni satırda, numarasız yaz. Maksimum 50 karakter."""
        result = _call_gemini(prompt)
        lines = [line.strip() for line in result.strip().split("\n") if line.strip()]
        if lines:
            alternatives = lines[:3]
    except Exception as e:
        logger.warning("Could not generate subject lines: %s", e)

    return alternatives[0]


def generate_followup_email(
    business_data: dict[str, Any], followup_number: int
) -> dict[str, str]:
    name = business_data.get("name", "İşletme")
    city = business_data.get("city", "")

    if followup_number == 1:
        prompt = f"""İşletme: {name}
Şehir: {city}
Durum: Bu işletmeye daha önce email attık ama cevap alamadık.

NAZİK BİR HATIRLATMA E-POSTASI YAZ.

KONU: ...
---
E-posta içeriği

Ek olarak şunu ekle: "Bu arada benzer bir işletme için yaptığımız siteyi görmek ister misiniz? senninweb.com/referanslar"

Kurallar:
- Konu maksimum 50 karakter
- İçerik maksimum 120 kelime
- Samimi Türkçe, baskı yok
- Net CTA
- İmza:
{settings.SENDER_NAME}
{settings.COMPANY_NAME}
{settings.WEBSITE}
{settings.SENDER_PHONE}"""
    else:
        prompt = f"""İşletme: {name}
Şehir: {city}
Durum: Bu işletmeye 2. kez takip emaili atıyoruz, cevap yok.

SON BİR DENEME, FARKLI AÇIDAN YAKLAŞ.

KONU: ...
---
E-posta içeriği

Şu mesajı ilet: "Belki şu an doğru zaman değildir, ama hazır olduğunuzda buradayım." Kapıyı açık bırak, baskı yapma.

Kurallar:
- Konu maksimum 50 karakter
- İçerik maksimum 120 kelime
- Samimi Türkçe
- Net CTA
- İmza:
{settings.SENDER_NAME}
{settings.COMPANY_NAME}
{settings.WEBSITE}
{settings.SENDER_PHONE}"""

    try:
        result = _call_gemini(prompt)
        subject, body = _parse_gemini_response(result)
    except Exception as e:
        logger.warning("Gemini API error for followup %s: %s", followup_number, e)
        if followup_number == 1:
            subject = f"{name}, bir hatırlatma"
            body = f"Merhaba {name},\n\nGeçen hafta size bir email atmıştım. Belki yoğunsunuzdur, o yüzden kısa bir hatırlatma yapayım.\n\n{settings.COMPANY_NAME} olarak küçük işletmelerin dijital görünürlüğünü artırıyoruz. {city}'deki işletmeniz için neler yapabileceğimizi 15 dakikalık bir görüşmede anlatabilirim.\n\nBu arada benzer bir işletme için yaptığımız siteyi görmek ister misiniz? senninweb.com/referanslar\n\nSevgiler,\n{settings.SENDER_NAME}\n{settings.COMPANY_NAME} — Web Tasarım & SEO\n{settings.WEBSITE}\n{settings.SENDER_PHONE}"
        else:
            subject = f"{name}, kapı açık"
            body = f"Merhaba {name},\n\nSize birkaç haftadır ulaşmaya çalışıyorum. Belki şu an doğru zaman değildir, ama hazır olduğunuzda buradayım.\n\n{settings.COMPANY_NAME} olarak {city}'deki işletmelerin web sitelerini ve Google görünürlüğünü profesyonel bir seviyeye taşıyoruz. Ne zaman isterseniz bir kahve içerken konuşabiliriz.\n\nKapı her zaman açık,\n{settings.SENDER_NAME}\n{settings.COMPANY_NAME} — Web Tasarım & SEO\n{settings.WEBSITE}\n{settings.SENDER_PHONE}"

    subject = _clean_spam_words(subject)
    return {"subject": subject[:50], "body": body}


def _call_gemini(prompt: str) -> str:
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not set")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            max_output_tokens=settings.GEMINI_MAX_TOKENS,
            temperature=settings.GEMINI_TEMPERATURE,
        ),
    )
    return response.text


def _parse_gemini_response(text: str) -> tuple[str, str]:
    subject = ""
    body = ""

    text_upper = text.upper()
    if "KONU:" in text_upper:
        idx = text_upper.index("KONU:")
        after_subject = text[idx + 5 :].strip()
        if "---" in after_subject:
            parts = after_subject.split("---", 1)
            subject = parts[0].strip()
            body = parts[1].strip()
        elif "İÇERİK:" in after_subject:
            parts = after_subject.split("İÇERİK:", 1)
            subject = parts[0].strip()
            body = parts[1].strip()

    if not subject:
        lines = text.strip().split("\n")
        if lines:
            subject = lines[0].strip()
            body = "\n".join(lines[1:]).strip()

    subject = subject.replace("\n", " ").strip()
    subject = " ".join(subject.split())

    return subject[:50], body


def _template_email(business_data: dict[str, Any]) -> tuple[str, str]:
    name = business_data.get("name", "İşletme")
    city = business_data.get("city", "şehriniz")
    biz_type = settings.BUSINESS_TYPES_TR.get(business_data.get("type", ""), "işletme")
    pain_point = settings.BUSINESS_PAIN_POINTS.get(
        business_data.get("type", ""),
        "Potansiyel müşterileriniz sizi Google'da arıyor.",
    )

    subject = f"{name} için dijital bir fikir"

    body = f"""Merhaba {name},

{city}'deki {biz_type} olarak dijital görünürlüğünüzü merak ettim. {pain_point}

{settings.COMPANY_NAME} olarak küçük işletmelerin Google'da bulunmasını ve profesyonel web sitelerine kavuşmasını sağlıyoruz. Size özel bir çözümden bahsetmek isterim.

15 dakikalık bir görüşme yapalım mı?

Sevgiler,
{settings.SENDER_NAME}
{settings.COMPANY_NAME} — Web Tasarım & SEO
{settings.WEBSITE}
{settings.SENDER_PHONE}"""

    return subject, body


def _clean_spam_words(text: str) -> str:
    result = text
    for word in _SPAM_WORDS:
        result = result.replace(word, "***")
    return result
