import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from backend.sfa_logger import log_system_info

class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all incoming HTTP requests for auditing and security.
    Uses centralized sfa_logger for consistent logging.
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Process Request
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        # Log Details
        log_data = {
            "method": request.method,
            "url": str(request.url),
            "status_code": response.status_code,
            "process_time": f"{process_time:.4f}s",
            "client": request.client.host if request.client else "unknown"
        }
        
        # Log to system.log via sfa_logger
        log_system_info(f"HTTP Audit: {log_data}")
        
        return response
