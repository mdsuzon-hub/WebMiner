# Downloads text URL data (archive_texts_urls.json)

import requests
import json
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from tqdm import tqdm  # <-- progress bar library

# ------------------------------ Adcance search ------------------------------
# 
# collection=
# subject=
# creator=
# year=
# language=  ben → Bangla   
#            eng → English
#            spa → Spanish
#            urd → Urdu
#            hin → Hindi
#            ara → Arabic
# 
# mediatype= texts        → books, PDFs, magazines, papers, documents
#            audio        → music, audiobooks, lectures, spoken word
#            movies       → videos, films, TV shows, documentaries
#            image        → photos, artwork, scans, illustrations
#            software     → programs, games, ROMs, utilities
#            data         → datasets, research data, archives
#            collection   → collection pages (not actual files)
#            etree        → live concert recordings (Live Music Archive)
#            web          → archived web pages / web captures             
# 
# -- pdf --
# collection:robarts AND subject:"Art"
# collection:robarts AND subject:"Art" AND language:eng
# collection:robarts AND subject:"Art" AND language:eng AND mediatype:texts
# 
# title:(Tintin) AND mediatype:(texts)
# 
# -- mp3 --
# collection:audio_bookspoetry AND subject:"audiobooks" AND language:eng AND mediatype:audio
# collection:audio_bookspoetry AND subject:"audiobooks" AND language:eng AND mediatype:audio AND year:2015

SEARCH = "collection:robarts AND subject:\"Art\" AND mediatype:texts"   #     <----- Search Query
TYPE = "texts"                                    #     <----- Media Type

MAX_RESULTS = 4000
ROWS = 100
OUTPUT_FILE = "archive_texts_urls.json"

results = []
page = 1

# Set up session with retries
session = requests.Session()
retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('https://', HTTPAdapter(max_retries=retries))

# Use tqdm with total MAX_RESULTS to show progress
with tqdm(total=MAX_RESULTS, desc="Fetching Archive.org texts") as pbar:
    while len(results) < MAX_RESULTS:
        url = f"https://archive.org/advancedsearch.php?q={SEARCH}&fl[]=identifier,title,mediatype&rows={ROWS}&page={page}&output=json"
        
        try:
            resp = session.get(url, timeout=10)  # timeout after 10 seconds
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.RequestException as e:
            print(f"⚠️ Request failed on page {page}: {e}")
            break  # stop if repeated failures occur

        docs = data.get("response", {}).get("docs", [])
        if not docs:
            break
        
        for doc in docs:
            identifier = doc.get("identifier")
            title = doc.get("title")
            mediatype = doc.get("mediatype")
            
            if identifier and title and mediatype == TYPE:
                results.append({
                    "title": title,
                    "url": f"https://archive.org/download/{identifier}"
                })
                pbar.update(1)  # update progress bar for each added item

            if len(results) >= MAX_RESULTS:
                break
        
        page += 1

# save JSON
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"✅ Done! Collected {len(results)} text/PDF items.")