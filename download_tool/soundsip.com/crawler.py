import os
import re
import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
import requests
from bs4 import BeautifulSoup


def build_page_url(base_url, page_num):
    """Updates or appends the page parameter in the URL query string."""
    parsed = urlparse(base_url)
    query_params = parse_qs(parsed.query)
    query_params["page"] = [str(page_num)]

    # Reconstruct query
    new_query = urlencode(query_params, doseq=True)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )


def extract_urls():
    print("=== SoundSip URL Collector ===")
    base_url = input("Enter Base URL: ").strip()
    start_page = int(input("Enter Starting Page (e.g., 1): ").strip())
    end_page = int(input("Enter Ending Page (e.g., 49): ").strip())

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_filepath = os.path.join(script_dir, "urls.txt")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )
    }

    found_urls = []

    print(
        f"\n[+] Starting scraping from page {start_page} to {end_page}...\n"
    )

    with requests.Session() as session:
        session.headers.update(headers)

        for page in range(start_page, end_page + 1):
            target_url = build_page_url(base_url, page)
            print(f"[FETCHING] Page {page}/{end_page}: {target_url}")

            try:
                response = session.get(target_url, timeout=15)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")

                # Links are inside <div class="col1"> -> <div class="link"> -> <a>
                page_links = 0
                for div_link in soup.find_all("div", class_="link"):
                    a_tag = div_link.find("a", href=True)
                    if a_tag:
                        full_url = a_tag["href"]
                        if not full_url.startswith("http"):
                            full_url = "https://soundsip.com/" + full_url.lstrip(
                                "/"
                            )

                        found_urls.append(full_url)
                        page_links += 1

                print(f"    └── Found {page_links} URLs on page {page}.")

            except Exception as e:
                print(f"    └── [ERROR] Failed to fetch page {page}: {e}")

            # Friendly delay to avoid overloading server
            time.sleep(0.5)

    # Save to urls.txt
    with open(output_filepath, "w", encoding="utf-8") as f:
        for url in found_urls:
            f.write(f"{url}\n")

    print(f"\n[SUCCESS] Saved {len(found_urls)} URLs to: {output_filepath}")


if __name__ == "__main__":
    extract_urls()