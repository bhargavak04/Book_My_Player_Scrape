import os
from typing import Dict, Any

class ScraperConfig:
    """Configuration management for the scraper"""
    
    def __init__(self):
        # Auto-save settings
        self.AUTO_SAVE_INTERVAL = int(os.getenv('AUTO_SAVE_INTERVAL', '1000'))
        self.REQUEST_DELAY = float(os.getenv('REQUEST_DELAY', '1.0'))
        
        # File settings
        self.INPUT_FILE = os.getenv('INPUT_FILE', '/app/input/urls.xlsx')
        self.URL_COLUMN = os.getenv('URL_COLUMN', 'url')
        self.START_FROM = int(os.getenv('START_FROM', '0'))
        
        # Network settings
        self.TIMEOUT = int(os.getenv('TIMEOUT', '30'))
        self.MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
        self.USER_AGENT = os.getenv('USER_AGENT', 
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        # Output settings
        self.OUTPUT_DIR = os.getenv('OUTPUT_DIR', '/app/output')
        self.LOG_DIR = os.getenv('LOG_DIR', '/app/logs')
        
        # Performance settings
        self.MAX_WORKERS = int(os.getenv('MAX_WORKERS', '1'))
        self.MEMORY_LIMIT = os.getenv('MEMORY_LIMIT', '2g')
    
    def get_dict(self) -> Dict[str, Any]:
        """Return configuration as dictionary"""
        return {
            'AUTO_SAVE_INTERVAL': self.AUTO_SAVE_INTERVAL,
            'REQUEST_DELAY': self.REQUEST_DELAY,
            'INPUT_FILE': self.INPUT_FILE,
            'URL_COLUMN': self.URL_COLUMN,
            'START_FROM': self.START_FROM,
            'TIMEOUT': self.TIMEOUT,
            'MAX_RETRIES': self.MAX_RETRIES,
            'USER_AGENT': self.USER_AGENT,
            'OUTPUT_DIR': self.OUTPUT_DIR,
            'LOG_DIR': self.LOG_DIR,
            'MAX_WORKERS': self.MAX_WORKERS,
            'MEMORY_LIMIT': self.MEMORY_LIMIT
        }
    
    def print_config(self):
        """Print current configuration"""
        print("=== SCRAPER CONFIGURATION ===")
        for key, value in self.get_dict().items():
            print(f"{key}: {value}")
        print("=" * 30)
