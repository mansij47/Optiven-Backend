"""
PDF Invoice Extraction Utilities
Contains helper functions for extracting data from PDF invoices
"""

import pdfplumber
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import warnings

warnings.filterwarnings('ignore')


# ===================== REGEX PATTERNS (CONSTANTS) =====================
# Number patterns
PATTERN_NUMBER = re.compile(r'[-+]?\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?')
PATTERN_CURRENCY = re.compile(r'(?:USD|EUR|GBP|INR|AUD|CAD|₹|Rs\.?|\$|€|£|¥)', re.IGNORECASE)
PATTERN_AMOUNT = re.compile(r'(?:USD|EUR|GBP|INR|AUD|CAD|₹|Rs\.?|\$|€|£|¥)?\s*[-+]?\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2,})?', re.IGNORECASE)

# Date patterns
DATE_FORMATS = [
    r'\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b',
    r'\b\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2}\b',
    r'\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[,\s]+\d{2,4}\b',
    r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2}[,\s]+\d{2,4}\b',
]
PATTERN_DATE = re.compile('|'.join(f'({fmt})' for fmt in DATE_FORMATS), re.IGNORECASE)

# Contact patterns
PATTERN_EMAIL = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PATTERN_PHONE = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}|\+?\d{10,15}')

# Tax ID patterns
PATTERN_GST_IN = re.compile(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b')
PATTERN_VAT_EU = re.compile(r'\b[A-Z]{2}\d{8,12}\b')
PATTERN_EIN_US = re.compile(r'\b\d{2}-\d{7}\b')


# ===================== UTILITY FUNCTIONS =====================
def clean_text(text: str) -> str:
    """Clean and normalize text"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', str(text))
    return text.strip()


def normalize_number(value: str) -> Optional[float]:
    """Convert string to float, handling various formats"""
    if not value:
        return None
    
    value = str(value).strip()
    value = re.sub(r'^(?:USD|EUR|GBP|INR|AUD|CAD|₹|Rs\.?|\$|€|£|¥)\s*', '', value, flags=re.IGNORECASE)
    value = re.sub(r'[^\d.,\-]', '', value)
    
    if ',' in value and '.' in value:
        if value.rindex(',') > value.rindex('.'):
            value = value.replace('.', '').replace(',', '.')
        else:
            value = value.replace(',', '')
    elif ',' in value:
        if len(value.split(',')[-1]) == 2:
            value = value.replace(',', '.')
        else:
            value = value.replace(',', '')
    
    try:
        return float(value)
    except ValueError:
        return None


def extract_pdf_text(pdf_path: Path) -> Tuple[str, List[Dict]]:
    """Extract text from PDF using pdfplumber"""
    full_text_parts = []
    all_tables = []
    
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ''
                if text:
                    full_text_parts.append(text)
                
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        all_tables.append({
                            'page': page_num,
                            'data': table
                        })
        
        full_text = '\n\n'.join(full_text_parts)
        return full_text, all_tables
        
    except Exception as e:
        print(f"Error extracting PDF: {e}")
        return "", []
