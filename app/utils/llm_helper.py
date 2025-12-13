"""
LLM Helper Functions
Validates and enhances extracted invoice data using Gemini AI
"""

import os
import re
import json
from typing import Dict, Any, Optional
import warnings

warnings.filterwarnings('ignore')

# Try to import Gemini API
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️  google-generativeai not installed")


# Initialize Gemini model (singleton pattern)
_gemini_model = None
_model_initialized = False


def _initialize_gemini() -> Optional[Any]:
    """Initialize Gemini model once"""
    global _gemini_model, _model_initialized
    
    if _model_initialized:
        return _gemini_model
    
    _model_initialized = True
    
    if not GEMINI_AVAILABLE:
        print("⚠️  LLM validation disabled - google-generativeai not installed")
        return None
    
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("⚠️  LLM validation disabled - GEMINI_API_KEY not found")
        return None
    
    try:
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel('models/gemini-flash-latest')
        print("✅ LLM validator initialized (Gemini Flash Latest)")
        return _gemini_model
    except Exception as e:
        print(f"❌ Failed to initialize LLM: {e}")
        return None


def _create_validation_prompt(
    extracted_data: Dict[str, Any], 
    full_text: str, 
    data_type: str
) -> str:
    """Create prompt for LLM to validate and correct data"""
    # Remove None values for cleaner prompt
    data_for_review = {k: v for k, v in extracted_data.items() if v is not None}
    
    prompt = f"""You are an expert invoice data validator. Review the extracted {data_type} data and correct any errors.

EXTRACTED {data_type.upper()} DATA (may contain errors):
{json.dumps(data_for_review, indent=2)}

FULL INVOICE TEXT:
{full_text}

YOUR TASK:
1. Compare extracted data with the full invoice text carefully
2. Fix CRITICAL errors:
   - Names containing numbers, dates, or irrelevant text (like "Total", "Logo", "123", invoice numbers)
   - Email addresses in wrong fields
   - Phone numbers in name/address fields
   - **INVOICE NUMBERS appearing as PIN codes** (invoice numbers are NOT pin codes)
   - Dates appearing as names
   - Addresses mixed with other data
3. Extract correct values from the full text:
   - For vendor: Look at TOP of invoice (header area), company name, payment account name
   - **Vendor Name vs Store Name Logic:**
     * If you see two similar names at the top (e.g., "R.K. Power Solutions" and "R.K. Electronics Pvt. Ltd")
     * The one WITHOUT legal suffixes (trade name/brand name) = **vendor_name**
     * The one WITH legal suffixes (Pvt. Ltd, Ltd., LLC, Inc., Corp., Private Limited, etc.) = **store_name**
     * Example: "R.K. Power Solutions" → vendor_name, "R.K. Electronics Pvt. Ltd" → store_name
   - For customer: Look at "Billed To", "Invoice To", "Issued to", "Client" sections
   - Extract complete addresses (street + city + state + zip)
   - **PIN/ZIP code: MUST come from address line (e.g., "City, ST 12345" or "USA 31036"), NOT from invoice header**
   - Clean phone numbers to standard format
4. Data type validation:
   - name: MUST be text only, NO numbers or dates
   - email: MUST be valid email format
   - phone: MUST be phone number format
   - **pincode: MUST be 5-6 digits from ADDRESS, NOT invoice number**
   - address: MUST be street address format
   - tax_id/gst_number: Tax identification format
5. CRITICAL PINCODE RULES:
   - Find the address first
   - Extract the 5-6 digit number from the END of the address
   - Common patterns: "City, ST 12345" or "City, Country 123456"
   - If the extracted pincode matches the invoice number, it's WRONG - find the real pincode from address
6. If a field is truly not found in text, return null (not string "null")
7. Never mix vendor and customer data

**IMPORTANT JSON RULES:**
- Return valid JSON with null (not "null" string) for missing fields
- Numbers must be numeric type, not strings
- Example: {{"name": "ABC Corp", "product_discount": null, "product_quantity": 10.0}}

RETURN ONLY VALID JSON (no markdown, no explanation):
{json.dumps({k: "..." if isinstance(v, str) else ("null" if v is None else "...") for k, v in extracted_data.items()}, indent=2)}"""
    
    return prompt


def _parse_llm_response(response_text: str, original_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse LLM JSON response and clean data"""
    try:
        response_text = response_text.strip()
        
        # Remove markdown code blocks
        if response_text.startswith('```'):
            response_text = re.sub(r'^```(?:json)?\n', '', response_text)
            response_text = re.sub(r'\n```$', '', response_text)
        
        # Extract JSON if there's extra text (find first { to last })
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(0)
        
        # Parse JSON
        corrected_data = json.loads(response_text)
        
        # Merge with original data structure and clean values
        result = original_data.copy()
        for key, value in corrected_data.items():
            if key in result:
                # Convert string 'null' to None
                if value in ['null', 'None', '', 'undefined', 'N/A', 'n/a']:
                    result[key] = None
                # Keep the corrected value
                else:
                    result[key] = value
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse LLM response: {e}")
        print(f"Response: {response_text[:300]}")
        return original_data
    except Exception as e:
        print(f"❌ Error processing LLM response: {e}")
        return original_data


def validate_and_enhance(
    extracted_data: Dict[str, Any], 
    full_text: str, 
    data_type: str = "data"
) -> Dict[str, Any]:
    """
    Validate and enhance extracted data using LLM
    
    Args:
        extracted_data: Data extracted by basic methods (may have errors)
        full_text: Full text from PDF
        data_type: Type of data (vendor, customer, financial, etc.)
    
    Returns:
        Corrected and enhanced data
    """
    model = _initialize_gemini()
    
    if not model:
        print(f"⚠️  LLM not available - returning original {data_type} data")
        return extracted_data
    
    try:
        print(f"🤖 Validating {data_type} data with LLM...")
        print(f"📝 Before LLM: {json.dumps({k: v for k, v in extracted_data.items() if v is not None}, indent=2)}")
        
        prompt = _create_validation_prompt(extracted_data, full_text, data_type)
        response = model.generate_content(prompt)
        corrected_data = _parse_llm_response(response.text, extracted_data)
        
        print(f"✅ After LLM: {json.dumps({k: v for k, v in corrected_data.items() if v is not None}, indent=2)}")
        print(f"✅ {data_type.capitalize()} validation completed")
        return corrected_data
        
    except Exception as e:
        print(f"⚠️  LLM validation failed: {e}")
        return extracted_data


# Convenience functions for specific data types
def validate_vendor_data(extracted_data: Dict, full_text: str) -> Dict:
    """Validate vendor data"""
    return validate_and_enhance(extracted_data, full_text, "vendor")


def validate_customer_data(extracted_data: Dict, full_text: str) -> Dict:
    """Validate customer data"""
    return validate_and_enhance(extracted_data, full_text, "customer")


def validate_financial_data(extracted_data: Dict, full_text: str) -> Dict:
    """Validate financial data"""
    return validate_and_enhance(extracted_data, full_text, "financial")
