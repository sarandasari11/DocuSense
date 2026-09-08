from typing import Optional

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse
import logging

from app.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])
oauth = OAuth()
logger = logging.getLogger("docusense.auth")

if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
    oauth.register(
        name="google",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={"scope": "openid email profile"},
    )


def oauth_configured() -> bool:
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


@router.get("/google")
async def google_login(request: Request):
    if not oauth_configured():
        return JSONResponse(
            status_code=503,
            content={"detail": "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."},
        )
    redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request):
    if not oauth_configured():
        return JSONResponse(status_code=503, content={"detail": "Google OAuth is not configured."})
    try:
        token = await oauth.google.authorize_access_token(request)
        userinfo = token.get("userinfo")
        if not userinfo:
            userinfo = await oauth.google.userinfo(token=token)
        request.session["user"] = {
            "id": userinfo.get("sub"),
            "email": userinfo.get("email"),
            "name": userinfo.get("name") or userinfo.get("email"),
            "picture": userinfo.get("picture"),
        }
        return RedirectResponse(url="/", status_code=303)
    except Exception as exc:
        logger.exception("Google OAuth callback failed: %s", type(exc).__name__)
        if type(exc).__name__ == "MismatchingStateError":
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "OAuth login expired or the callback used a different host. Start a new login from http://localhost:8000 and do not use an older Google callback tab."
                },
            )
        return JSONResponse(status_code=401, content={"detail": "Google authentication failed."})


@router.get("/me")
async def current_user(request: Request):
    user: Optional[dict] = request.session.get("user")
    return {"authenticated": bool(user), "user": user}


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"authenticated": False}
