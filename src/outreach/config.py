from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API Keys
    GOOGLE_MAPS_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # Google OAuth
    GMAIL_CREDENTIALS_PATH: str = "credentials.json"
    GMAIL_TOKEN_PATH: str = "token.json"
    SHEETS_TOKEN_PATH: str = "sheets_token.json"

    # Google Sheets
    SPREADSHEET_ID: str = ""

    # Sender Info
    SENDER_NAME: str = "Çağatay Macar"
    SENDER_EMAIL: str = "outreach@senninweb.com"
    SENDER_PHONE: str = "+90 (531) 405 15 84"
    WEBSITE: str = "senninweb.com"
    COMPANY_NAME: str = "Sennin Web"

    # Target Configuration
    TARGET_CITIES: list[str] = [
        "Bilecik",
        "Bozüyük",
        "Osmaneli",
        "İznik",
        "Gemlik",
        "Bursa",
        "İstanbul",
        "Kadıköy",
        "Beşiktaş",
        "Şişli",
        "Beyoğlu",
        "Üsküdar",
        "Maltepe",
        "Pendik",
        "Kocaeli",
        "İzmit",
        "Gebze",
        "Darıca",
        "Çayırova",
    ]

    TARGET_BUSINESS_TYPES: list[str] = [
        "diş kliniği",
        "avukat",
        "gayrimenkul danışmanı",
        "restoran",
        "güzellik salonu",
        "muhasebeci",
        "veteriner",
        "fizyoterapist",
        "psikolog",
    ]

    # Website Priority Scoring
    WEBSITE_PRIORITY: dict[str, int] = {
        "none": 100,
        "wix": 75,
        "blogger": 70,
        "wordpress_basic": 65,
        "poor": 60,
        "average": 30,
        "good": 0,
    }

    MIN_PRIORITY_SCORE: int = 60
    MIN_DAYS_BETWEEN_CONTACTS: int = 30

    # Send Configuration
    SEND_HOURS: list[int] = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
    RANDOM_DELAY_MIN: int = 45
    RANDOM_DELAY_MAX: int = 120
    MAX_EMAILS_PER_DAY: int = 50
    ALLOW_WEEKEND_SENDING: bool = False

    # Email Warmup
    WARMUP_MODE: bool = True
    WARMUP_START_DATE: str = ""
    WARMUP_SCHEDULE: dict[str, int] = {
        "1": 10,
        "2": 20,
        "3": 35,
        "4": 50,
    }

    # Google Maps API
    MAPS_RADIUS_KM: int = 10
    MAPS_SEARCH_LIMIT: int = 60
    MAPS_PLACE_TYPE: str = "establishment"

    # Gemini API
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_MAX_TOKENS: int = 2048
    GEMINI_TEMPERATURE: float = 0.7

    # Logging
    LOG_FILE: str = "outreach.log"
    LOG_MAX_BYTES: int = 10 * 1024 * 1024
    LOG_BACKUP_COUNT: int = 3

    # Local Backup
    LOCAL_BACKUP_FILE: str = "local_backup.json"

    # Scoring Weights
    SCORE_NO_WEBSITE: int = 40
    SCORE_POOR_WEBSITE: int = 25
    SCORE_HIGH_RATING: int = 20
    SCORE_MANY_REVIEWS: int = 15
    SCORE_HAS_EMAIL: int = 25
    SCORE_VERY_MANY_REVIEWS: int = 10

    # Follow-up Timing (days)
    FOLLOWUP_1_DELAY: int = 3
    FOLLOWUP_2_DELAY: int = 4
    COLD_AFTER_DAYS: int = 7
    REACTIVATE_AFTER_DAYS: int = 30

    REPORT_DIR: str = "reports"

    BUSINESS_TYPES_TR: dict[str, str] = {
        "diş kliniği": "Diş Kliniği",
        "avukat": "Avukat",
        "gayrimenkul danışmanı": "Gayrimenkul Danışmanı",
        "restoran": "Restoran",
        "güzellik salonu": "Güzellik Salonu",
        "muhasebeci": "Muhasebeci",
        "veteriner": "Veteriner",
        "fizyoterapist": "Fizyoterapist",
        "psikolog": "Psikolog",
    }

    BUSINESS_PAIN_POINTS: dict[str, str] = {
        "diş kliniği": "Hastalar Google'da diş hekimi arıyor, eğer siz çıkmazsanız rakibinize gidiyorlar.",
        "avukat": "İnsanlar Google'da avukat ararken ilk 3 sonuçla çalışıyor.",
        "gayrimenkul danışmanı": "Emlak alıcıları önce Google'da araştırma yapıyor, sosyal medyada değil.",
        "restoran": "Aç olan insanlar nerede yiyeceklerini bulmak için Instagram değil Google Haritalar'ı açıyor.",
        "güzellik salonu": "Kadınlar karar vermeden önce Google'da 'güzellik salonu [şehir]' arıyor.",
        "muhasebeci": "İşletme sahipleri Google'da muhasebeci ararken ilk sıradakini tercih ediyor.",
        "veteriner": "Evcil hayvan sahipleri acil durumlarda Google'da en yakın veterineri arıyor.",
        "fizyoterapist": "Hastalar Google'da fizyoterapist araştırması yaparak karar veriyor.",
        "psikolog": "İnsanlar Google'da psikolog ararken profesyonel bir web sitesi güven veriyor.",
    }


settings = Settings()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
