import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List
from api.auth_utils import get_current_active_user
from api.models import User

router = APIRouter(prefix="/api/upload", tags=["Upload"])

UPLOAD_DIR = "data/db"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".db", ".csv"}

@router.post("/dataset")
async def upload_dataset(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """
    Upload a database or CSV file for analysis.
    Files are saved in data/datasets/
    """
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Make filename safe and unique per user if needed
    # For now, just save with original name in the shared datasets folder
    # In a multi-tenant production app, we'd use user-specific subfolders
    safe_filename = "".join([c for c in file.filename if c.isalnum() or c in "._-"])
    file_path = os.path.join(UPLOAD_DIR, safe_filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {
            "success": True,
            "filename": safe_filename,
            "path": os.path.abspath(file_path),
            "url_path": f"/data/db/{safe_filename}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/list")
async def list_datasets(current_user: User = Depends(get_current_active_user)):
    """List all available datasets in the upload directory."""
    files = []
    if os.path.exists(UPLOAD_DIR):
        for f in os.listdir(UPLOAD_DIR):
            if any(f.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS):
                files.append({
                    "name": f,
                    "path": os.path.abspath(os.path.join(UPLOAD_DIR, f)),
                    "size": os.path.getsize(os.path.join(UPLOAD_DIR, f))
                })
    return {"files": files}
