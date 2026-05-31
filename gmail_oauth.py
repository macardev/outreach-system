#!/usr/bin/env python3
import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
flow.redirect_uri = "http://localhost:8080/"

auth_url, _ = flow.authorization_url(
    access_type="offline",
    include_granted_scopes="true",
    prompt="consent",
)

print("=" * 60)
print("SU LINKI TARAYICINDA AC:")
print("=" * 60)
print(auth_url)
print("=" * 60)
print()
print("Yetki verdikten sonra, tarayici localhost:8080'a yonlenecek.")
print("O SAYFANIN ADRES CUBUGUNDAKI TAM URL'YI KOPYALA")
print("ve asagidaki dosyaya yapistir:")
print()
print("  echo 'URL' > /tmp/oauth_url.txt")
print()
print("Sonra bu script devam etsin diye ENTER'a bas...")
input("Bekleniyor...")

with open("/tmp/oauth_url.txt") as f:
    redirect_url = f.read().strip()

flow.fetch_token(authorization_response=redirect_url)
creds = flow.credentials

with open("token.json", "w") as f:
    f.write(creds.to_json())
print("Token saved to token.json!")
