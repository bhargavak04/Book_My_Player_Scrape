import requests
import re
from bs4 import BeautifulSoup
from typing import Dict, Any, List
import time
import pandas as pd
import logging
import os
import json
from datetime import datetime
import threading
import signal
import sys

class BookMyPlayerScraperPro:
    def __init__(self, auto_save_interval: int = 1000, max_workers: int = 1, delay_between_requests: float = 1.0):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Configuration
        self.auto_save_interval = auto_save_interval
        self.delay_between_requests = delay_between_requests
        self.max_workers = max_workers
        
        # Progress tracking
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0
        self.start_time = None
        
        # Data storage
        self.results = []
        self.venue_data = []
        self.coach_data = []
        self.player_data = []
        self.error_data = []
        
        # Setup logging
        self.setup_logging()
        
        # Graceful shutdown handler
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.logger.info("BookMyPlayerScraperPro initialized")
        self.logger.info(f"Auto-save interval: {auto_save_interval} records")
        self.logger.info(f"Request delay: {delay_between_requests} seconds")
    
    def setup_logging(self):
        """Setup comprehensive logging"""
        # Create logs directory
        os.makedirs('logs', exist_ok=True)
        
        # Configure logging
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        
        # File handler for all logs
        file_handler = logging.FileHandler(f'logs/scraper_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(log_format))
        
        # Console handler for important logs
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(log_format))
        
        # Progress handler for detailed progress
        progress_handler = logging.FileHandler('logs/progress.log')
        progress_handler.setLevel(logging.INFO)
        progress_handler.setFormatter(logging.Formatter(log_format))
        
        # Setup main logger
        self.logger = logging.getLogger('BookMyPlayerScraper')
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        # Setup progress logger
        self.progress_logger = logging.getLogger('Progress')
        self.progress_logger.setLevel(logging.INFO)
        self.progress_logger.addHandler(progress_handler)
        self.progress_logger.addHandler(console_handler)
    
    def signal_handler(self, signum, frame):
        """Handle graceful shutdown"""
        self.logger.info(f"Received signal {signum}. Saving progress and shutting down...")
        self.save_progress()
        sys.exit(0)
    
    def fetch_page(self, url: str) -> str:
        """Fetch page content with error handling and retries"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response.text
            except Exception as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"Failed to fetch {url} after {max_retries} attempts: {e}")
                    return ""
                else:
                    self.logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}. Retrying...")
                    time.sleep(2 ** attempt)  # Exponential backoff
        return ""
    
    def format_phone(self, phone_str: str) -> str:
        """Format phone number properly"""
        if not phone_str:
            return ""
        digits = re.sub(r'[^0-9]', '', str(phone_str))
        if len(digits) == 10:
            return digits
        elif len(digits) > 10:
            return digits[-10:]
        return phone_str
    
    def extract_venue_fields(self, html: str, url: str) -> Dict[str, Any]:
        """Extract venue/academy specific fields"""
        soup = BeautifulSoup(html, 'html.parser')
        data = {'type': 'venue', 'url': url, 'scraped_at': datetime.now().isoformat()}
        
        # Direct ID extractions
        id_fields = {
            'academy_phone': 'phone',
            'academy_address': 'address', 
            'listing_title': 'name',
            'loc_id_details': 'location_id',
            'sport_details': 'sport',
            'object_type_details': 'object_type',
            'academy_phone2': 'phone2'
        }
        
        for field_id, key in id_fields.items():
            element = soup.find(attrs={'id': field_id})
            if element:
                value = element.get('value') or element.get_text(strip=True)
                if value:
                    if 'phone' in key:
                        data[key] = self.format_phone(value)
                    else:
                        data[key] = value
        
        # Description from meta tag
        desc_meta = soup.find('meta', attrs={'name': 'description'})
        if desc_meta:
            data['description'] = desc_meta.get('content', '')
        
        # Instagram URL extraction
        instagram_pattern = r'<a href="(https://www\.instagram\.com/[^"]+)"'
        instagram_match = re.search(instagram_pattern, html)
        if instagram_match:
            data['instagram_url'] = instagram_match.group(1)
        
        return data
    
    def extract_coach_fields(self, html: str, url: str) -> Dict[str, Any]:
        """Extract coach specific fields"""
        soup = BeautifulSoup(html, 'html.parser')
        data = {'type': 'coach', 'url': url, 'scraped_at': datetime.now().isoformat()}
        
        # Direct ID extractions
        id_fields = {
            'coachName': 'name',
            'coachPhone': 'phone',
            'coachAddress': 'address',
            'sport_details': 'sport'
        }
        
        for field_id, key in id_fields.items():
            element = soup.find(attrs={'id': field_id})
            if element:
                value = element.get('value') or element.get_text(strip=True)
                if value:
                    if key == 'phone':
                        data[key] = self.format_phone(value)
                    else:
                        data[key] = value
        
        # Location extraction with icon
        location_pattern = r'<i class="fa-solid fa-location-dot"></i>\s*([^<]+)'
        location_match = re.search(location_pattern, html)
        if location_match:
            data['location'] = location_match.group(1).strip()
        
        # Email extraction
        email_pattern = r'<i class="fa-regular fa-envelope"></i>\s*([^<]+@[^<]+)'
        email_match = re.search(email_pattern, html)
        if email_match:
            data['email'] = email_match.group(1).strip()
        
        # Date of Birth extraction
        dob_pattern = r'Date Of Birth:\s*(\d{4}-\d{2}-\d{2})'
        dob_match = re.search(dob_pattern, html)
        if dob_match:
            data['date_of_birth'] = dob_match.group(1)
        
        return data
    
    def extract_player_fields(self, html: str, url: str) -> Dict[str, Any]:
        """Extract player specific fields"""
        soup = BeautifulSoup(html, 'html.parser')
        data = {'type': 'player', 'url': url, 'scraped_at': datetime.now().isoformat()}
        
        # Direct ID extractions
        id_fields = {
            'playerAddress': 'address',
            'playerPhone': 'phone',
            'playerName': 'name',
            'loc_id_details': 'location_id',
            'object_id_details': 'object_id'
        }
        
        for field_id, key in id_fields.items():
            element = soup.find(attrs={'id': field_id})
            if element:
                value = element.get('value') or element.get_text(strip=True)
                if value:
                    if key == 'phone':
                        data[key] = self.format_phone(value)
                    else:
                        data[key] = value
        
        # Location extraction with icon
        location_pattern = r'<i class="fa-solid fa-location-dot"></i>\s*([^<]+?)</p>'
        location_match = re.search(location_pattern, html)
        if location_match:
            data['location'] = location_match.group(1).strip()
        
        # Email extraction
        email_pattern = r'<i class="fa-regular fa-envelope"></i>\s*([^<]*)</p>'
        email_match = re.search(email_pattern, html)
        if email_match:
            email_value = email_match.group(1).strip()
            data['email'] = email_value if email_value != '-' else ''
        
        return data
    
    def detect_content_type(self, html: str, url: str) -> str:
        """Detect content type based on URL patterns and page content"""
        
        # URL-based detection
        if '/gym/' in url or 'academy' in url.lower():
            return 'venue'
        elif 'coach' in url:
            return 'coach' 
        elif 'player' in url:
            return 'player'
        
        # Content-based detection as fallback
        soup = BeautifulSoup(html, 'html.parser')
        
        # Check for venue-specific elements
        venue_indicators = [
            soup.find(attrs={'id': 'academy_phone'}),
            soup.find(attrs={'id': 'academy_address'}),
            soup.find(attrs={'id': 'listing_title'})
        ]
        if any(venue_indicators):
            return 'venue'
        
        # Check for coach-specific elements
        coach_indicators = [
            soup.find(attrs={'id': 'coachName'}),
            soup.find(attrs={'id': 'coachPhone'}),
            soup.find(attrs={'id': 'coachAddress'})
        ]
        if any(coach_indicators):
            return 'coach'
        
        # Check for player-specific elements
        player_indicators = [
            soup.find(attrs={'id': 'playerName'}),
            soup.find(attrs={'id': 'playerPhone'}),
            soup.find(attrs={'id': 'playerAddress'})
        ]
        if any(player_indicators):
            return 'player'
        
        return 'unknown'
    
    def scrape_url(self, url: str) -> Dict[str, Any]:
        """Main scraping function that auto-detects type and extracts appropriate fields"""
        try:
            html = self.fetch_page(url)
            if not html:
                return {'url': url, 'type': 'error', 'error': 'Failed to fetch page', 'scraped_at': datetime.now().isoformat()}
            
            content_type = self.detect_content_type(html, url)
            
            if content_type == 'venue':
                return self.extract_venue_fields(html, url)
            elif content_type == 'coach':
                return self.extract_coach_fields(html, url)
            elif content_type == 'player':
                return self.extract_player_fields(html, url)
            else:
                return {'url': url, 'type': 'unknown', 'error': 'Could not determine content type', 'scraped_at': datetime.now().isoformat()}
        except Exception as e:
            self.logger.error(f"Error scraping {url}: {e}")
            return {'url': url, 'type': 'error', 'error': str(e), 'scraped_at': datetime.now().isoformat()}
    
    def categorize_result(self, result: Dict[str, Any]):
        """Categorize result into appropriate list"""
        if result['type'] == 'venue':
            self.venue_data.append(result)
        elif result['type'] == 'coach':
            self.coach_data.append(result)
        elif result['type'] == 'player':
            self.player_data.append(result)
        else:
            self.error_data.append(result)
    
    def save_progress(self, filename_prefix: str = "bookmyplayer_progress"):
        """Save current progress to Excel file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"output/{filename_prefix}_{timestamp}.xlsx"
        
        os.makedirs('output', exist_ok=True)
        
        try:
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                if self.venue_data:
                    pd.DataFrame(self.venue_data).to_excel(writer, sheet_name='Venues', index=False)
                if self.coach_data:
                    pd.DataFrame(self.coach_data).to_excel(writer, sheet_name='Coaches', index=False)
                if self.player_data:
                    pd.DataFrame(self.player_data).to_excel(writer, sheet_name='Players', index=False)
                if self.error_data:
                    pd.DataFrame(self.error_data).to_excel(writer, sheet_name='Errors', index=False)
            
            # Save progress stats
            stats = {
                'processed': self.processed_count,
                'success': self.success_count,
                'errors': self.error_count,
                'venues': len(self.venue_data),
                'coaches': len(self.coach_data),
                'players': len(self.player_data),
                'timestamp': timestamp,
                'filename': filename
            }
            
            with open(f"output/stats_{timestamp}.json", 'w') as f:
                json.dump(stats, f, indent=2)
            
            self.logger.info(f"Progress saved to {filename}")
            self.logger.info(f"Stats: Processed={self.processed_count}, Success={self.success_count}, Errors={self.error_count}")
            self.logger.info(f"Data: Venues={len(self.venue_data)}, Coaches={len(self.coach_data)}, Players={len(self.player_data)}")
            
            return filename
            
        except Exception as e:
            self.logger.error(f"Failed to save progress: {e}")
            return None
    
    def get_processing_stats(self):
        """Get current processing statistics"""
        if self.start_time:
            elapsed_time = time.time() - self.start_time
            rate = self.processed_count / elapsed_time if elapsed_time > 0 else 0
        else:
            elapsed_time = 0
            rate = 0
        
        return {
            'processed': self.processed_count,
            'success': self.success_count,
            'errors': self.error_count,
            'venues': len(self.venue_data),
            'coaches': len(self.coach_data),
            'players': len(self.player_data),
            'elapsed_time': elapsed_time,
            'rate_per_second': rate,
            'rate_per_minute': rate * 60
        }
    
    def process_urls_from_excel(self, input_file: str, url_column: str = 'url', start_from: int = 0):
        """Process URLs from Excel file with auto-save and progress tracking"""
        self.logger.info(f"Loading URLs from {input_file}")
        
        try:
            # Read Excel file
            if input_file.endswith('.xlsx') or input_file.endswith('.xls'):
                df = pd.read_excel(input_file)
            else:
                df = pd.read_csv(input_file)
            
            if url_column not in df.columns:
                raise ValueError(f"Column '{url_column}' not found in file. Available columns: {df.columns.tolist()}")
            
            urls = df[url_column].dropna().astype(str).tolist()
            
            if start_from > 0:
                urls = urls[start_from:]
                self.logger.info(f"Starting from record {start_from}")
            
            total_urls = len(urls)
            self.logger.info(f"Found {total_urls} URLs to process")
            
            if total_urls == 0:
                self.logger.warning("No URLs found to process")
                return
            
            self.start_time = time.time()
            
            # Process URLs
            for i, url in enumerate(urls, start=start_from + 1):
                try:
                    # Log progress
                    if i % 100 == 0 or i == 1:
                        stats = self.get_processing_stats()
                        self.progress_logger.info(
                            f"Processing {i}/{total_urls} | "
                            f"Success: {stats['success']} | "
                            f"Errors: {stats['errors']} | "
                            f"Rate: {stats['rate_per_minute']:.1f}/min | "
                            f"URL: {url[:100]}..."
                        )
                    
                    # Scrape URL
                    result = self.scrape_url(url)
                    self.results.append(result)
                    self.categorize_result(result)
                    
                    # Update counters
                    self.processed_count += 1
                    if result['type'] in ['venue', 'coach', 'player']:
                        self.success_count += 1
                    else:
                        self.error_count += 1
                    
                    # Auto-save check
                    if self.processed_count % self.auto_save_interval == 0:
                        self.save_progress()
                        self.logger.info(f"Auto-saved at {self.processed_count} records")
                    
                    # Delay between requests
                    if i < total_urls:  # Don't delay after last URL
                        time.sleep(self.delay_between_requests)
                
                except Exception as e:
                    self.logger.error(f"Error processing URL {i}: {url} - {e}")
                    self.error_count += 1
                    self.processed_count += 1
                    continue
            
            # Final save
            final_file = self.save_progress("bookmyplayer_final")
            
            # Final stats
            final_stats = self.get_processing_stats()
            self.logger.info("=== SCRAPING COMPLETED ===")
            self.logger.info(f"Total processed: {final_stats['processed']}")
            self.logger.info(f"Successful: {final_stats['success']}")
            self.logger.info(f"Errors: {final_stats['errors']}")
            self.logger.info(f"Venues: {final_stats['venues']}")
            self.logger.info(f"Coaches: {final_stats['coaches']}")
            self.logger.info(f"Players: {final_stats['players']}")
            self.logger.info(f"Total time: {final_stats['elapsed_time']:.1f} seconds")
            self.logger.info(f"Average rate: {final_stats['rate_per_minute']:.1f} URLs/minute")
            self.logger.info(f"Final file: {final_file}")
            
        except Exception as e:
            self.logger.error(f"Error processing Excel file: {e}")
            self.save_progress("bookmyplayer_error_recovery")
            raise

if __name__ == "__main__":
    # Configuration from environment variables
    AUTO_SAVE_INTERVAL = int(os.getenv('AUTO_SAVE_INTERVAL', '1000'))
    REQUEST_DELAY = float(os.getenv('REQUEST_DELAY', '1.0'))
    INPUT_FILE = os.getenv('INPUT_FILE', 'BookMyPlayer.xlsx')
    URL_COLUMN = os.getenv('URL_COLUMN', '0')
    START_FROM = int(os.getenv('START_FROM', '0'))
    
    # Create scraper
    scraper = BookMyPlayerScraperPro(
        auto_save_interval=AUTO_SAVE_INTERVAL,
        delay_between_requests=REQUEST_DELAY
    )
    
    # Process URLs
    scraper.process_urls_from_excel(INPUT_FILE, URL_COLUMN, START_FROM)
