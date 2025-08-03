
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.auth import decode_token
 
class JWTAuthMiddleware(BaseHTTPMiddleware):    
    async def dispatch(self, request: Request, call_next):
        
        
        if request.method == "OPTIONS":
            return await call_next(request)
        # Define routes to bypass the middleware
        bypass_routes = ["/","/docs", "/openapi.json", "/redoc"]
    
        # Bypass routes if the path matches an exact route or contains "system"
        if request.url.path in bypass_routes or "/register" in request.url.path or "/login" in request.url.path:
            return await call_next(request)
 
        # Check for the Authorization header
        token = request.headers.get("Authorization")

        if not token or not token.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Token missing or invalid.")
 
        try:
            # Extract and verify the token
            token = token.split(" ")[1]
            payload = decode_token(token)
            request.state.user = payload  # Attach user data to request state
            
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token.")
 
        return await call_next(request)
