import os
import re
import time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup


def find_download_form(soup, page_url):
    """
    The page has multiple <form> elements (e.g. a Google Custom Search box
    whose action is https://www.google.com/cse). Picking the first form
    grabs that search form instead of the real download form, which is
    why every request was 404'ing against google.com/cse.

    This walks all forms and skips anything that isn't the real one.
    """
    forms = soup.find_all("form")

    for form in forms:
        action = form.get("action", "") or ""

        # Skip Google Custom Search / any obviously unrelated 3rd-party form
        if "google.com" in action.lower():
            continue

        # Prefer forms that actually contain a download-looking submit button
        inputs = form.find_all("input")
        has_download_btn = any(
            (inp.get("name", "").lower() in ("dlbtn", "download", "op"))
            or ("download" in (inp.get("value", "") or "").lower())
            for inp in inputs
        )

        if has_download_btn:
            return form

    # Fallback: return the last non-google form found, if any
    non_google_forms = [
        f for f in forms if "google.com" not in (f.get("action", "") or "").lower()
    ]
    if non_google_forms:
        return non_google_forms[-1]

    return None


def download_mp3s():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    urls_file = os.path.join(script_dir, "urls.txt")
    output_dir = os.path.join(script_dir, "audio")

    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(urls_file):
        print(f"[ERROR] Could not find '{urls_file}'. Please run crawler.py first.")
        return

    with open(urls_file, "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    print(f"=== SoundSip MP3 Downloader ===")
    print(f"[+] Loaded {len(urls)} URLs from urls.txt")
    print(f"[+] Save location: {output_dir}\n")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )
    }

    with requests.Session() as session:
        session.headers.update(headers)

        for index, file_page_url in enumerate(urls, start=1):
            print(f"[{index}/{len(urls)}] Processing: {file_page_url}")

            try:
                res = session.get(file_page_url, timeout=15)
                res.raise_for_status()

                soup = BeautifulSoup(res.text, "html.parser")
                form = find_download_form(soup, file_page_url)

                if not form:
                    print("    └── [SKIP] No valid download form found on this page.")
                    continue

                action_url = form.get("action", file_page_url)
                if not action_url.startswith("http"):
                    action_url = urljoin(file_page_url, action_url)

                payload = {}
                for input_tag in form.find_all("input"):
                    name = input_tag.get("name")
                    value = input_tag.get("value", "")
                    if name:
                        payload[name] = value

                dl_response = session.post(
                    action_url, data=payload, stream=True, timeout=60
                )
                dl_response.raise_for_status()

                # Sanity check: make sure we actually got a file, not an HTML page
                content_type = dl_response.headers.get("Content-Type", "")
                if "text/html" in content_type.lower():
                    print(f"    └── [SKIP] Server returned HTML, not audio (form/action may be wrong).")
                    continue

                filename = None
                content_disp = dl_response.headers.get("Content-Disposition")
                if content_disp and "filename=" in content_disp:
                    filename = re.findall(r'filename="?([^";]+)"?', content_disp)[0]
                else:
                    submit_val = payload.get("dlbtn", "")
                    if "Download " in submit_val:
                        filename = submit_val.replace("Download ", "").strip()

                if not filename or not filename.endswith(".mp3"):
                    filename = f"file_{index}.mp3"

                save_path = os.path.join(output_dir, filename)

                if os.path.exists(save_path):
                    print(f"    └── [EXISTS] Skipping '{filename}'")
                    continue

                print(f"    └── Downloading '{filename}'...")
                with open(save_path, "wb") as file:
                    for chunk in dl_response.iter_content(chunk_size=8192):
                        if chunk:
                            file.write(chunk)

                print(f"    └── [DONE] Saved to audio/{filename}")

            except Exception as e:
                print(f"    └── [ERROR] Failed to download: {e}")

            time.sleep(1)


if __name__ == "__main__":
    download_mp3s()