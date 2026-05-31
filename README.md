# Outreach System — B2B Email Outreach Automation

Türkiye'deki küçük işletmelere (web sitesi olmayan veya kötü web sitesi olan) kişiselleştirilmiş outreach e-postaları göndermek için otomatik sistem.

**Hedef:** 15 gün içinde ilk ödeme yapan müşteriyi kazanmak.

---

## 📋 İçindekiler

1. [Google Cloud Console Kurulumu](#1-google-cloud-console-kurulumu)
2. [Gemini API Key](#2-gemini-api-key)
3. [OAuth Credentials İndirme](#3-oauth-credentials)
4. [Kurulum Adımları](#4-kurulum)
5. [İlk Çalıştırma](#5-ilk-çalıştırma)
6. [Günlük Kullanım](#6-günlük-kullanım)
7. [Otomatik Zamanlama](#7-cronjob-kurulumu)
8. [Sorun Giderme](#8-sorun-giderme)

---

## 1. Google Cloud Console Kurulumu

### Adım 1: Proje Oluştur
1. [Google Cloud Console](https://console.cloud.google.com/)'a git
2. Üst taraftaki proje seçiciye tıkla → **Yeni Proje**
3. Proje adı: `outreach-system` (veya dilediğin)
4. **Oluştur**'a tıkla

### Adım 2: API'leri Aktifleştir
Aşağıdaki API'leri sırayla aktifleştir:

1. **Google Maps API**
   - [Google Maps API](https://console.cloud.google.com/apis/library/places-backend.googleapis.com)
   - → **Enable**

2. **Gmail API**
   - [Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com)
   - → **Enable**

3. **Google Sheets API**
   - [Google Sheets API](https://console.cloud.google.com/apis/library/sheets.googleapis.com)
   - → **Enable**

4. **PageSpeed Insights API**
   - [PageSpeed Insights API](https://console.cloud.google.com/apis/library/pagespeedonline.googleapis.com)
   - → **Enable**

### Adım 3: Credentials (API Key) Oluştur
1. **API Key** oluşturmak için:
   - [Credentials](https://console.cloud.google.com/apis/credentials) sayfasına git
   - **+ Create Credentials** → **API Key**
   - Anahtarı kopyala, bir yere not et
   - **Edit API Key** → "API restrictions" → **Restrict key** ve sadece şunları seç:
     - Places API
     - PageSpeed Insights API
   - **Save**

---

## 2. Gemini API Key

1. [Google AI Studio](https://aistudio.google.com/app/apikey)'ye git
2. Google hesabınla giriş yap
3. **Create API Key**'e tıkla
4. Anahtarı kopyala, bir yere not et

---

## 3. OAuth Credentials

Gmail ve Google Sheets API'leri OAuth 2.0 Authentication gerektirir.

### OAuth Consent Screen
1. [OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent) sayfasına git
2. **External** → **Create**
3. **App name:** `Outreach System`
4. **User support email:** kendi email'ini seç
5. **Developer contact:** kendi email'ini gir
6. **Save and Continue**
7. **Scopes** sayfasında → **Add or Remove Scopes** → şunları ekle:
   - `.../auth/gmail.send`
   - `.../auth/gmail.modify`
   - `.../auth/spreadsheets`
8. **Test users** sayfasında → **Add Users** → kendi email'ini ve hedef email'ini ekle

### Credentials JSON İndir
1. [Credentials](https://console.cloud.google.com/apis/credentials) sayfasına git
2. **+ Create Credentials** → **OAuth Client ID**
3. **Application type:** **Desktop app**
4. **Name:** `Outreach Desktop`
5. **Create**
6. **Download JSON** butonuna tıkla
7. Dosyayı `credentials.json` olarak **proje ana klasörüne** kaydet

### Google Sheets ID Bulma
1. [Google Sheets](https://sheets.google.com/)'e git
2. **+** butonuyla yeni bir boş sayfa oluştur
3. URL'deki ID'yi kopyala:
   ```
   https://docs.google.com/spreadsheets/d/XXXXXXXXXXXXXXXXXXX/edit
   ```
   `XXXXXXXXXXXXXXXXXXX` kısmı **SPREADSHEET_ID**

---

## 4. Kurulum

### Gereksinimler
- Python 3.10+
- uv (hızlı Python paket yöneticisi)

### uv Kurulumu
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Proje Kurulumu
```bash
# Proje dizinine git
cd outreach-system

# Bağımlılıkları yükle
uv sync

# (Opsiyonel) Doğrula
uv run python -c "from src.outreach.config import settings; print('OK')"
```

### .env Dosyası Oluştur
```bash
# Kurulum sihirbazını çalıştır
uv run python main.py --setup
```

Alternatif olarak `.env` dosyasını manuel oluştur:

```env
GOOGLE_MAPS_API_KEY="AIza..."
GEMINI_API_KEY="AI..."
SPREADSHEET_ID="XXXXXXXXXXXXXXXXXXX"
SENDER_NAME="Çağatay Macar"
SENDER_EMAIL="outreach@senninweb.com"
WARMUP_START_DATE="2025-05-12"
```

---

## 5. İlk Çalıştırma

### Adım 1: Warmup Durumunu Kontrol Et
```bash
uv run python main.py --mode warmup-status
```

### Adım 2: Scrape Testi (API Anahtarı Gerekli)
```bash
uv run python main.py --mode scrape --city "Bilecik" --type "diş kliniği" --limit 5
```

İlk çalıştırmada Gmail OAuth penceresi açılacak → Google hesabınla giriş yap → **Continue** → **Continue** (uyarıları geç).

### Adım 3: Gönderim Testi
```bash
# Günlük limit kadar email gönder
uv run python main.py --mode send
```

### Adım 4: Dashboard'u Görüntüle
```bash
uv run python main.py --mode report
```

---

## 6. Günlük Kullanım

### Scrape Modları

```bash
# Tek şehir + tek tip
python main.py --mode scrape --city "Bilecik" --type "diş kliniği" --limit 50

# Tüm şehirler x tüm tipler
python main.py --mode scrape-all

# Belirli şehir
python main.py --mode scrape --city "İstanbul" --type "avukat" --limit 100
```

### Send Modu

```bash
# Otomatik (warmup limitini kullanır)
python main.py --mode send

# Minimum skor 70+ olanlara gönder
python main.py --mode send --min-score 70
```

### Follow-up

```bash
python main.py --mode followup
```

### Rapor

```bash
python main.py --mode report
```

---

## 7. Cronjob Kurulumu

### Linux (crontab)

```bash
crontab -e
```

Şu satırları ekle:

```cron
# Hafta içi her gün çalıştır
30 8 * * 1-5 cd /path/to/outreach-system && uv run python main.py --mode scrape-all --limit 30 >> outreach.log 2>&1
0 9 * * 1-5 cd /path/to/outreach-system && uv run python main.py --mode send >> outreach.log 2>&1
0 13 * * 1-5 cd /path/to/outreach-system && uv run python main.py --mode send >> outreach.log 2>&1
0 18 * * 1-5 cd /path/to/outreach-system && uv run python main.py --mode followup >> outreach.log 2>&1
0 19 * * 1-5 cd /path/to/outreach-system && uv run python main.py --mode report >> outreach.log 2>&1
```

### Windows (Görev Zamanlayıcı)

1. **Task Scheduler**'ı aç
2. **Create Basic Task**
3. Ad: `Outreach Morning Send`
4. Trigger: Daily, 09:00
5. Action: Start a program
   - Program: `python.exe`
   - Arguments: `main.py --mode send`
   - Start in: `C:\...\outreach-system`

---

## 8. Sorun Giderme

### "No module named 'src'"
```bash
# Proje kök dizininde olduğundan emin ol
cd outreach-system
uv run python main.py --mode warmup-status
```

### "GMAIL_API_KEY is not set"
```bash
# .env dosyasını kontrol et
cat .env
# Setup sihirbazını yeniden çalıştır
python main.py --setup
```

### "Google Maps API quota exceeded"
- API anahtarının kısıtlamalarını kontrol et
- Google Cloud Console'dan kota artışı iste
- Sistem otomatik bekler, bir sonraki gün devam eder

### "Sheets OAuth failed"
- `credentials.json` dosyası proje ana dizininde mi?
- `token.json`'ı sil, yeniden dene (yeniden yetkilendirme açılır)

### "Rate limit exceeded" (Gmail)
- Sistem otomatik olarak 60 saniye bekler
- Warmup modunu kontrol et (hafta 4+ olmalı)
- Gmail API kotanı kontrol et

### Email gönderilmiyor
- `--mode warmup-status` ile günlük limiti kontrol et
- Saat dilimini kontrol et (SEND_HOURS: 9, 10, 13, 14)
- Hafta içinde olup olmadığını kontrol et

### Log dosyası
Tüm işlemler `outreach.log` dosyasına kaydedilir:

```bash
# Son 20 satırı göster
tail -20 outreach.log

# Hataları filtrele
grep -i error outreach.log
```

---

## 🔧 Mimarisi

```
main.py                  # CLI giriş noktası
src/outreach/
├── config.py            # Tüm yapılandırma (pydantic-settings)
├── warmup.py            # Email ısındırma yöneticisi
├── scraper.py           # Google Maps ile işletme keşfi
├── email_generator.py   # Gemini AI ile içerik üretimi
├── gmail_sender.py      # Gmail API ile gönderim
├── sheets_manager.py    # Google Sheets takibi
└── follow_up.py         # Otomatik takip sistemi
```

### Veri Akışı

```
1. Scrape → Google Maps API → İşletme verileri
2. Score → Web sitesi kalitesi + puan hesaplama
3. Filter → Daha önce iletişime geçilmeyenler
4. Generate → Gemini AI → Kişisel email
5. Queue → Warmup limiti kontrolü
6. Send → Gmail API → HTML email
7. Track → Google Sheets → Tüm veriler
8. Follow-up → 3. ve 7. günlerde otomatik takip
```

---

## ⚙️ Teknolojiler

- **Python 3.10+** — Ana geliştirme dili
- **uv** — Hızlı bağımlılık yöneticisi
- **Google Maps API** — İşletme keşfi
- **Google Gemini AI** — Email içeriği
- **Gmail API** — Email gönderimi
- **Google Sheets API** — Veri takibi
- **Rich** — Terminal çıktıları
- **Pydantic** — Yapılandırma yönetimi

---

**Made with ❤️ for Turkish small businesses**
