from fastapi import APIRouter, File, UploadFile, Query, HTTPException, Request, BackgroundTasks
from typing import List
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import asyncio

from app.models.invoice_model import (
    ExtractionType,
    ExtractionResponse,
    InvoiceDataModel
)
from app.services.invoice_extraction_service import extract_invoice_data
from app.services.cloudinary_service import (
    upload_pdf_from_path,
    is_cloudinary_configured
)

router = APIRouter()


def upload_to_cloudinary_background(file_path: str, filename: str):
    """Background task to upload PDF to Cloudinary"""
    try:
        if is_cloudinary_configured():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = Path(filename).stem
            public_id = f"{base_name}_{timestamp}"
            
            print(f"📤 [Background] Uploading invoice PDF to Cloudinary: {filename}")
            upload_result = upload_pdf_from_path(
                file_path=file_path,
                folder="optiven_pdfs/invoices",
                public_id=public_id
            )
            
            if upload_result and upload_result.get("secure_url"):
                print(f"✅ [Background] Invoice PDF uploaded: {upload_result['secure_url']}")
            
            # Clean up temp file after upload
            try:
                import os
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"🗑️ [Background] Cleaned up temp file: {file_path}")
            except Exception as cleanup_error:
                print(f"⚠️ [Background] Cleanup error: {cleanup_error}")
    except Exception as e:
        print(f"⚠️ [Background] Cloudinary upload failed: {e}")


@router.get("/extraction-types")
async def get_extraction_types():
    """Get list of available extraction types"""
    return {
        "extraction_types": [
            {"type": "all", "description": "Extract all available data from invoice"},
            {"type": "vendor", "description": "Extract vendor/seller information only"},
            {"type": "customer", "description": "Extract customer/client information only"},
            {"type": "financial", "description": "Extract financial summary (subtotal, tax, total, etc.)"},
            {"type": "items", "description": "Extract line items/products only"},
            {"type": "payment", "description": "Extract payment information only"},
            {"type": "dates", "description": "Extract dates (invoice date, due date, etc.)"}
        ]
    }


@router.post("/extract", response_model=ExtractionResponse)
async def extract_invoice(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF invoice file to extract"),
    extraction_type: ExtractionType = Query(
        ExtractionType.ALL,
        description="Type of data to extract: 'all', 'vendor', 'customer', 'financial', 'items', 'payment', or 'dates'"
    ),
    use_llm: bool = Query(
        True,
        description="Use LLM for validation and correction of extracted data"
    )
):
    """
    Extract structured data from PDF invoice based on extraction type
    
    - **file**: PDF invoice file to process
    - **extraction_type**: Type of data to extract (vendor/customer/financial/items/payment/dates/all)
    - **use_llm**: Enable AI validation and correction (default: true)
    
    Returns structured data based on the extraction type:
    - **vendor**: Vendor/seller information only
    - **customer**: Customer/client information only
    - **financial**: Financial summary (subtotal, tax, total, etc.)
    - **items**: Line items/products only
    - **payment**: Payment information only
    - **dates**: Date information only
    - **all**: Complete invoice data
    """
    
    # Check authentication
    user = request.state.user
    if not user or user.get("role") not in ["admin", "procurement", "sales"]:
        raise HTTPException(
            status_code=403, 
            detail="Forbidden: Admin, Procurement, or Sales access required."
        )
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PDF files are supported."
        )
    
    # Create temporary file to save uploaded PDF
    temp_dir = None
    try:
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        temp_file_path = Path(temp_dir) / file.filename
        
        # Save uploaded file
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Extract data using service
        invoice_data = await extract_invoice_data(
            pdf_path=temp_file_path,
            extraction_type=extraction_type,
            use_llm=use_llm
        )
        
        # Create metadata
        metadata = {
            'filename': file.filename,
            'extraction_date': datetime.now().isoformat(),
            'extraction_type': extraction_type.value,
            'llm_validation': use_llm,
            'status': 'success',
            'extracted_by': user.get('username', 'unknown')
        }
        
        # Upload PDF to Cloudinary in background (non-blocking)
        if is_cloudinary_configured():
            # Copy file to a persistent temp location for background upload
            import os
            persistent_temp = tempfile.mktemp(suffix='.pdf')
            shutil.copy2(str(temp_file_path), persistent_temp)
            
            # Schedule background upload (won't block response)
            background_tasks.add_task(
                upload_to_cloudinary_background,
                persistent_temp,
                file.filename
            )
            metadata['cloudinary_upload'] = 'scheduled'
        
        return ExtractionResponse(
            success=True,
            message=f"Invoice data extracted successfully ({extraction_type.value})",
            data=invoice_data,
            metadata=metadata
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e)
        )
    except Exception as e:
        import traceback
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "type": type(e).__name__,
                "traceback": traceback.format_exc()
            }
        )
    finally:
        # Cleanup temporary files
        if temp_dir and Path(temp_dir).exists():
            shutil.rmtree(temp_dir)
        # Close uploaded file
        await file.close()


@router.post("/extract-multiple", response_model=ExtractionResponse)
async def extract_multiple_types(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF invoice file to extract"),
    extraction_types: List[ExtractionType] = Query(
        ...,
        description="Multiple extraction types (e.g., vendor, customer, financial)"
    ),
    use_llm: bool = Query(True, description="Use LLM for validation")
):
    """
    Extract multiple data types from PDF invoice in one request
    
    - **file**: PDF invoice file
    - **extraction_types**: List of data types to extract (e.g., ['vendor', 'customer', 'financial'])
    - **use_llm**: Enable AI validation
    
    Example: ?extraction_types=vendor&extraction_types=customer&extraction_types=financial
    """
    
    # Check authentication
    user = request.state.user
    if not user or user.get("role") not in ["admin", "procurement", "sales"]:
        raise HTTPException(
            status_code=403, 
            detail="Forbidden: Admin, Procurement, or Sales access required."
        )
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PDF files are supported."
        )
    
    # If 'all' is in the list, just extract all
    if ExtractionType.ALL in extraction_types:
        return await extract_invoice(request, background_tasks, file, ExtractionType.ALL, use_llm)
    
    # Extract all data once
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        temp_file_path = Path(temp_dir) / file.filename
        
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Extract all data
        full_result = await extract_invoice_data(
            pdf_path=temp_file_path,
            extraction_type=ExtractionType.ALL,
            use_llm=use_llm
        )
        
        # Filter the response to only include requested types
        filtered_data = InvoiceDataModel(
            invoice_number=full_result.invoice_number,
            document_type=full_result.document_type
        )
        
        if ExtractionType.DATES in extraction_types:
            filtered_data.dates = full_result.dates
        if ExtractionType.VENDOR in extraction_types:
            filtered_data.vendor = full_result.vendor
        if ExtractionType.CUSTOMER in extraction_types:
            filtered_data.customer = full_result.customer
        if ExtractionType.FINANCIAL in extraction_types:
            filtered_data.financial = full_result.financial
        if ExtractionType.PAYMENT in extraction_types:
            filtered_data.payment = full_result.payment
        if ExtractionType.ITEMS in extraction_types:
            filtered_data.items_data = full_result.items_data
        
        metadata = {
            'filename': file.filename,
            'extraction_date': datetime.now().isoformat(),
            'extraction_type': [et.value for et in extraction_types],
            'llm_validation': use_llm,
            'status': 'success',
            'extracted_by': user.get('username', 'unknown')
        }
        
        # Upload PDF to Cloudinary in background (non-blocking)
        if is_cloudinary_configured():
            import os
            persistent_temp = tempfile.mktemp(suffix='.pdf')
            shutil.copy2(str(temp_file_path), persistent_temp)
            
            background_tasks.add_task(
                upload_to_cloudinary_background,
                persistent_temp,
                file.filename
            )
            metadata['cloudinary_upload'] = 'scheduled'
        
        return ExtractionResponse(
            success=True,
            message=f"Invoice data extracted successfully (multiple types)",
            data=filtered_data,
            metadata=metadata
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    finally:
        if temp_dir and Path(temp_dir).exists():
            shutil.rmtree(temp_dir)
        await file.close()
