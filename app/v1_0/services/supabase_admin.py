import httpx
from datetime import datetime
from typing import Any, Dict, Optional, cast
from app.core.settings import settings
from app.v1_0.schemas import InviteUserIn, CreateUserIn

class SupabaseAdminService:
    def __init__(self) -> None:
        self.base = settings.SUPABASE_URL.rstrip("/")
        self.headers = settings.SUPABASE_ADMIN_HEADERS

    @staticmethod
    def _normalize_user(u: Dict[str, Any]) -> Dict[str, Any]:
        uid = u.get("id")
        email = u.get("email")
        if not isinstance(uid, str) or not isinstance(email, str):
            raise RuntimeError("supabase_admin_user_shape_invalid")
        created = u.get("created_at") or u.get("invited_at")
        confirmed = u.get("confirmed_at") or u.get("email_confirmed_at")
        return {
            "id": uid,
            "email": email,
            "created_at": created,
            "confirmed_at": confirmed,
            "user_metadata": cast(Dict[str, Any], u.get("user_metadata") or {}),
            "app_metadata": cast(Dict[str, Any], u.get("app_metadata") or {}),
        }

    async def list_users(
    self, page: int = 1, per_page: int = 10, email: Optional[str] = None
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "per_page": per_page}
        if email:
            params["email"] = email

        def _ts(s: Optional[str]) -> float:
            if not s:
                return 0.0
            try:
                return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
            except Exception:
                return 0.0

        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{self.base}/auth/v1/admin/users",
                headers=self.headers,
                params=params,
            )
            if r.status_code >= 300:
                raise RuntimeError(f"supabase_admin_list_users_failed[{r.status_code}]: {r.text}")

            payload = r.json()

            if isinstance(payload, list):
                src = payload
            elif isinstance(payload, dict):
                if isinstance(payload.get("items"), list):
                    src = payload["items"]
                elif isinstance(payload.get("users"), list):
                    src = payload["users"]
                elif isinstance(payload.get("items"), dict) and isinstance(payload["items"].get("users"), list):
                    src = payload["items"]["users"]
                else:
                    raise RuntimeError("supabase_admin_unexpected_payload: " + str(payload)[:600])
            else:
                raise RuntimeError(f"supabase_admin_unexpected_type: {type(payload).__name__}")

            if any(not isinstance(x, dict) for x in src):
                raise RuntimeError("supabase_admin_unexpected_item_type: " + str(src[:3])[:600])

            mapped = [self._normalize_user(cast(Dict[str, Any], u)) for u in src]

            # Activos primero (confirmed_at != None). Dentro de cada grupo, más recientes por created_at.
            mapped = sorted(
                mapped,
                key=lambda u: (
                    u.get("confirmed_at") is None,
                    -_ts(cast(Optional[str], u.get("created_at"))),
                ),
            )

            has_next = len(src) == per_page
            if isinstance(payload, dict):
                if isinstance(payload.get("has_next"), bool):
                    has_next = payload["has_next"]
                elif payload.get("next_page"):
                    has_next = True
                elif isinstance(payload.get("links"), dict) and payload["links"].get("next"):
                    has_next = True

            return {"items": mapped, "page": page, "per_page": per_page, "has_next": has_next}


    async def invite(self, body: InviteUserIn) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"email": body.email}
        if body.redirect_to:
            payload["redirect_to"] = body.redirect_to
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(f"{self.base}/auth/v1/invite", headers=self.headers, json=payload)
            if r.status_code >= 300:
                raise RuntimeError(f"supabase_admin_invite_failed[{r.status_code}]: {r.text}")
            data = r.json()
            user = data.get("user") or data
            if not isinstance(user, dict):
                raise RuntimeError("supabase_admin_invite_unexpected_payload: " + str(data)[:600])
            return self._normalize_user(user)

    async def create(self, body: CreateUserIn) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "email": body.email,
            "password": body.password,
            "email_confirm": True,
            "user_metadata": body.user_metadata or {},
            "app_metadata": body.app_metadata or {},
        }
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(f"{self.base}/auth/v1/admin/users", headers=self.headers, json=payload)
            if r.status_code >= 300:
                raise RuntimeError(f"supabase_admin_create_failed[{r.status_code}]: {r.text}")
            data = r.json()
            user = data.get("user") or data
            if not isinstance(user, dict):
                raise RuntimeError("supabase_admin_create_unexpected_payload: " + str(data)[:600])
            return self._normalize_user(user)

    async def delete(self, user_id: str) -> dict:
        if not isinstance(user_id, str) or not user_id:
            raise RuntimeError("supabase_admin_delete_invalid_id")

        url = f"{self.base}/auth/v1/admin/users/{user_id}"
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.delete(url, headers=self.headers)
            if r.status_code >= 300:
                raise RuntimeError(f"supabase_admin_delete_failed[{r.status_code}]: {r.text}")
        return {"id": user_id, "deleted": True}