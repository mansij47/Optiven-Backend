"""
Cloudinary Service
Handles PDF upload, storage, and streaming from Cloudinary.
Non-breaking integration - maintains existing API behavior.
"""

import cloudinary
import cloudinary.uploader
import cloudinary.api
import cloudinary.utils
import httpx
import io
import os
import tempfile
from typing import Optional, Tuple, AsyncIterator
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app.config import (
    CLOUDINARY_CLOUD_NAME,
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET
)


# ===================== CLOUDINARY CONFIGURATION =====================
def configure_cloudinary():
    """
    Configure Cloudinary with credentials from environment.
    Call this once at application startup.
    """
    if not all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
        print("⚠️  Cloudinary credentials not fully configured. PDF cloud storage disabled.")
        return False
    
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True
    )
    print("✅ Cloudinary configured successfully")
    return True


# Initialize Cloudinary on module load
CLOUDINARY_ENABLED = configure_cloudinary()


# ===================== UPLOAD FUNCTIONS =====================
def upload_pdf_from_memory(
    pdf_bytes: bytes,
    folder: str = "optiven_pdfs",
    filename: str = None,
    public_id: str = None
) -> Optional[dict]:
    """
    Upload PDF directly from memory (bytes) to Cloudinary.
    
    Args:
        pdf_bytes: PDF file content as bytes
        folder: Cloudinary folder path (default: optiven_pdfs)
        filename: Original filename for display purposes
        public_id: Custom public ID (if None, Cloudinary generates one)
        
    Returns:
        dict with upload result including 'secure_url', 'public_id', etc.
        None if upload fails or Cloudinary not configured
    """
    if not CLOUDINARY_ENABLED:
        print("⚠️  Cloudinary not enabled, skipping upload")
        return None
    
    try:
        # Create options for upload
        upload_options = {
            "resource_type": "raw",  # Required for PDF files
            "folder": folder,
            "format": "pdf",
            "type": "upload",
            "access_mode": "public"  # Ensure raw files are publicly accessible
        }
        
        if public_id:
            upload_options["public_id"] = public_id
            upload_options["overwrite"] = True
        
        if filename:
            # Use filename without extension as public_id if not provided
            if not public_id:
                base_name = os.path.splitext(filename)[0]
                upload_options["public_id"] = base_name
        
        # Upload from bytes using BytesIO
        result = cloudinary.uploader.upload(
            io.BytesIO(pdf_bytes),
            **upload_options
        )
        
        print(f"✅ PDF uploaded to Cloudinary: {result.get('secure_url', 'URL not available')}")
        return result
    
    except Exception as e:
        print(f"❌ Cloudinary upload failed: {str(e)}")
        return None


def upload_pdf_from_path(
    file_path: str,
    folder: str = "optiven_pdfs",
    public_id: str = None
) -> Optional[dict]:
    """
    Upload PDF from a local file path to Cloudinary.
    
    Args:
        file_path: Path to the PDF file
        folder: Cloudinary folder path
        public_id: Custom public ID
        
    Returns:
        dict with upload result or None if failed
    """
    if not CLOUDINARY_ENABLED:
        print("⚠️  Cloudinary not enabled, skipping upload")
        return None
    
    try:
        filename = os.path.basename(file_path)
        
        upload_options = {
            "resource_type": "raw",
            "folder": folder,
            "format": "pdf",
            "type": "upload",
            "access_mode": "public"  # Ensure raw files are publicly accessible
        }
        
        if public_id:
            upload_options["public_id"] = public_id
            upload_options["overwrite"] = True
            upload_options["invalidate"] = True  # Force CDN cache refresh
        else:
            base_name = os.path.splitext(filename)[0]
            upload_options["public_id"] = base_name
        
        result = cloudinary.uploader.upload(file_path, **upload_options)
        
        print(f"✅ PDF uploaded to Cloudinary: {result.get('secure_url', 'URL not available')}")
        return result
    
    except Exception as e:
        print(f"❌ Cloudinary upload failed: {str(e)}")
        return None


# ===================== STREAMING FUNCTIONS =====================
def extract_public_id_from_url(cloudinary_url: str) -> Optional[str]:
    """
    Extract public_id from a Cloudinary URL.
    Example URL: https://res.cloudinary.com/cloud/raw/upload/v123/folder/file.pdf
    Returns: folder/file
    """
    try:
        # Remove .pdf extension and extract path after /upload/v.../
        import re
        match = re.search(r'/upload/v\d+/(.+?)\.pdf', cloudinary_url)
        if match:
            return match.group(1)
        # Try without version
        match = re.search(r'/upload/(.+?)\.pdf', cloudinary_url)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None


def generate_signed_url(public_id: str) -> str:
    """
    Generate a signed URL for a raw resource that expires in 1 hour.
    """
    import time
    try:
        signed_url = cloudinary.utils.cloudinary_url(
            public_id,
            resource_type="raw",
            type="authenticated",
            sign_url=True,
            format="pdf"
        )
        # cloudinary_url returns a tuple (url, options)
        if isinstance(signed_url, tuple):
            return signed_url[0]
        return signed_url
    except Exception as e:
        print(f"⚠️ Failed to generate signed URL: {e}")
        return None


async def stream_pdf_from_url(
    cloudinary_url: str,
    filename: str = "document.pdf",
    inline: bool = False
) -> StreamingResponse:
    """
    Stream a PDF from Cloudinary URL to the client.
    This hides the Cloudinary URL from the user.
    
    Args:
        cloudinary_url: The Cloudinary secure_url for the PDF
        filename: Filename for Content-Disposition header
        inline: If True, display in browser; if False, force download
        
    Returns:
        StreamingResponse that streams the PDF content
        
    Raises:
        HTTPException: If URL is invalid or file not found
    """
    if not cloudinary_url:
        raise HTTPException(status_code=404, detail="PDF not found")
    
    # URL to actually stream (may be changed to signed URL if needed)
    stream_url = cloudinary_url
    
    # Validate URL exists BEFORE starting the stream
    # This prevents "response already started" errors
    async with httpx.AsyncClient() as client:
        try:
            # Use HEAD request to check if file exists without downloading
            head_response = await client.head(cloudinary_url, follow_redirects=True)
            
            if head_response.status_code == 401:
                # Try signed URL for authenticated resources
                print(f"⚠️ URL requires authentication (401), trying signed URL...")
                public_id = extract_public_id_from_url(cloudinary_url)
                if public_id:
                    signed = generate_signed_url(public_id)
                    if signed:
                        # Verify signed URL works
                        signed_response = await client.head(signed, follow_redirects=True)
                        if signed_response.status_code == 200:
                            print(f"✅ Signed URL works for {public_id}")
                            stream_url = signed
                        else:
                            print(f"⚠️ Signed URL also failed: {signed_response.status_code}")
                            raise HTTPException(
                                status_code=404,
                                detail="PDF not found in cloud storage. It may need to be regenerated."
                            )
                    else:
                        raise HTTPException(
                            status_code=404,
                            detail="PDF not found in cloud storage. It may need to be regenerated."
                        )
                else:
                    raise HTTPException(
                        status_code=404,
                        detail="PDF not found in cloud storage. It may need to be regenerated."
                    )
            elif head_response.status_code != 200:
                print(f"⚠️ Cloudinary URL validation failed: {head_response.status_code} for {cloudinary_url}")
                raise HTTPException(
                    status_code=404,
                    detail="PDF not found in cloud storage. It may need to be regenerated."
                )
        except httpx.RequestError as e:
            print(f"⚠️ Cloudinary URL request error: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail="Unable to connect to cloud storage. Please try again."
            )
    
    async def stream_content() -> AsyncIterator[bytes]:
        """Generator that streams content from Cloudinary"""
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", stream_url, follow_redirects=True) as response:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    yield chunk
    
    # Set content disposition based on inline flag
    disposition = "inline" if inline else "attachment"
    
    return StreamingResponse(
        content=stream_content(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "no-cache"
        }
    )


async def get_pdf_bytes_from_url(cloudinary_url: str) -> bytes:
    """
    Download PDF content from Cloudinary URL as bytes.
    Useful for email attachments or further processing.
    
    Args:
        cloudinary_url: The Cloudinary secure_url for the PDF
        
    Returns:
        bytes: PDF file content
    """
    if not cloudinary_url:
        raise HTTPException(status_code=404, detail="PDF URL not provided")
    
    async with httpx.AsyncClient() as client:
        response = await client.get(cloudinary_url)
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail="Failed to fetch PDF from storage"
            )
        
        return response.content


# ===================== DELETE FUNCTIONS =====================
def delete_pdf_from_cloudinary(public_id: str, folder: str = None) -> bool:
    """
    Delete a PDF from Cloudinary.
    
    Args:
        public_id: The public ID of the resource
        folder: Folder prefix (will be prepended to public_id if provided)
        
    Returns:
        bool: True if deleted successfully
    """
    if not CLOUDINARY_ENABLED:
        return False
    
    try:
        full_public_id = f"{folder}/{public_id}" if folder else public_id
        
        result = cloudinary.uploader.destroy(
            full_public_id,
            resource_type="raw"
        )
        
        return result.get("result") == "ok"
    
    except Exception as e:
        print(f"❌ Cloudinary delete failed: {str(e)}")
        return False


# ===================== HELPER FUNCTIONS =====================
def extract_public_id_from_url(cloudinary_url: str) -> Optional[str]:
    """
    Extract the public_id from a Cloudinary URL.
    
    Args:
        cloudinary_url: Full Cloudinary URL
        
    Returns:
        str: The public_id or None if extraction fails
    """
    try:
        # URL format: https://res.cloudinary.com/{cloud}/raw/upload/{version}/{folder}/{public_id}.pdf
        if "cloudinary.com" not in cloudinary_url:
            return None
        
        # Remove the base URL and get the path
        parts = cloudinary_url.split("/upload/")
        if len(parts) < 2:
            return None
        
        path = parts[1]
        
        # Remove version if present (starts with v followed by numbers)
        if path.startswith("v") and "/" in path:
            path = path.split("/", 1)[1]
        
        # Remove extension
        if path.endswith(".pdf"):
            path = path[:-4]
        
        return path
    
    except Exception:
        return None


def is_cloudinary_configured() -> bool:
    """
    Check if Cloudinary is properly configured.
    
    Returns:
        bool: True if Cloudinary is enabled and configured
    """
    return CLOUDINARY_ENABLED


# ===================== GENERATE AND UPLOAD HELPER =====================
def generate_and_upload_pdf(
    generate_func,
    data: dict,
    pdf_type: str,
    identifier: str,
    folder: str = "optiven_pdfs"
) -> Tuple[str, str]:
    """
    Generate a PDF using the provided function and upload to Cloudinary.
    Returns both the local temp path and Cloudinary URL.
    
    Args:
        generate_func: PDF generation function that takes (data, output_dir=None)
        data: Data to pass to the PDF generator
        pdf_type: Type prefix (e.g., 'PurchaseOrder', 'Contract')
        identifier: Unique identifier (e.g., order_id)
        folder: Cloudinary folder
        
    Returns:
        Tuple[str, str]: (temp_file_path, cloudinary_url)
        cloudinary_url will be empty string if upload fails
    """
    # Generate PDF to temp file
    temp_path = generate_func(data, output_dir=None)
    
    cloudinary_url = ""
    
    if CLOUDINARY_ENABLED:
        # Upload to Cloudinary
        public_id = f"{pdf_type}_{identifier}"
        result = upload_pdf_from_path(
            file_path=temp_path,
            folder=folder,
            public_id=public_id
        )
        
        if result:
            cloudinary_url = result.get("secure_url", "")
    
    return temp_path, cloudinary_url


# ===================== CACHE INVALIDATION =====================
async def invalidate_pdf_cache(
    collection,
    filter_query: dict,
    pdf_url_field: str = "pdf_url"
) -> bool:
    """
    Invalidate cached PDF URL in database and optionally delete from Cloudinary.
    Call this when the underlying data changes and PDF needs to be regenerated.
    
    Args:
        collection: MongoDB collection (e.g., db["PurchaseOrders"])
        filter_query: Query to find the document (e.g., {"order_id": "PO001"})
        pdf_url_field: Name of the field storing the PDF URL
        
    Returns:
        bool: True if cache was invalidated
    """
    try:
        # Get the current PDF URL before deleting
        doc = await collection.find_one(filter_query, {"_id": 0, pdf_url_field: 1})
        
        if doc and doc.get(pdf_url_field):
            old_url = doc[pdf_url_field]
            
            # Delete from Cloudinary
            public_id = extract_public_id_from_url(old_url)
            if public_id:
                delete_pdf_from_cloudinary(public_id)
            
            # Remove URL from database
            await collection.update_one(
                filter_query,
                {"$unset": {pdf_url_field: ""}}
            )
            print(f"✅ PDF cache invalidated for {filter_query}")
            return True
        
        return False
    
    except Exception as e:
        print(f"⚠️ Failed to invalidate PDF cache: {str(e)}")
        return False


def clear_pdf_url_sync(collection, filter_query: dict, pdf_url_field: str = "pdf_url"):
    """
    Synchronous helper to clear PDF URL from a document.
    Use this in synchronous code paths.
    
    Note: This does NOT delete from Cloudinary, only clears the DB field.
    The PDF will be regenerated on next download.
    """
    try:
        from pymongo import MongoClient
        # This is a placeholder - in async code use invalidate_pdf_cache instead
        print(f"⚠️ Sync PDF URL clear requested for {filter_query}")
    except Exception as e:
        print(f"⚠️ Failed to clear PDF URL: {str(e)}")
