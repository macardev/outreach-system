"""Setup credentials from base64-encoded environment variables."""
import os, base64

def write_file_from_b64(path: str, env_var: str) -> None:
    encoded = os.environ.get(env_var, "")
    if not encoded:
        print(f"WARNING: {env_var} is empty!")
        return
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
        with open(path, "w") as f:
            f.write(decoded)
        size = os.path.getsize(path)
        print(f"Written {path} ({size} bytes)")
    except Exception as e:
        print(f"ERROR decoding {env_var}: {e}")

print("=== Setting up .env ===")
with open(".env", "w") as f:
    f.write(f'GOOGLE_MAPS_API_KEY="{os.environ.get("GOOGLE_MAPS_API_KEY", "")}"\n')
    f.write(f'GEMINI_API_KEY="{os.environ.get("GEMINI_API_KEY", "")}"\n')
    f.write(f'SPREADSHEET_ID="{os.environ.get("SPREADSHEET_ID", "")}"\n')
    f.write(f'SENDER_NAME="{os.environ.get("SENDER_NAME", "")}"\n')
    f.write(f'SENDER_EMAIL="{os.environ.get("SENDER_EMAIL", "")}"\n')
    f.write(f'WARMUP_START_DATE="{os.environ.get("WARMUP_START_DATE", "")}"\n')

print("=== Setting up JSON files from base64 ===")
write_file_from_b64("credentials.json", "CREDENTIALS_JSON")
write_file_from_b64("token.json", "GMAIL_TOKEN_JSON")
write_file_from_b64("sheets_token.json", "SHEETS_TOKEN_JSON")

print("=== Setup complete ===")
