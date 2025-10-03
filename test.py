import requests
import re
from bs4 import BeautifulSoup
from typing import Dict, Any
import time
import pandas as pd

class BookMyPlayerScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def fetch_page(self, url: str) -> str:
        """Fetch page content with error handling"""
        try:
            response = self.session.get(url, timeout=20)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return ""
    
    def format_phone(self, phone_str: str) -> str:
        """Format phone number properly"""
        if not phone_str:
            return ""
        # Extract digits only
        digits = re.sub(r'[^0-9]', '', str(phone_str))
        if len(digits) == 10:
            return digits
        elif len(digits) > 10:
            return digits[-10:]  # Take last 10 digits
        return phone_str
    
    def extract_venue_fields(self, html: str, url: str) -> Dict[str, Any]:
        """Extract venue/academy specific fields"""
        soup = BeautifulSoup(html, 'html.parser')
        data = {'type': 'venue', 'url': url}
        
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
        data = {'type': 'coach', 'url': url}
        
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
        data = {'type': 'player', 'url': url}
        
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
        print(f"Processing: {url}")
        
        html = self.fetch_page(url)
        if not html:
            return {'url': url, 'type': 'error', 'error': 'Failed to fetch page'}
        
        content_type = self.detect_content_type(html, url)
        print(f"Detected type: {content_type}")
        
        if content_type == 'venue':
            return self.extract_venue_fields(html, url)
        elif content_type == 'coach':
            return self.extract_coach_fields(html, url)
        elif content_type == 'player':
            return self.extract_player_fields(html, url)
        else:
            return {'url': url, 'type': 'unknown', 'error': 'Could not determine content type'}
    
    def scrape_multiple_urls(self, urls: list) -> list:
        """Scrape multiple URLs and return results"""
        results = []
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] Processing: {url}")
            try:
                result = self.scrape_url(url)
                results.append(result)
                print(f"✓ Success: {result.get('type', 'unknown')} - {result.get('name', 'N/A')}")
                time.sleep(1)  # Be respectful with requests
            except Exception as e:
                print(f"✗ Error: {e}")
                results.append({'url': url, 'type': 'error', 'error': str(e)})
        return results
    
    def save_to_excel(self, results: list, filename: str = "scraped_data.xlsx"):
        """Save results to Excel with separate sheets for each type"""
        venue_data = [r for r in results if r.get('type') == 'venue']
        coach_data = [r for r in results if r.get('type') == 'coach']
        player_data = [r for r in results if r.get('type') == 'player']
        error_data = [r for r in results if r.get('type') in ['error', 'unknown']]
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            if venue_data:
                pd.DataFrame(venue_data).to_excel(writer, sheet_name='Venues', index=False)
            if coach_data:
                pd.DataFrame(coach_data).to_excel(writer, sheet_name='Coaches', index=False)
            if player_data:
                pd.DataFrame(player_data).to_excel(writer, sheet_name='Players', index=False)
            if error_data:
                pd.DataFrame(error_data).to_excel(writer, sheet_name='Errors', index=False)
        
        print(f"\n✓ Data saved to {filename}")
        print(f"  - Venues: {len(venue_data)}")
        print(f"  - Coaches: {len(coach_data)}")
        print(f"  - Players: {len(player_data)}")
        print(f"  - Errors: {len(error_data)}")

# Example usage
if __name__ == "__main__":
    scraper = BookMyPlayerScraper()
    
    # Test URLs
    test_urls = [
        "https://www.bookmyplayer.com/gym/new-ajinkyatara-fitness-santacruz-west-mumbai-aid-41388",
        "https://www.bookmyplayer.com/maheshmhaske-arts-coach-in-shaktinagarjammu-jammuandkashmir-chid-660", 
        "https://www.bookmyplayer.com/dilnawaz-arshad-batting-all-rounder-0-cricket-player-in-delhi-delhi-pid-2586"
    ]
    
    # Scrape all URLs
    results = scraper.scrape_multiple_urls(test_urls)
    
    # Save to Excel
    scraper.save_to_excel(results, "bookmyplayer_test_results.xlsx")
    
    # Print summary
    print("\n" + "="*80)
    print("EXTRACTION SUMMARY:")
    print("="*80)
    
    for result in results:
        print(f"\n🔗 {result['url']}")
        print(f"📋 Type: {result['type']}")
        if result['type'] != 'error':
            for key, value in result.items():
                if key not in ['url', 'type'] and value:
                    print(f"   {key}: {value}")
