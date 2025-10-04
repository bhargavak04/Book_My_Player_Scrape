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
        
        # Log venue extraction details
        venue_name = data.get('name', 'Unknown')
        venue_phone = data.get('phone', 'No phone')
        venue_address = data.get('address', 'No address')
        self.logger.info(f"VENUE EXTRACTED: {venue_name} | Phone: {venue_phone} | Address: {venue_address}")
        
        return data
    
    def extract_coach_fields(self, html: str, url: str) -> Dict[str, Any]:
        """Extract coach specific fields - handles both HTML and JSON responses"""
        data = {'type': 'coach', 'url': url, 'scraped_at': datetime.now().isoformat()}
        
        # First, try to detect if this is JSON data
        html_clean = html.strip()
        if html_clean.startswith('{') or html_clean.startswith('\n{'):
            # This is JSON data - extract from JSON
            return self.extract_coach_from_json(html_clean, url)
        
        # Otherwise, treat as HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Direct ID extractions (try multiple approaches)
        id_fields = {
            'coachName': 'name',
            'coachPhone': 'phone',
            'coachAddress': 'address',
            'sport_details': 'sport'
        }
        
        for field_id, key in id_fields.items():
            # Try ID first
            element = soup.find(attrs={'id': field_id})
            if element:
                value = element.get('value') or element.get_text(strip=True)
                if value and value.strip():
                    if key == 'phone':
                        data[key] = self.format_phone(value)
                    else:
                        data[key] = value
            else:
                # Try class-based extraction as fallback
                if key == 'name':
                    # Try to find coach name in title or heading
                    title_elem = soup.find('h1') or soup.find('title')
                    if title_elem:
                        title_text = title_elem.get_text(strip=True)
                        if 'coach' in title_text.lower():
                            data[key] = title_text
        
        # Enhanced location extraction
        location_patterns = [
            r'<i class="fa-solid fa-location-dot"></i>\s*([^<\n]+)',
            r'<i class="fa-solid fa-location-dot"></i>\s*([^<]+?)(?=<|$)',
            r'Location[:\s]*([^<\n]+)',
            r'Address[:\s]*([^<\n]+)'
        ]
        
        for pattern in location_patterns:
            location_match = re.search(pattern, html, re.IGNORECASE)
            if location_match:
                location_text = location_match.group(1).strip()
                if location_text and len(location_text) > 3:
                    data['location'] = location_text
                    break
        
        # Enhanced email extraction (avoid generic emails)
        email_patterns = [
            r'<i class="fa-regular fa-envelope"></i>\s*([^<\n]+@[^<\n]+)',
            r'Email[:\s]*([^<\n]+@[^<\n]+)',
            r'Contact[:\s]*([^<\n]+@[^<\n]+)',
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        ]
        
        for pattern in email_patterns:
            email_match = re.search(pattern, html, re.IGNORECASE)
            if email_match:
                email_text = email_match.group(1).strip()
                # Skip generic emails
                if email_text and not any(generic in email_text.lower() for generic in ['care@', 'info@', 'support@', 'contact@', 'admin@']):
                    data['email'] = email_text
                    break
        
        # Enhanced phone extraction
        phone_patterns = [
            r'<i class="fa-solid fa-phone"></i>\s*([^<\n]+)',
            r'Phone[:\s]*([^<\n]+)',
            r'Contact[:\s]*([^<\n]+)',
            r'(\+?[0-9\s\-\(\)]{10,})'
        ]
        
        for pattern in phone_patterns:
            phone_match = re.search(pattern, html, re.IGNORECASE)
            if phone_match:
                phone_text = phone_match.group(1).strip()
                if phone_text and len(re.sub(r'[^0-9]', '', phone_text)) >= 10:
                    data['phone'] = self.format_phone(phone_text)
                    break
        
        # Date of Birth extraction
        dob_patterns = [
            r'Date Of Birth[:\s]*(\d{4}-\d{2}-\d{2})',
            r'DOB[:\s]*(\d{4}-\d{2}-\d{2})',
            r'Born[:\s]*(\d{4}-\d{2}-\d{2})'
        ]
        
        for pattern in dob_patterns:
            dob_match = re.search(pattern, html, re.IGNORECASE)
            if dob_match:
                data['date_of_birth'] = dob_match.group(1)
                break
        
        # Log coach extraction details (HTML)
        coach_name = data.get('name', 'Unknown')
        coach_phone = data.get('phone', 'No phone')
        coach_email = data.get('email', 'No email')
        coach_location = data.get('location', 'No location')
        self.logger.info(f"COACH EXTRACTED (HTML): {coach_name} | Phone: {coach_phone} | Email: {coach_email} | Location: {coach_location}")
        
        return data
    
    def extract_coach_from_json(self, json_content: str, url: str) -> Dict[str, Any]:
        """Extract coach data from JSON response"""
        data = {'type': 'coach', 'url': url, 'scraped_at': datetime.now().isoformat()}
        
        try:
            # Clean the JSON content
            json_clean = json_content.strip()
            if json_clean.startswith('\n'):
                json_clean = json_clean[1:]
            
            # Check if content is empty
            if not json_clean:
                self.logger.warning(f"Empty JSON content for coach URL: {url}")
                return data
            
            # Parse JSON
            json_data = json.loads(json_clean)
            
            # Extract coach data from 'd' key
            if 'd' in json_data:
                coach_info = json_data['d']
                
                # Map JSON fields to our data structure
                field_mapping = {
                    'name': 'name',
                    'phone': 'phone',
                    'email': 'email',
                    'address': 'address',
                    'city': 'city',
                    'state': 'state',
                    'sport': 'sport',
                    'experience': 'experience',
                    'education': 'education',
                    'achievement': 'achievement',
                    'skill': 'skills',
                    'heighlight': 'highlight',
                    'fee': 'fee',
                    'package': 'package',
                    'gender': 'gender',
                    'location': 'location',
                    'certificate': 'certificate',
                    'about': 'about',
                    'postcode': 'postcode',
                    'lat': 'latitude',
                    'lng': 'longitude'
                }
                
                for json_key, data_key in field_mapping.items():
                    if json_key in coach_info and coach_info[json_key] is not None:
                        value = coach_info[json_key]
                        if value and str(value).strip():
                            if data_key == 'phone':
                                data[data_key] = self.format_phone(str(value))
                            else:
                                data[data_key] = str(value)
                
                # Create location string from city and state
                if 'city' in data and 'state' in data:
                    city = data['city']
                    state = data['state']
                    # Avoid duplication if city already contains state
                    if state.lower() in city.lower():
                        data['location'] = city
                    else:
                        data['location'] = f"{city}, {state}"
                elif 'city' in data:
                    data['location'] = data['city']
                elif 'state' in data:
                    data['location'] = data['state']
                
                # Log coach extraction details
                coach_name = data.get('name', 'Unknown')
                coach_phone = data.get('phone', 'No phone')
                coach_email = data.get('email', 'No email')
                coach_location = data.get('location', 'No location')
                self.logger.info(f"COACH EXTRACTED (JSON): {coach_name} | Phone: {coach_phone} | Email: {coach_email} | Location: {coach_location}")
                
            else:
                self.logger.warning("No 'd' key found in coach JSON data")
                
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse coach JSON: {e}")
        except Exception as e:
            self.logger.error(f"Error extracting coach from JSON: {e}")
        
        return data
    
    def extract_player_fields(self, html: str, url: str) -> Dict[str, Any]:
        """Extract player specific fields"""
        soup = BeautifulSoup(html, 'html.parser')
        data = {'type': 'player', 'url': url, 'scraped_at': datetime.now().isoformat()}
        
        # Direct ID extractions (try multiple approaches)
        id_fields = {
            'playerAddress': 'address',
            'playerPhone': 'phone',
            'playerName': 'name',
            'loc_id_details': 'location_id',
            'object_id_details': 'object_id'
        }
        
        for field_id, key in id_fields.items():
            # Try ID first
            element = soup.find(attrs={'id': field_id})
            if element:
                value = element.get('value') or element.get_text(strip=True)
                if value and value.strip():
                    if key == 'phone':
                        data[key] = self.format_phone(value)
                    else:
                        data[key] = value
        
        # Enhanced name extraction - try multiple sources
        if not data.get('name'):
            # Try h1 tag first
            h1_elem = soup.find('h1')
            if h1_elem:
                h1_text = h1_elem.get_text(strip=True)
                if h1_text and len(h1_text) > 3:
                    data['name'] = h1_text
            else:
                # Try title tag
                title_elem = soup.find('title')
                if title_elem:
                    title_text = title_elem.get_text(strip=True)
                    # Extract name from title (remove " - Basketball Player in Noida" part)
                    if ' - ' in title_text:
                        data['name'] = title_text.split(' - ')[0]
                    else:
                        data['name'] = title_text
        
        # Enhanced location extraction
        location_patterns = [
            r'<i class="fa-solid fa-location-dot"></i>\s*([^<\n]+?)</p>',
            r'<i class="fa-solid fa-location-dot"></i>\s*([^<\n]+)',
            r'<i class="fa-solid fa-location-dot"></i>\s*([^<]+?)(?=<|$)',
            r'Location[:\s]*([^<\n]+)',
            r'Address[:\s]*([^<\n]+)'
        ]
        
        for pattern in location_patterns:
            location_match = re.search(pattern, html, re.IGNORECASE)
            if location_match:
                location_text = location_match.group(1).strip()
                # Clean up location text and avoid long descriptions
                if (location_text and 
                    len(location_text) > 3 and 
                    len(location_text) < 200 and  # Avoid very long text
                    location_text != '-' and
                    not any(bad in location_text.lower() for bad in ['book coaching', 'training schedule', 'free trial', 'description'])):
                    data['location'] = location_text
                    break
        
        # Enhanced email extraction (avoid generic emails and empty values)
        email_patterns = [
            r'<i class="fa-regular fa-envelope"></i>\s*([^<\n]+@[^<\n]+)',
            r'<i class="fa-regular fa-envelope"></i>\s*([^<]*)</p>',
            r'Email[:\s]*([^<\n]+@[^<\n]+)',
            r'Contact[:\s]*([^<\n]+@[^<\n]+)',
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        ]
        
        for pattern in email_patterns:
            email_match = re.search(pattern, html, re.IGNORECASE)
            if email_match:
                email_text = email_match.group(1).strip()
                # Skip generic emails, empty values, and malformed text
                if (email_text and 
                    email_text != '-' and 
                    '@' in email_text and
                    len(email_text) < 100 and  # Avoid long malformed text
                    not any(generic in email_text.lower() for generic in ['care@', 'info@', 'support@', 'contact@', 'admin@']) and
                    not any(bad in email_text.lower() for bad in ['book coaching', 'training schedule', 'free trial'])):
                    data['email'] = email_text
                    break
        
        # Enhanced phone extraction
        phone_patterns = [
            r'<i class="fa-solid fa-phone"></i>\s*([^<\n]+)',
            r'Phone[:\s]*([^<\n]+)',
            r'Contact[:\s]*([^<\n]+)',
            r'(\+?[0-9\s\-\(\)]{10,})'
        ]
        
        for pattern in phone_patterns:
            phone_match = re.search(pattern, html, re.IGNORECASE)
            if phone_match:
                phone_text = phone_match.group(1).strip()
                if phone_text and len(re.sub(r'[^0-9]', '', phone_text)) >= 10:
                    data['phone'] = self.format_phone(phone_text)
                    break
        
        # Log player extraction details
        player_name = data.get('name', 'Unknown')
        player_phone = data.get('phone', 'No phone')
        player_email = data.get('email', 'No email')
        player_location = data.get('location', 'No location')
        self.logger.info(f"PLAYER EXTRACTED: {player_name} | Phone: {player_phone} | Email: {player_email} | Location: {player_location}")
        
        return data
    
    def detect_content_type(self, html: str, url: str) -> tuple[str, dict]:
        """Detect content type using brute force - try all extraction methods and pick the best one"""
        
        # Try venue extraction first
        venue_data = self.extract_venue_fields(html, url)
        venue_score = self._calculate_extraction_score(venue_data, 'venue')
        
        # Try player extraction
        player_data = self.extract_player_fields(html, url)
        player_score = self._calculate_extraction_score(player_data, 'player')
        
        # Try coach extraction (both HTML and JSON)
        coach_data = self.extract_coach_fields(html, url)
        coach_score = self._calculate_extraction_score(coach_data, 'coach')
        
        # Debug logging
        self.logger.debug(f"Extraction scores - Venue: {venue_score}, Player: {player_score}, Coach: {coach_score}")
        
        # Return the type with the highest score and its data
        scores = {
            'venue': venue_score,
            'player': player_score,
            'coach': coach_score
        }
        
        data_map = {
            'venue': venue_data,
            'player': player_data,
            'coach': coach_data
        }
        
        best_type = max(scores, key=scores.get)
        
        # Only return the best type if it has a reasonable score
        if scores[best_type] > 0:
            return best_type, data_map[best_type]
        else:
            # Fallback to URL-based detection if all scores are 0
            fallback_type = self._fallback_url_detection(url)
            return fallback_type, data_map.get(fallback_type, {'url': url, 'type': fallback_type, 'scraped_at': datetime.now().isoformat()})
    
    def _calculate_extraction_score(self, data: dict, content_type: str) -> int:
        """Calculate how well the extraction worked (higher score = better match)"""
        score = 0
        
        # Base score for having the right type
        if data.get('type') == content_type:
            score += 10
        
        # Score for having key fields with actual values
        if content_type == 'venue':
            if data.get('name') and data.get('name') != 'Unknown':
                score += 5
            if data.get('phone') and data.get('phone') != 'No phone':
                score += 5
            if data.get('address') and data.get('address') != 'No address':
                score += 5
            if data.get('sport'):
                score += 3
            if data.get('description'):
                score += 2
                
        elif content_type == 'player':
            if data.get('name') and data.get('name') != 'Unknown':
                score += 5
            if data.get('phone') and data.get('phone') != 'No phone':
                score += 5
            if data.get('email') and data.get('email') != 'No email':
                score += 5
            if data.get('location') and data.get('location') != 'No location':
                score += 3
                
        elif content_type == 'coach':
            if data.get('name') and data.get('name') != 'Unknown':
                score += 5
            if data.get('phone') and data.get('phone') != 'No phone':
                score += 5
            if data.get('email') and data.get('email') != 'No email':
                score += 5
            if data.get('location') and data.get('location') != 'No location':
                score += 3
            if data.get('experience'):
                score += 2
            if data.get('education'):
                score += 2
        
        return score
    
    def _fallback_url_detection(self, url: str) -> str:
        """Fallback URL-based detection when brute force fails"""
        url_lower = url.lower()
        
        # Venue patterns
        venue_patterns = [
            '/gym/', '/academy', 'academy', '/school', 'school', 
            '/club', 'club', '/fc', 'fc', '/acad', 'acad',
            '-aid-', '/aid-', 'football-accademy', 'football-academy'
        ]
        if any(pattern in url_lower for pattern in venue_patterns):
            return 'venue'
        
        # Coach patterns
        if 'coach' in url_lower or '-chid-' in url_lower:
            return 'coach' 
        
        # Player patterns
        if 'player' in url_lower or '-pid-' in url_lower:
            return 'player'
        
        return 'unknown'
    
    def scrape_url(self, url: str) -> Dict[str, Any]:
        """Main scraping function that auto-detects type and extracts appropriate fields"""
        try:
            html = self.fetch_page(url)
            if not html:
                return {'url': url, 'type': 'error', 'error': 'Failed to fetch page', 'scraped_at': datetime.now().isoformat()}
            
            # Use brute force detection - tries all extraction methods and picks the best one
            content_type, extracted_data = self.detect_content_type(html, url)
            
            if content_type in ['venue', 'coach', 'player']:
                return extracted_data
            else:
                self.logger.warning(f"UNKNOWN TYPE: {url} - Could not determine content type")
                return {'url': url, 'type': 'unknown', 'error': 'Could not determine content type', 'scraped_at': datetime.now().isoformat()}
        except Exception as e:
            self.logger.error(f"ERROR SCRAPING: {url} - {e}")
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
                    
                    # Detailed summary every 10 records
                    if i % 10 == 0:
                        stats = self.get_processing_stats()
                        self.logger.info(f"SUMMARY: Processed {i}/{total_urls} | Venues: {stats['venues']} | Coaches: {stats['coaches']} | Players: {stats['players']} | Errors: {stats['errors']}")
                    
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
