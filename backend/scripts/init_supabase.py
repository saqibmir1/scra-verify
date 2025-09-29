import os
import sys
from supabase import create_client

BUCKET_NAME = "verification-files"

def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY (or SUPABASE_SERVICE_ROLE_KEY) must be set", file=sys.stderr)
        sys.exit(1)

    client = create_client(url, key)

    # 1) Ensure bucket exists
    try:
        client.storage.from_(BUCKET_NAME).list("", {"limit": 1})
        print(f"Bucket '{BUCKET_NAME}' already exists and is accessible")
    except Exception as e:
        print(f"Bucket '{BUCKET_NAME}' not accessible: {e}. Creating...")
        try:
            client.storage.create_bucket(BUCKET_NAME, {
                "public": False,
                "allowedMimeTypes": ["image/png", "image/jpeg", "application/pdf"],
                "fileSizeLimit": 10485760,
            })
            # Validate
            client.storage.from_(BUCKET_NAME).list("", {"limit": 1})
            print(f"Created bucket '{BUCKET_NAME}' successfully")
        except Exception as ce:
            print(f"ERROR: Failed to create bucket '{BUCKET_NAME}': {ce}", file=sys.stderr)
            sys.exit(1)

    print("Supabase initialization complete")

if __name__ == "__main__":
    main()


