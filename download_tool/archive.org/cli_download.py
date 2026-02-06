#!/usr/bin/env python3
"""
Advanced Archive Downloader - Terminal Version (Without Pre-Sizing)
High-performance, multithreaded downloader with detailed logging and progress bars
"""

import os
import json
import requests
import threading
import time
import sys
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Terminal UI
from tqdm import tqdm
from colorama import init, Fore, Back, Style
import signal

SUBJECT = "Art"

# =========================
# CONFIGURATION
# =========================
class Config:
    INPUT_JSON = "archive_files_urls.json"
    BASE_DIR = "download"
    MAX_WORKERS = 10  # More threads for terminal version
    CHUNK_SIZE = 65536  # 64KB chunks
    TIMEOUT = (10, 60)  # (connect timeout, read timeout)
    MAX_RETRIES = 3
    CONNECTION_POOL = 50
    SPEED_SMOOTHING = 5
    
    FOLDERS = {
        "thumb": "thumb",
        "metadata": "metadata",
        "pdf": "pdf"  # All PDFs go here
    }
    
    # Colors for terminal
    COLORS = {
        "header": Fore.CYAN + Style.BRIGHT,
        "success": Fore.GREEN,
        "warning": Fore.YELLOW,
        "error": Fore.RED,
        "info": Fore.BLUE,
        "download": Fore.MAGENTA,
        "progress": Fore.CYAN,
        "reset": Style.RESET_ALL
    }

# =========================
# TERMINAL UI UTILITIES
# =========================
class TerminalUI:
    """Handles all terminal display and formatting"""
    
    @staticmethod
    def clear_line():
        """Clear current line in terminal"""
        sys.stdout.write("\033[K")
        sys.stdout.flush()
    
    @staticmethod
    def move_up(lines=1):
        """Move cursor up specified number of lines"""
        sys.stdout.write(f"\033[{lines}A")
        sys.stdout.flush()
    
    @staticmethod
    def move_down(lines=1):
        """Move cursor down specified number of lines"""
        sys.stdout.write(f"\033[{lines}B")
        sys.stdout.flush()
    
    @staticmethod
    def print_header(text):
        """Print formatted header"""
        print(f"\n{Config.COLORS['header']}{'='*60}")
        print(f"{text:^60}")
        print(f"{'='*60}{Config.COLORS['reset']}\n")
    
    @staticmethod
    def print_success(text):
        """Print success message"""
        print(f"{Config.COLORS['success']}✅ {text}{Config.COLORS['reset']}")
    
    @staticmethod
    def print_warning(text):
        """Print warning message"""
        print(f"{Config.COLORS['warning']}⚠️  {text}{Config.COLORS['reset']}")
    
    @staticmethod
    def print_error(text):
        """Print error message"""
        print(f"{Config.COLORS['error']}❌ {text}{Config.COLORS['reset']}")
    
    @staticmethod
    def print_info(text):
        """Print info message"""
        print(f"{Config.COLORS['info']}ℹ️  {text}{Config.COLORS['reset']}")
    
    @staticmethod
    def print_download(text):
        """Print download message"""
        print(f"{Config.COLORS['download']}⬇️  {text}{Config.COLORS['reset']}")
    
    @staticmethod
    def format_size(bytes_num):
        """Format bytes to human readable string"""
        if bytes_num == 0:
            return "0 B"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_num < 1024.0:
                return f"{bytes_num:.1f} {unit}"
            bytes_num /= 1024.0
        return f"{bytes_num:.1f} TB"
    
    @staticmethod
    def format_time(seconds):
        """Format seconds to HH:MM:SS"""
        if seconds <= 0:
            return "00:00:00"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    @staticmethod
    def print_stats_table(stats):
        """Print statistics in a table format"""
        print(f"\n{Config.COLORS['header']}{'📊 DOWNLOAD STATISTICS':^60}{Config.COLORS['reset']}")
        print(f"{'─'*60}")
        
        data = [
            ("Total Items", f"{stats['total_items']}"),
            ("Completed Items", f"{stats['completed_items']}"),
            ("Total Files", f"{stats['total_files']}"),
            ("Completed Files", f"{stats['completed_files']}"),
            ("Failed Files", f"{stats['failed_files']}"),
            ("Skipped Files", f"{stats['skipped_files']}"),
            ("Downloaded Size", TerminalUI.format_size(stats['downloaded_size'])),
            ("Elapsed Time", TerminalUI.format_time(stats['elapsed_time'])),
            ("Avg Speed", f"{stats['avg_speed']:.1f} KB/s")
        ]
        
        for label, value in data:
            print(f"{Config.COLORS['info']}{label:25}{Config.COLORS['reset']}: {value}")
        
        print(f"{'─'*60}")

# =========================
# ADVANCED DOWNLOAD MANAGER (WITHOUT PRE-SIZING)
# =========================
class AdvancedTerminalDownloader:
    def __init__(self, config: Config):
        self.config = config
        self.ui = TerminalUI()
        self.session_pool = {}
        self.lock = threading.RLock()
        self.is_paused = threading.Event()
        self.is_stopped = threading.Event()
        self.start_time = None
        
        # Performance tracking
        self.speed_samples = []
        self.speed_lock = threading.Lock()
        
        # Statistics
        self.stats = {
            "total_items": 0,
            "completed_items": 0,
            "total_files": 0,
            "completed_files": 0,
            "total_size": 0,  # Will remain 0 without pre-sizing
            "downloaded_size": 0,
            "failed_files": 0,
            "skipped_files": 0,
            "start_time": None,
            "elapsed_time": 0,
            "download_speed": 0.0,
            "avg_speed": 0.0,
            "active_downloads": 0
        }
        
        # Progress bars
        self.overall_pbar = None
        self.file_pbars = {}
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Create directories
        self._ensure_directories()
        
        # Load existing downloads for resume
        self.existing_downloads = self._load_existing_downloads()
    
    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C and termination signals"""
        self.ui.print_warning("\n\n⚠️  Interrupt received. Stopping downloads gracefully...")
        self.is_stopped.set()
        if self.overall_pbar:
            self.overall_pbar.close()
    
    def _ensure_directories(self):
        """Create all necessary directories"""
        os.makedirs(self.config.BASE_DIR, exist_ok=True)
        for folder in self.config.FOLDERS.values():
            os.makedirs(os.path.join(self.config.BASE_DIR, folder), exist_ok=True)
        self.ui.print_success(f"Created directory structure in '{self.config.BASE_DIR}'")
    
    def _load_existing_downloads(self) -> Dict[str, List[str]]:
        """Load existing downloads from names.json for resume functionality"""
        names_path = os.path.join(self.config.BASE_DIR, "names.json")
        existing_downloads = {}
        
        if os.path.exists(names_path):
            try:
                with open(names_path, 'r', encoding='utf-8') as f:
                    existing_downloads = json.load(f)
                self.ui.print_info(f"Loaded {len(existing_downloads)} existing items from names.json")
            except json.JSONDecodeError:
                self.ui.print_warning("Existing names.json is corrupted, will create new one")
            except Exception as e:
                self.ui.print_warning(f"Could not load existing names.json: {e}")
        
        return existing_downloads
    
    def _update_names_json(self, item_id: str, filename: str):
        """Update names.json incrementally for each completed file"""
        names_path = os.path.join(self.config.BASE_DIR, "names.json")
        
        try:
            # Load existing data or create new
            existing_data = {}
            if os.path.exists(names_path):
                try:
                    with open(names_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = {}
            
            # Update the data
            if item_id not in existing_data:
                existing_data[item_id] = []
            
            # Add filename if not already present
            if filename not in existing_data[item_id]:
                existing_data[item_id].append(filename)
            
            # Save back to file
            with open(names_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
                
            return True
            
        except Exception as e:
            self.ui.print_error(f"Error updating names.json: {e}")
            return False
    
    def _check_existing_file(self, item_id: str, filename: str, file_type: str) -> Tuple[bool, int]:
        """Check if file already exists and is complete"""
        # Determine destination folder
        if file_type == "pdf":
            dest_folder = self.config.FOLDERS["pdf"]
        else:
            dest_folder = self.config.FOLDERS.get(file_type, "other")
        
        dest_path = os.path.join(self.config.BASE_DIR, dest_folder, filename)
        
        # Check if file exists physically
        if os.path.exists(dest_path):
            file_size = os.path.getsize(dest_path)
            
            # Check in names.json if this file was recorded as completed
            if item_id in self.existing_downloads:
                if filename in self.existing_downloads[item_id]:
                    return True, file_size
            
            # Also check if file seems complete (non-zero size)
            if file_size > 0:
                # Without pre-sizing, we can't verify if it's the complete file
                # But we'll assume it is if it exists and has content
                return True, file_size
        
        return False, 0
    
    def get_session(self, worker_id: int = 0):
        """Get or create a session for a worker"""
        if worker_id not in self.session_pool:
            session = requests.Session()
            
            # Advanced retry strategy
            retry_strategy = Retry(
                total=self.config.MAX_RETRIES,
                backoff_factor=1,
                status_forcelist=[429, 500, 502, 503, 504, 408],
                allowed_methods=["GET", "HEAD"],
                respect_retry_after_header=True
            )
            
            # High-performance adapter
            adapter = HTTPAdapter(
                max_retries=retry_strategy,
                pool_connections=self.config.CONNECTION_POOL,
                pool_maxsize=self.config.CONNECTION_POOL,
                pool_block=False
            )
            
            session.mount('https://', adapter)
            session.mount('http://', adapter)
            
            # Optimized headers
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive"
            })
            
            self.session_pool[worker_id] = session
        
        return self.session_pool[worker_id]
    
    def parse_input_data(self, raw_data: Dict) -> List[Dict]:
        """Parse input JSON with validation - supports new format with multiple PDFs"""
        items = []
        
        self.ui.print_info("Parsing input data...")
        
        for item_id, item_data in raw_data.items():
            try:
                files_dict = item_data.get("files", {})
                if not files_dict:
                    continue
                
                # Validate and organize files
                validated_files = {}
                
                # Process thumb and metadata (single files)
                for file_type in ["thumb", "metadata"]:
                    if file_type in files_dict:
                        url = files_dict[file_type]
                        # Create safe filename
                        safe_id = self._safe_filename(item_id)
                        filename = self._generate_filename(safe_id, file_type)
                        
                        # Check if file already exists
                        already_downloaded, existing_size = self._check_existing_file(item_id, filename, file_type)
                        
                        validated_files[file_type] = {
                            "url": url,
                            "filename": filename,
                            "type": file_type,
                            "size": 0,  # Will be discovered during download
                            "downloaded": existing_size if already_downloaded else 0,
                            "status": "skipped" if already_downloaded else "pending",
                            "progress": 100.0 if already_downloaded else 0.0
                        }
                
                # Process PDFs (multiple files)
                pdf_files = []
                if "pdfs" in files_dict:
                    pdfs_list = files_dict["pdfs"]
                    if isinstance(pdfs_list, list):
                        for pdf_info in pdfs_list:
                            if isinstance(pdf_info, dict) and "name" in pdf_info and "url" in pdf_info:
                                pdf_name = self._safe_filename(pdf_info["name"])
                                
                                # Check if PDF already exists
                                already_downloaded, existing_size = self._check_existing_file(item_id, pdf_name, "pdf")
                                
                                pdf_files.append({
                                    "url": pdf_info["url"],
                                    "filename": pdf_name,  # Use the name from JSON
                                    "type": "pdf",
                                    "size": 0,  # Will be discovered during download
                                    "downloaded": existing_size if already_downloaded else 0,
                                    "status": "skipped" if already_downloaded else "pending",
                                    "progress": 100.0 if already_downloaded else 0.0
                                })
                
                # Add PDFs to validated files with unique keys
                for idx, pdf_info in enumerate(pdf_files):
                    validated_files[f"pdf_{idx}"] = pdf_info
                
                if validated_files:
                    # Count completed files
                    completed_count = sum(1 for f in validated_files.values() if f["status"] == "skipped")
                    total_files = len(validated_files)
                    
                    items.append({
                        "id": item_id,
                        "safe_id": safe_id,
                        "files": validated_files,
                        "status": "completed" if completed_count == total_files else "pending",
                        "progress": (completed_count / total_files * 100) if total_files > 0 else 0,
                        "completed_files": completed_count,
                        "total_files": total_files,
                        "total_size": 0,  # Unknown without sizing
                        "downloaded_size": sum(f["downloaded"] for f in validated_files.values())
                    })
                    
                    # Update statistics for skipped files
                    if completed_count > 0:
                        with self.lock:
                            self.stats["skipped_files"] += completed_count
                            self.stats["completed_files"] += completed_count
                            self.stats["downloaded_size"] += sum(f["downloaded"] for f in validated_files.values())
                    
            except Exception as e:
                self.ui.print_warning(f"Skipping item '{item_id}': {e}")
                continue
        
        self.ui.print_success(f"Parsed {len(items)} items with {sum(item['total_files'] for item in items)} total files")
        self.ui.print_info(f"Found {self.stats['skipped_files']} already downloaded files to skip")
        return items
    
    def _safe_filename(self, text: str) -> str:
        """Create safe filename for Windows/Linux"""
        # Decode URL-encoded characters first
        text = unquote(text)
        
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            text = text.replace(char, '_')
        
        # Also replace any control characters
        text = ''.join(char for char in text if ord(char) >= 32 or char in ['\n', '\t'])
        
        # Limit length and remove trailing dots/spaces
        text = text[:200].rstrip('. ')
        
        # Ensure it has a valid extension
        if not any(text.lower().endswith(ext) for ext in ['.pdf', '.jpg', '.xml']):
            # Try to guess extension from content type or keep as is
            pass
            
        return text
    
    def _generate_filename(self, item_id: str, file_type: str) -> str:
        """Generate filename for thumb and metadata files"""
        if file_type == "thumb":
            return f"{item_id}__ia_thumb.jpg"
        elif file_type == "metadata":
            return f"{item_id}_meta.xml"
        else:
            # Should not be called for PDFs
            return f"{item_id}.pdf"
    
    def update_statistics(self):
        """Update statistics with current data"""
        with self.lock:
            if self.start_time:
                self.stats["elapsed_time"] = time.time() - self.start_time
    
    def download_file_advanced(self, item: Dict, file_key: str, 
                             worker_id: int = 0) -> Tuple[bool, int, str]:
        """Advanced download method with progress tracking (without pre-sizing)"""
        
        if self.is_stopped.is_set():
            return False, 0, "Download stopped"
        
        file_info = item["files"][file_key]
        
        # Skip if already completed
        if file_info["status"] in ["completed", "skipped"]:
            return True, file_info["downloaded"], "Already downloaded"
        
        url = file_info["url"]
        filename = file_info["filename"]
        file_type = file_info["type"]
        
        # Determine destination folder
        if file_type == "pdf":
            dest_folder = self.config.FOLDERS["pdf"]
        else:
            dest_folder = self.config.FOLDERS.get(file_type, "other")
        
        dest_path = os.path.join(self.config.BASE_DIR, dest_folder, filename)
        
        # Create progress bar for this file (indeterminate initially)
        desc = f"{filename[:25]:25}"
        pbar = tqdm(
            desc=desc,
            unit="B",
            unit_scale=True,
            ncols=80,
            leave=False,
            bar_format="{desc} |{bar}| {n_fmt}/{total_fmt} [{rate_fmt}]",
            # total=None initially (indeterminate)
        )
        self.file_pbars[f"{item['id']}_{file_key}"] = pbar
        
        try:
            # Check for existing file and resume
            start_byte = 0
            if os.path.exists(dest_path):
                start_byte = os.path.getsize(dest_path)
                if start_byte > 0:
                    # Without pre-sizing, we can't verify completeness
                    # But we'll try to resume anyway
                    pbar.update(start_byte)  # Show existing progress
            
            # Prepare session
            session = self.get_session(worker_id)
            
            # Set headers for resume
            headers = {}
            if start_byte > 0:
                headers['Range'] = f'bytes={start_byte}-'
            
            # Stream download
            with session.get(
                url,
                headers=headers,
                stream=True,
                timeout=self.config.TIMEOUT,
                allow_redirects=True
            ) as response:
                response.raise_for_status()
                
                # Get total size from response headers if available
                if 'content-length' in response.headers:
                    content_length = int(response.headers['content-length'])
                    total_size = start_byte + content_length
                    
                    # Update progress bar with known total
                    pbar.total = total_size
                    pbar.refresh()
                    
                    file_info["size"] = total_size
                else:
                    total_size = 0  # Unknown size
                    file_info["size"] = 0
                
                # Open file for writing
                mode = 'ab' if start_byte > 0 else 'wb'
                with open(dest_path, mode) as f:
                    downloaded = start_byte
                    last_update = time.time()
                    bytes_since_update = 0
                    
                    for chunk in response.iter_content(chunk_size=self.config.CHUNK_SIZE):
                        if self.is_stopped.is_set():
                            pbar.close()
                            del self.file_pbars[f"{item['id']}_{file_key}"]
                            return False, downloaded, "Download stopped"
                        
                        # Check if paused
                        if self.is_paused.is_set():
                            while self.is_paused.is_set() and not self.is_stopped.is_set():
                                time.sleep(0.1)
                        
                        if self.is_stopped.is_set():
                            pbar.close()
                            del self.file_pbars[f"{item['id']}_{file_key}"]
                            return False, downloaded, "Download stopped"
                        
                        if chunk:
                            f.write(chunk)
                            chunk_size = len(chunk)
                            downloaded += chunk_size
                            bytes_since_update += chunk_size
                            
                            # Update progress bar
                            pbar.update(chunk_size)
                            
                            # Update speed calculation
                            current_time = time.time()
                            if current_time - last_update >= 0.5:
                                with self.speed_lock:
                                    speed = bytes_since_update / (current_time - last_update)
                                    self._update_speed(speed)
                                
                                bytes_since_update = 0
                                last_update = current_time
                
                # Get final size and update file info
                final_size = os.path.getsize(dest_path)
                
                # Verify download if we knew the expected size
                if total_size > 0 and final_size != total_size:
                    self.ui.print_warning(f"Size mismatch for {filename}: expected {total_size}, got {final_size}")
                    # Still mark as completed since we downloaded something
                
                file_info["status"] = "completed"
                file_info["downloaded"] = final_size
                file_info["progress"] = 100.0
                
                # Close progress bar
                pbar.close()
                del self.file_pbars[f"{item['id']}_{file_key}"]
                
                # Update names.json immediately after successful download
                self._update_names_json(item["id"], filename)
                
                return True, final_size, "Download completed"
        
        except requests.exceptions.RequestException as e:
            pbar.close()
            del self.file_pbars[f"{item['id']}_{file_key}"]
            return False, 0, f"Network error: {str(e)}"
        except IOError as e:
            pbar.close()
            del self.file_pbars[f"{item['id']}_{file_key}"]
            return False, 0, f"File error: {str(e)}"
        except Exception as e:
            pbar.close()
            del self.file_pbars[f"{item['id']}_{file_key}"]
            return False, 0, f"Unexpected error: {str(e)}"
    
    def _update_speed(self, current_speed: float):
        """Update speed statistics with smoothing"""
        self.speed_samples.append(current_speed)
        if len(self.speed_samples) > self.config.SPEED_SMOOTHING:
            self.speed_samples.pop(0)
        
        self.stats["download_speed"] = current_speed
        self.stats["avg_speed"] = sum(self.speed_samples) / len(self.speed_samples) / 1024
    
    def calculate_statistics(self, items: List[Dict]) -> Dict:
        """Calculate total statistics WITHOUT pre-fetching file sizes"""
        total_files = sum(item["total_files"] for item in items)
        
        # Skip size checking - just count files
        self.ui.print_info("Skipping file size pre-check (faster startup)")
        
        # Update basic statistics
        self.stats.update({
            "total_items": len(items),
            "total_files": total_files,
            "total_size": 0,  # Unknown without sizing
            "downloaded_size": sum(item["downloaded_size"] for item in items),
            "start_time": time.time() if not self.stats["start_time"] else self.stats["start_time"]
        })
        
        return self.stats
    
    def download_all(self, items: List[Dict]):
        """Main download method with multithreading"""
        
        self.start_time = time.time()
        self.stats["start_time"] = self.start_time
        
        # Count pending files for progress bar
        pending_files = sum(1 for item in items for f in item["files"].values() if f["status"] == "pending")
        
        # Create overall progress bar
        self.ui.print_header("STARTING DOWNLOAD")
        self.ui.print_info(f"{pending_files} files to download, {self.stats['skipped_files']} files already downloaded")
        self.ui.print_warning("Note: Total size unknown (skipped pre-size check for faster startup)")
        
        self.overall_pbar = tqdm(
            total=self.stats["total_files"],
            desc="Overall",
            unit="files",
            ncols=80,
            bar_format="{desc} |{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
            initial=self.stats["skipped_files"]
        )
        
        print(f"\n{Config.COLORS['download']}📦 Downloading {self.stats['total_items']} items "
              f"({pending_files} new files){Config.COLORS['reset']}")
        print(f"{Config.COLORS['info']}Note: File sizes will be discovered during download{Config.COLORS['reset']}")
        print(f"{'─'*80}")
        
        # Create a list to track active downloads for logging
        active_downloads = {}
        
        try:
            with ThreadPoolExecutor(max_workers=self.config.MAX_WORKERS) as executor:
                futures = {}
                worker_counter = 0
                
                # Submit all pending files for download
                for item in items:
                    if self.is_stopped.is_set():
                        break
                    
                    # Log item start
                    self.ui.print_info(f"Processing item: {item['id'][:50]}... ({item['completed_files']}/{item['total_files']} completed)")
                    
                    for file_key, file_info in item["files"].items():
                        if self.is_stopped.is_set():
                            break
                        
                        # Skip if already completed or skipped
                        if file_info["status"] in ["completed", "skipped"]:
                            continue
                        
                        # Track active download
                        download_id = f"{item['id']}_{file_key}"
                        active_downloads[download_id] = {
                            "filename": file_info["filename"],
                            "start_time": time.time(),
                            "status": "starting"
                        }
                        
                        # Submit download task
                        future = executor.submit(
                            self.download_file_advanced,
                            item,
                            file_key,
                            worker_counter % self.config.MAX_WORKERS
                        )
                        futures[future] = (item["id"], file_key, download_id)
                        worker_counter += 1
                
                # Process results
                for future in as_completed(futures):
                    if self.is_stopped.is_set():
                        break
                    
                    item_id, file_key, download_id = futures[future]
                    
                    try:
                        success, size, message = future.result(timeout=300)
                        
                        # Update overall progress
                        self.overall_pbar.update(1)
                        
                        # Remove from active downloads
                        if download_id in active_downloads:
                            del active_downloads[download_id]
                        
                        # Find the item
                        item = next((i for i in items if i["id"] == item_id), None)
                        if not item:
                            continue
                        
                        if success:
                            item["completed_files"] += 1
                            item["downloaded_size"] += size
                            item["files"][file_key]["status"] = "completed"
                            
                            with self.lock:
                                self.stats["completed_files"] += 1
                                self.stats["downloaded_size"] += size
                            
                            # Check if item completed
                            if item["completed_files"] == item["total_files"]:
                                item["status"] = "completed"
                                with self.lock:
                                    self.stats["completed_items"] += 1
                                self.ui.print_success(f"✓ Item completed: {item_id[:50]}...")
                            
                            # Log success
                            filename = item["files"][file_key]["filename"]
                            size_str = self.ui.format_size(size)
                            self.ui.print_success(f"Downloaded: {filename[:40]}... ({size_str})")
                            
                        else:
                            with self.lock:
                                self.stats["failed_files"] += 1
                            
                            # Log error
                            self.ui.print_error(f"Failed: {message}")
                        
                        # Update statistics
                        self.update_statistics()
                        
                    except Exception as e:
                        with self.lock:
                            self.stats["failed_files"] += 1
                        
                        # Log error
                        self.ui.print_error(f"Download error: {e}")
            
            # Completion
            if not self.is_stopped.is_set():
                self._on_download_complete(items)
                
        except KeyboardInterrupt:
            self.ui.print_warning("\nDownload interrupted by user")
            self._save_session_state(items)
        except Exception as e:
            self.ui.print_error(f"Fatal error: {e}")
            self._save_session_state(items)
        finally:
            self._cleanup()
    
    def _save_session_state(self, items: List[Dict]):
        """Save current session state for resume"""
        try:
            session_path = os.path.join(self.config.BASE_DIR, "session_state.json")
            session_data = {
                "timestamp": datetime.now().isoformat(),
                "interrupted": True,
                "stats": self.stats,
                "items": []
            }
            
            for item in items:
                item_data = {
                    "id": item["id"],
                    "status": item["status"],
                    "completed_files": item["completed_files"],
                    "total_files": item["total_files"],
                    "files": {}
                }
                
                for file_key, file_info in item["files"].items():
                    item_data["files"][file_key] = {
                        "filename": file_info["filename"],
                        "status": file_info["status"],
                        "downloaded": file_info["downloaded"],
                        "size": file_info["size"]
                    }
                
                session_data["items"].append(item_data)
            
            with open(session_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            self.ui.print_info(f"Session state saved to {session_path}")
            self.ui.print_info(f"Run again to resume from where you left off")
            
        except Exception as e:
            self.ui.print_error(f"Error saving session state: {e}")
    
    def _on_download_complete(self, items: List[Dict]):
        """Handle download completion"""
        self.update_statistics()
        
        # Close overall progress bar
        if self.overall_pbar:
            self.overall_pbar.close()
        
        print(f"\n{Config.COLORS['success']}{'='*80}")
        print(f"🎉 DOWNLOAD COMPLETED SUCCESSFULLY!")
        print(f"{'='*80}{Config.COLORS['reset']}")
        
        # Calculate actual total size from downloaded files
        actual_total_size = 0
        for item in items:
            for file_info in item["files"].values():
                if file_info["status"] == "completed" or file_info["status"] == "skipped":
                    actual_total_size += file_info["downloaded"]
        
        self.stats["total_size"] = actual_total_size
        
        # Print statistics
        self.ui.print_stats_table(self.stats)
        
        # Save detailed log
        self._save_detailed_log(items)
        
        print(f"\n{Config.COLORS['success']}✅ All downloads saved to: {os.path.abspath(self.config.BASE_DIR)}{Config.COLORS['reset']}")
        print(f"{Config.COLORS['info']}📁 names.json updated incrementally during download{Config.COLORS['reset']}")
        
        # Show folder summary
        print(f"\n{Config.COLORS['header']}{'📁 FOLDER CONTENTS':^60}{Config.COLORS['reset']}")
        print(f"{'─'*60}")
        for folder_name, folder_path in self.config.FOLDERS.items():
            full_path = os.path.join(self.config.BASE_DIR, folder_path)
            if os.path.exists(full_path):
                file_count = len([f for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f))])
                print(f"{Config.COLORS['info']}{folder_name:15}{Config.COLORS['reset']}: {file_count} files")
        print(f"{'─'*60}")
    
    def _save_detailed_log(self, items: List[Dict]):
        """Save detailed log without overwriting names.json"""
        try:
            # Save detailed log
            log_json = {
                "metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "total_items": self.stats["total_items"],
                    "total_files": self.stats["total_files"],
                    "completed_items": self.stats["completed_items"],
                    "completed_files": self.stats["completed_files"],
                    "failed_files": self.stats["failed_files"],
                    "skipped_files": self.stats["skipped_files"],
                    "total_size": self.stats["total_size"],
                    "downloaded_size": self.stats["downloaded_size"],
                    "elapsed_time": self.stats["elapsed_time"],
                    "avg_speed": self.stats["avg_speed"],
                    "note": "Downloaded without pre-size checking"
                },
                "items": []
            }
            
            for item in items:
                item_log = {
                    "id": item["id"],
                    "status": item["status"],
                    "total_files": item["total_files"],
                    "completed_files": item["completed_files"],
                    "total_size": sum(f["downloaded"] for f in item["files"].values()),
                    "downloaded_size": item["downloaded_size"],
                    "files": []
                }
                
                for file_key, file_info in item["files"].items():
                    item_log["files"].append({
                        "key": file_key,
                        "type": file_info["type"],
                        "filename": file_info["filename"],
                        "size": file_info["size"],
                        "downloaded": file_info["downloaded"],
                        "status": file_info["status"],
                        "url": file_info["url"][:100] + "..." if len(file_info["url"]) > 100 else file_info["url"]
                    })
                
                log_json["items"].append(item_log)
            
            log_path = os.path.join(self.config.BASE_DIR, "download_log.json")
            
            # Append to existing log or create new
            existing_logs = []
            if os.path.exists(log_path):
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        existing_logs = json.load(f)
                    if not isinstance(existing_logs, list):
                        existing_logs = [existing_logs]
                except json.JSONDecodeError:
                    existing_logs = []
            
            existing_logs.append(log_json)
            
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(existing_logs, f, indent=2, ensure_ascii=False)
            
            self.ui.print_success(f"Saved detailed log: {log_path}")
            
            # Save summary CSV (append mode)
            csv_path = os.path.join(self.config.BASE_DIR, "download_summary.csv")
            write_header = not os.path.exists(csv_path)
            
            with open(csv_path, 'a', encoding='utf-8') as f:
                if write_header:
                    f.write("Timestamp,Item ID,Status,Total Files,Completed Files,Downloaded Size\n")
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for item in items:
                    if item["completed_files"] > 0:
                        f.write(f"{timestamp},{item['id']},{item['status']},{item['total_files']},"
                               f"{item['completed_files']},{item['downloaded_size']}\n")
            
            self.ui.print_success(f"Updated summary CSV: {csv_path}")
            
        except Exception as e:
            self.ui.print_error(f"Error saving log files: {e}")
    
    def _cleanup(self):
        """Cleanup after download"""
        # Close all progress bars
        if self.overall_pbar:
            self.overall_pbar.close()
        
        for pbar in self.file_pbars.values():
            pbar.close()
        
        self.file_pbars.clear()

# =========================
# MAIN APPLICATION
# =========================
def main():
    """Main application entry point"""
    
    # Initialize colorama for Windows
    init(autoreset=True)
    
    # Clear screen
    os.system('cls' if os.name == 'nt' else 'clear')
    
    # Print banner
    print(f"{Config.COLORS['header']}")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           ⚡ ADVANCED ARCHIVE DOWNLOADER ⚡                  ║")
    print("║     Terminal Edition - No Pre-Size Check (Faster Startup)   ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"{Config.COLORS['reset']}")
    
    print(f"\n{Config.COLORS['info']}Version: 2.1 | Threads: {Config.MAX_WORKERS} | "
          f"Chunk Size: {Config.CHUNK_SIZE//1024}KB{Config.COLORS['reset']}")
    print(f"{Config.COLORS['info']}Press Ctrl+C to stop download (resumable){Config.COLORS['reset']}")
    print(f"{Config.COLORS['warning']}Note: File sizes discovered during download{Config.COLORS['reset']}\n")
    
    # Check for input file
    if not os.path.exists(Config.INPUT_JSON):
        TerminalUI.print_error(f"Input file '{Config.INPUT_JSON}' not found!")
        print(f"\nPlease create '{Config.INPUT_JSON}' with the following format:")
        print("""
{
  "Item Name": {
    "file_id": "Item Name",
    "files": {
      "thumb": "https://archive.org/download/.../__ia_thumb.jpg",
      "metadata": "https://archive.org/download/.../file_meta.xml",
      "pdfs": [
        {
          "name": "filename.pdf",
          "url": "https://archive.org/download/.../filename.pdf"
        },
        {
          "name": "another_file.pdf",
          "url": "https://archive.org/download/.../another_file.pdf"
        }
      ]
    }
  }
}""")
        input("\nPress Enter to exit...")
        return
    
    # Create downloader instance
    downloader = AdvancedTerminalDownloader(Config())
    
    try:
        # Load and parse input data
        TerminalUI.print_info(f"Loading {Config.INPUT_JSON}...")
        
        with open(Config.INPUT_JSON, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        
        items = downloader.parse_input_data(raw_data)
        
        if not items:
            TerminalUI.print_error("No valid items found in input file!")
            return
        
        # Calculate statistics (without sizing)
        stats = downloader.calculate_statistics(items)
        
        # Display summary
        print(f"\n{Config.COLORS['header']}{'📋 DOWNLOAD SUMMARY':^60}{Config.COLORS['reset']}")
        print(f"{'─'*60}")
        print(f"{Config.COLORS['info']}Items:{Config.COLORS['reset']} {stats['total_items']}")
        print(f"{Config.COLORS['info']}Files:{Config.COLORS['reset']} {stats['total_files']}")
        print(f"{Config.COLORS['info']}Already Downloaded:{Config.COLORS['reset']} {stats['skipped_files']}")
        print(f"{Config.COLORS['info']}To Download:{Config.COLORS['reset']} {stats['total_files'] - stats['skipped_files']}")
        print(f"{Config.COLORS['warning']}Total Size:{Config.COLORS['reset']} Unknown (will discover during download)")
        print(f"{Config.COLORS['info']}PDF Folder:{Config.COLORS['reset']} {Config.BASE_DIR}/pdf/")
        print(f"{Config.COLORS['info']}Thumbs Folder:{Config.COLORS['reset']} {Config.BASE_DIR}/thumb/")
        print(f"{Config.COLORS['info']}Metadata Folder:{Config.COLORS['reset']} {Config.BASE_DIR}/metadata/")
        print(f"{'─'*60}")
        
        # Ask for confirmation
        print(f"\n{Config.COLORS['warning']}Start download? [y/N]: {Config.COLORS['reset']}", end='')
        response = input().strip().lower()
        
        if response not in ['y', 'yes']:
            TerminalUI.print_info("Download cancelled")
            return
        
        # Start download
        downloader.download_all(items)
        
    except json.JSONDecodeError as e:
        TerminalUI.print_error(f"Invalid JSON in input file: {e}")
    except KeyboardInterrupt:
        TerminalUI.print_warning("\n\nApplication terminated by user")
    except Exception as e:
        TerminalUI.print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\n{Config.COLORS['header']}Thank you for using Advanced Archive Downloader!{Config.COLORS['reset']}")

if __name__ == "__main__":
    main()