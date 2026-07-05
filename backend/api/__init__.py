from fastapi import APIRouter
from api.routes import auth, video, edit, vault, style, payments, jobs, edit_state

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(video.router)
api_router.include_router(edit.router)
api_router.include_router(vault.router)
api_router.include_router(style.router)
api_router.include_router(payments.router)
api_router.include_router(jobs.router)
api_router.include_router(edit_state.router)