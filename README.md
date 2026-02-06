<!-- ========================================= -->
<!--            🚀 PROJECT README UI          -->
<!-- ========================================= -->

<h1 align="center">⚡ WebScrapeHub</h1>
<p align="center">
  <b>Smart Web Scraper & Downloader</b><br>
  Fast • Automated • Powerful • Clean CLI Experience
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0-blue">
  <img src="https://img.shields.io/badge/python-3.x-green">
  <img src="https://img.shields.io/badge/platform-windows%20%7C%20linux-lightgrey">
  <img src="https://img.shields.io/badge/status-active-success">
</p>

---

## ✨ Overview

WebScrapeHub is a powerful tool that allows users to scrape data from websites and download files automatically.  
Built for speed and automation, it helps collect documents, media, metadata, and structured data efficiently.

--------------------------------------------------
⚙️ FEATURES
--------------------------------------------------
- Website scraping automation
- Bulk file downloading
- Multithreaded performance
- CLI and GUI support
- JSON-based workflow
- Organized downloads folder
- Progress tracking
- Error handling and retry system
- Filter by file type or category

--------------------------------------------------
📂 PROJECT STRUCTURE
--------------------------------------------------

```text
WebScrapeHub/
│
├── 📁 archive.org
│   ├── 📄 1_texts_urls_download.py    # Scrapes & extracts text-based links
│   └── 📄 2_files_urls_download.py    # Handles media & document discovery
│
├── 📁 Interfaces
│   ├── 📄 gui_download.py             # Graphical User Interface (Tkinter/PyQt)
│   └── 📄 cli_download.py             # Command Line Interface (Argparse)
│
├── 📁 Data Storage
│   ├── 📄 archive_texts_urls.json     # Database of discovered text links
│   └── 📄 archive_files_urls.json     # Database of discovered file links
│
└── 📁 Output
    └── 📂 downloads/                  # 📥 Target folder for all downloaded assets

```

--------------------------------------------------
▶️ USAGE
--------------------------------------------------

Step 1 – Fetch Text or Item URLs
python 1_texts_urls_download.py

Step 2 – Extract File URLs
python 2_files_urls_download.py

Step 3 – Download Files using CLI
python cli_download.py

Step 4 – Download Files using GUI
python gui_download.py

--------------------------------------------------
📦 SUPPORTED CONTENT
--------------------------------------------------
- PDF Documents
- Images
- Audio Files
- Video Files
- Metadata
- Thumbnails
- Text Files

--------------------------------------------------
⚡ CONFIGURATION
--------------------------------------------------
Edit configuration inside scripts:

MAX_WORKERS = 8
SEARCH = "your search query"
OUTPUT_FILE = "output.json"

--------------------------------------------------
🛡 DISCLAIMER
--------------------------------------------------
This tool is intended for educational, research, and legal data
collection purposes only. Always respect copyright laws and
website terms of service when scraping or downloading content.

--------------------------------------------------
⭐ LICENSE
--------------------------------------------------
MIT License © 2026

--------------------------------------------------
⚡ Built for Developers • Automation • Data Collection
--------------------------------------------------
