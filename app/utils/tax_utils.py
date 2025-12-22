"""
Tax calculation utilities for country-wise tax handling.
This module provides centralized tax calculation functions that can be used
across the application wherever tax calculations are needed.
"""

from typing import Optional, Dict
from app.db import db


# Tax rates by country (ISO 3166-1 alpha-2 codes)
TAX_RATES = {
    # North America
    "US": {"rate": 0.0, "name": "Sales Tax (State-specific)"},  # Varies by state
    "CA": {"rate": 13.0, "name": "HST"},  # Harmonized Sales Tax (varies by province)
    "MX": {"rate": 16.0, "name": "IVA"},  # Impuesto al Valor Agregado
    
    # Europe
    "GB": {"rate": 20.0, "name": "VAT"},  # Value Added Tax
    "DE": {"rate": 19.0, "name": "MwSt"},  # Mehrwertsteuer
    "FR": {"rate": 20.0, "name": "TVA"},  # Taxe sur la Valeur Ajoutée
    "IT": {"rate": 22.0, "name": "IVA"},  # Imposta sul Valore Aggiunto
    "ES": {"rate": 21.0, "name": "IVA"},  # Impuesto sobre el Valor Añadido
    "NL": {"rate": 21.0, "name": "BTW"},  # Belasting over de Toegevoegde Waarde
    "BE": {"rate": 21.0, "name": "TVA/BTW"},  # Taxe sur la Valeur Ajoutée
    "SE": {"rate": 25.0, "name": "Moms"},  # Mervärdesskatt
    "DK": {"rate": 25.0, "name": "Moms"},  # Merværdiafgift
    "NO": {"rate": 25.0, "name": "MVA"},  # Merverdiavgift
    "FI": {"rate": 24.0, "name": "ALV"},  # Arvonlisävero
    "PL": {"rate": 23.0, "name": "VAT"},  # Value Added Tax
    "PT": {"rate": 23.0, "name": "IVA"},  # Imposto sobre o Valor Acrescentado
    "AT": {"rate": 20.0, "name": "USt"},  # Umsatzsteuer
    "CH": {"rate": 7.7, "name": "MWST"},  # Mehrwertsteuer
    "IE": {"rate": 23.0, "name": "VAT"},  # Value Added Tax
    
    # Asia Pacific
    "IN": {"rate": 18.0, "name": "GST"},  # Goods and Services Tax
    "CN": {"rate": 13.0, "name": "VAT"},  # Value Added Tax
    "JP": {"rate": 10.0, "name": "消費税"},  # Consumption Tax
    "AU": {"rate": 10.0, "name": "GST"},  # Goods and Services Tax
    "NZ": {"rate": 15.0, "name": "GST"},  # Goods and Services Tax
    "SG": {"rate": 8.0, "name": "GST"},  # Goods and Services Tax
    "MY": {"rate": 0.0, "name": "SST"},  # Sales and Service Tax (varies)
    "TH": {"rate": 7.0, "name": "VAT"},  # Value Added Tax
    "ID": {"rate": 11.0, "name": "PPN"},  # Pajak Pertambahan Nilai
    "PH": {"rate": 12.0, "name": "VAT"},  # Value Added Tax
    "VN": {"rate": 10.0, "name": "VAT"},  # Value Added Tax
    "KR": {"rate": 10.0, "name": "부가가치세"},  # Value Added Tax
    "HK": {"rate": 0.0, "name": "No VAT/GST"},  # No sales tax
    "TW": {"rate": 5.0, "name": "VAT"},  # Value Added Tax
    
    # Middle East & Africa
    "AE": {"rate": 5.0, "name": "VAT"},  # Value Added Tax
    "SA": {"rate": 15.0, "name": "VAT"},  # Value Added Tax
    "ZA": {"rate": 15.0, "name": "VAT"},  # Value Added Tax
    "IL": {"rate": 17.0, "name": "VAT"},  # Value Added Tax
    "TR": {"rate": 18.0, "name": "KDV"},  # Katma Değer Vergisi
    "EG": {"rate": 14.0, "name": "VAT"},  # Value Added Tax
    
    # South America
    "BR": {"rate": 17.0, "name": "ICMS"},  # Imposto sobre Circulação de Mercadorias (varies)
    "AR": {"rate": 21.0, "name": "IVA"},  # Impuesto al Valor Agregado
    "CL": {"rate": 19.0, "name": "IVA"},  # Impuesto al Valor Agregado
    "CO": {"rate": 19.0, "name": "IVA"},  # Impuesto al Valor Agregado
    "PE": {"rate": 18.0, "name": "IGV"},  # Impuesto General a las Ventas
}

# Default tax rate if country not found
DEFAULT_TAX_RATE = 0.0


async def get_store_country(store_id: str) -> Optional[str]:
    """
    Retrieve the country code for a given store.
    
    Args:
        store_id: The store identifier
        
    Returns:
        Country code (e.g., 'US', 'IN', 'GB') or None if not found
    """
    try:
        store = await db.Stores.find_one(
            {"store_id": store_id},
            {"_id": 0, "address.country": 1}
        )
        
        if store and "address" in store and "country" in store["address"]:
            country = store["address"]["country"]
            # Convert to uppercase for consistency
            return country.upper() if country else None
        
        return None
    except Exception as e:
        print(f"Error retrieving store country: {e}")
        return None


def get_tax_rate_for_country(country_code: Optional[str]) -> float:
    """
    Get the tax rate for a specific country.
    
    Args:
        country_code: Two-letter country code (ISO 3166-1 alpha-2)
        
    Returns:
        Tax rate as a percentage (e.g., 18.0 for 18%)
    """
    if not country_code:
        return DEFAULT_TAX_RATE
    
    country_code = country_code.upper()
    
    if country_code in TAX_RATES:
        return TAX_RATES[country_code]["rate"]
    
    return DEFAULT_TAX_RATE


def get_tax_info_for_country(country_code: Optional[str]) -> Dict[str, any]:
    """
    Get comprehensive tax information for a specific country.
    
    Args:
        country_code: Two-letter country code (ISO 3166-1 alpha-2)
        
    Returns:
        Dictionary containing tax rate and tax name
    """
    if not country_code:
        return {"rate": DEFAULT_TAX_RATE, "name": "No Tax"}
    
    country_code = country_code.upper()
    
    if country_code in TAX_RATES:
        return TAX_RATES[country_code]
    
    return {"rate": DEFAULT_TAX_RATE, "name": "Unknown"}


async def get_tax_rate_for_store(store_id: str) -> float:
    """
    Get the tax rate for a specific store based on its country.
    
    Args:
        store_id: The store identifier
        
    Returns:
        Tax rate as a percentage (e.g., 18.0 for 18%)
    """
    country_code = await get_store_country(store_id)
    return get_tax_rate_for_country(country_code)


async def get_tax_info_for_store(store_id: str) -> Dict[str, any]:
    """
    Get comprehensive tax information for a specific store.
    
    Args:
        store_id: The store identifier
        
    Returns:
        Dictionary containing tax rate and tax name
    """
    country_code = await get_store_country(store_id)
    return get_tax_info_for_country(country_code)


def calculate_tax_amount(unit_price: float, tax_rate: float, quantity: int = 1) -> float:
    """
    Calculate tax amount for a product.
    
    Args:
        unit_price: Price per unit
        tax_rate: Tax rate as a percentage (e.g., 18.0 for 18%)
        quantity: Number of units (default: 1)
        
    Returns:
        Total tax amount
    """
    try:
        unit_price = float(unit_price) if unit_price else 0.0
        tax_rate = float(tax_rate) if tax_rate else 0.0
        quantity = int(quantity) if quantity else 0
        
        tax_per_unit = (unit_price * tax_rate) / 100
        total_tax = tax_per_unit * quantity
        
        return round(total_tax, 2)
    except (ValueError, TypeError):
        return 0.0


def calculate_product_total_with_tax(unit_price: float, tax_rate: float, quantity: int) -> float:
    """
    Calculate total price for a product including tax.
    Formula: quantity * (unit_price + tax_amount)
    Where tax_amount = (unit_price * tax_rate / 100)
    
    Args:
        unit_price: Price per unit
        tax_rate: Tax rate as a percentage (e.g., 18.0 for 18%)
        quantity: Number of units
        
    Returns:
        Total price including tax
    """
    try:
        unit_price = float(unit_price) if unit_price else 0.0
        tax_rate = float(tax_rate) if tax_rate else 0.0
        quantity = int(quantity) if quantity else 0
        
        tax_amount = (unit_price * tax_rate) / 100
        total = quantity * (unit_price + tax_amount)
        
        return round(total, 2)
    except (ValueError, TypeError):
        return 0.0


async def calculate_product_total_for_store(
    store_id: str, 
    unit_price: float, 
    quantity: int,
    override_tax_rate: Optional[float] = None
) -> Dict[str, any]:
    """
    Calculate product total with tax for a specific store.
    Automatically retrieves the tax rate based on store's country.
    
    Args:
        store_id: The store identifier
        unit_price: Price per unit
        quantity: Number of units
        override_tax_rate: Optional tax rate to override country default
        
    Returns:
        Dictionary containing:
        - subtotal: Price without tax
        - tax_rate: Applied tax rate percentage
        - tax_amount: Total tax amount
        - total: Total price including tax
        - tax_name: Name of the tax (GST, VAT, etc.)
    """
    try:
        # Get tax rate
        if override_tax_rate is not None:
            tax_rate = float(override_tax_rate)
            tax_name = "Custom Tax"
        else:
            tax_info = await get_tax_info_for_store(store_id)
            tax_rate = tax_info["rate"]
            tax_name = tax_info["name"]
        
        # Calculate amounts
        unit_price = float(unit_price) if unit_price else 0.0
        quantity = int(quantity) if quantity else 0
        
        subtotal = unit_price * quantity
        tax_amount = calculate_tax_amount(unit_price, tax_rate, quantity)
        total = subtotal + tax_amount
        
        return {
            "subtotal": round(subtotal, 2),
            "tax_rate": tax_rate,
            "tax_amount": tax_amount,
            "total": round(total, 2),
            "tax_name": tax_name
        }
    except Exception as e:
        print(f"Error calculating product total: {e}")
        return {
            "subtotal": 0.0,
            "tax_rate": 0.0,
            "tax_amount": 0.0,
            "total": 0.0,
            "tax_name": "Error"
        }


def format_tax_display(tax_rate: float, tax_name: str) -> str:
    """
    Format tax information for display.
    
    Args:
        tax_rate: Tax rate as a percentage
        tax_name: Name of the tax
        
    Returns:
        Formatted string (e.g., "GST (18%)" or "VAT (20%)")
    """
    if tax_rate == 0:
        return "No Tax"
    
    return f"{tax_name} ({tax_rate}%)"
