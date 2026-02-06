# Archive Downloader

A set of Python scripts to download text and file URLs from Archive.org, either via GUI or CLI.

## Files

- **1_get_texts.py**  
  Downloads text URL data (`archive_texts_urls.json`).

- **2_get_urls_.py**  
  Downloads file URL data (`archive_files_urls.json`).

- **gui_download.py**  
  Downloads files using a graphical interface.

- **cli_download.py**  
  Downloads files via the command line.

## Requirements

- Python 3.x
- `requests` library
- `tkinter` (for GUI)

## Usage

### CLI Scripts
```bash
python texts_download.py
python files_download.py
python cli_download.py
