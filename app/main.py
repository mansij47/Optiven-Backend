
from fastapi import FastAPI, Request, APIRouter
from app.middlewares.jwt_middleware import JWTAuthMiddleware
from app.routes import admin_routes, auth_routes, sales_routes, super_admin_routes, procurement_routes
from fastapi.middleware.cors import CORSMiddleware
from app.utils.auth import decode_token
 
app = FastAPI(title="Optiven Backend")
router = APIRouter()

# Include routes
router.include_router(super_admin_routes.router, tags=["Super Admin"], prefix="/api/super_admin")
router.include_router(admin_routes.router, tags=["Admin"], prefix="/api/admin")
router.include_router(procurement_routes.router, tags=["Procurement"], prefix="/api/procurement")
router.include_router(sales_routes.router, tags=["Sales"], prefix="/api/sales")
router.include_router(auth_routes.router, tags=["Auth"], prefix="/api/auth")

app.include_router(router)

origins = [
    "http://localhost:5173",  # local dev
    "https://optiven-frontend-1.onrender.com",  # production frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # NOT "*"
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.add_middleware(JWTAuthMiddleware)



@app.api_route("/", methods=["GET", "HEAD"])
def root():
    return {"message": "Welcome to Optiven Backend"}

 
# import uvicorn
 
# if __name__ == "__main__":
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
