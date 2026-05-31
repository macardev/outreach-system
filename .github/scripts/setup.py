"""Setup credentials from environment variables for GitHub Actions."""
import os, json

def write_file(path: str, env_var: str) -> None:
    value = os.environ.get(env_var, "")
    if not value:
        print(f"WARNING: {env_var} is empty!")
    with open(path, "w") as f:
        f.write(value)
    size = os.path.getsize(path)
    print(f"Written {path} ({size} bytes)")

print("=== Setting up .env ===")
with open(".env", "w") as f:
    f.write(f'GOOGLE_MAPS_API_KEY="{os.environ.get("GOOGLE_MAPS_API_KEY", "")}"\n')
    f.write(f'GEMINI_API_KEY="{os.environ.get("GEMINI_API_KEY", "")}"\n')
    f.write(f'SPREADSHEET_ID="{os.environ.get("SPREADSHEET_ID", "")}"\n')
    f.write(f'SENDER_NAME="{os.environ.get("SENDER_NAME", "")}"\n')
    f.write(f'SENDER_EMAIL="{os.environ.get("SENDER_EMAIL", "")}"\n')
    f.write(f'WARMUP_START_DATE="{os.environ.get("WARMUP_START_DATE", "")}"\n')

print("=== Setting up credentials.json ===")
write_file("credentials.json", "CREDENTIALS_JSON")

print("=== Setting up token.json ===")
write_file("token.json", "GMAIL_TOKEN_JSON")

print("=== Setting up sheets_token.json ===")
write_file("sheets_token.json", "SHEETS_TOKEN_JSON")

print("=== Setup complete ===")
