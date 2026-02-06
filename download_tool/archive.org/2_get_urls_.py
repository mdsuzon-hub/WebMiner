import os
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import time
from datetime import datetime

# =========================
# CONFIG
# =========================
INPUT_JSON = "archive_texts_urls.json"
OUTPUT_JSON = "archive_files_urls.json"
MAX_WORKERS = 8  # Number of concurrent threads

# =========================
# CUSTOM LOGGER WITH PROGRESS BAR SUPPORT
# =========================
class ProgressLogger:
    def __init__(self):
        self.progress_bar = None
        self.stats = {
            "processed": 0,
            "success": 0,
            "no_pdf": 0,
            "no_table": 0,
            "errors": 0
        }
    
    def update_progress(self):
        if self.progress_bar:
            self.progress_bar.set_postfix({
                'OK': self.stats["success"],
                'No PDF': self.stats["no_pdf"],
                'Failed': self.stats["errors"]
            })
    
    def log_info(self, message):
        # Clear progress bar line, print message, then restore progress bar
        if self.progress_bar:
            sys.stdout.write('\r' + ' ' * 100 + '\r')
            print(f"{message}")
            self.progress_bar.refresh()
        else:
            print(f"{message}")
    
    def log_error(self, message):
        self.log_info(f"❌ {message}")

logger = ProgressLogger()

# =========================
# SESSION (ROBUST)
# =========================
session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=2,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
session.mount("https://", HTTPAdapter(max_retries=retries))
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
})

# =========================
# PROCESS SINGLE ITEM (SCRAPE ONLY)
# =========================
def process_item(item, global_index, total_items):
    file_id = item.get("title") or item.get("url")
    base_url = item.get("url")
    result = {
        "file_id": file_id,
        "files": {
            "thumb": None,
            "metadata": None,
            "pdfs": []  # store all PDFs with their names
        }
    }

    try:
        resp = session.get(base_url, timeout=(15, 60))
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")

        if not table:
            logger.stats["no_table"] += 1
            logger.update_progress()
            return None

        for a in table.find_all("a"):
            name = a.text.strip()
            href = a.get("href")
            if not href or name == "Parent Directory":
                continue

            full_url = urljoin(base_url + "/", href)

            if name == "__ia_thumb.jpg":
                result["files"]["thumb"] = full_url
            elif name.endswith("_meta.xml"):
                result["files"]["metadata"] = full_url
            elif name.lower().endswith(".pdf"):
                # Store PDF with both name and URL
                pdf_info = {
                    "name": name,
                    "url": full_url
                }
                result["files"]["pdfs"].append(pdf_info)

        # Skip if no PDFs found
        if not result["files"]["pdfs"]:
            logger.stats["no_pdf"] += 1
            logger.update_progress()
            return None

        logger.stats["success"] += 1
        logger.update_progress()
        return result

    except Exception as e:
        logger.stats["errors"] += 1
        logger.update_progress()
        logger.log_error(f"Error processing {file_id}: {str(e)}")
        return None

# =========================
# MAIN EXECUTION
# =========================
def main():
    print("=" * 60)
    print("FILE URL EXTRACTION STARTED")
    print("=" * 60)
    
    # Load input JSON
    try:
        with open(INPUT_JSON, "r", encoding="utf-8") as f:
            items = json.load(f)
        
        if not isinstance(items, list):
            print(f"ERROR: Input JSON must be a list. Got {type(items)}")
            return
        
        total_items = len(items)
        print(f"Loaded {total_items} items from {INPUT_JSON}")
        
    except FileNotFoundError:
        print(f"ERROR: Input file not found: {INPUT_JSON}")
        return
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {INPUT_JSON}: {e}")
        return
    
    report = {}
    start_time = time.time()
    
    # Initialize tqdm for progress bar (import here to avoid unnecessary dependency)
    try:
        from tqdm import tqdm
        print("\n")  # Empty line before progress bar starts
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # Submit all tasks
            futures = {
                executor.submit(process_item, item, idx+1, total_items): idx
                for idx, item in enumerate(items)
            }
            
            # Create progress bar
            logger.progress_bar = tqdm(
                total=total_items, 
                desc="Processing", 
                unit="item",
                position=0,
                leave=True,
                bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]'
            )
            
            # Process completed futures
            completed = 0
            for future in as_completed(futures):
                idx = futures[future]
                res = future.result()
                
                if res:
                    fid = res["file_id"]
                    
                    # If file_id already exists, append a number to make it unique
                    original_fid = fid
                    counter = 1
                    while fid in report:
                        fid = f"{original_fid}_{counter}"
                        counter += 1

                    report[fid] = res
                
                completed += 1
                logger.progress_bar.update(1)
                logger.update_progress()
            
            # Close progress bar
            logger.progress_bar.close()
            
    except ImportError:
        # Fallback if tqdm is not available
        print("NOTE: tqdm not installed. Using simple progress indicator.")
        print("Install with: pip install tqdm\n")
        
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(process_item, item, idx+1, total_items): idx
                for idx, item in enumerate(items)
            }
            
            completed = 0
            for future in as_completed(futures):
                idx = futures[future]
                res = future.result()
                
                if res:
                    fid = res["file_id"]
                    
                    # If file_id already exists, append a number to make it unique
                    original_fid = fid
                    counter = 1
                    while fid in report:
                        fid = f"{original_fid}_{counter}"
                        counter += 1

                    report[fid] = res
                
                completed += 1
                if completed % 100 == 0:
                    print(f"  Progress: {completed}/{total_items}")
    
    # Calculate processing time
    processing_time = time.time() - start_time
    
    # Save JSON
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # =========================
    # FINAL STATISTICS
    # =========================
    print("\n" + "=" * 60)
    print("PROCESSING STATISTICS:")
    print("=" * 60)
    
    # Calculate some additional statistics
    total_pdfs = 0
    for item in report.values():
        total_pdfs += len(item["files"]["pdfs"])
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"{timestamp} - INFO -    Total items processed: {total_items}")
    print(f"{timestamp} - INFO -    Successfully extracted: {logger.stats['success']}")
    print(f"{timestamp} - INFO -    Items without PDF: {logger.stats['no_pdf']}")
    print(f"{timestamp} - INFO -    Items without table: {logger.stats['no_table']}")
    print(f"{timestamp} - INFO -    Failed items: {logger.stats['errors']}")
    print(f"{timestamp} - INFO -    Total PDFs found: {total_pdfs}")
    print(f"{timestamp} - INFO -    Average PDFs per item: {total_pdfs/max(1, len(report)):.2f}")
    
    print(f"\n⏱️  Processing time: {processing_time:.1f} seconds ({processing_time/60:.1f} minutes)")
    print(f"📄 Items with PDFs saved: {len(report)}")
    print(f"📊 Total PDF files collected: {total_pdfs}")
    print(f"💾 Output saved to: {OUTPUT_JSON}")
    print("=" * 60)
    print("🎉 DONE! JSON report saved successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()