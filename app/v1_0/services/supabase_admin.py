from datetime import datetime
from typing import Any, Dict, Optional, cast

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.v1_0.repositories import RoleRepository
from app.v1_0.schemas import CreateUserIn, InviteUserIn, UpdateUserIn


class SupabaseAdminService:
    """Admin helper for Supabase Auth REST endpoints."""

    def __init__(self, role_repository: RoleRepository) -> None:
        self.base = settings.SUPABASE_URL.rstrip("/")
        self.headers = settings.SUPABASE_ADMIN_HEADERS
        self.role_repository = role_repository

    @staticmethod
    def _normalize_user(u: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a Supabase user payload into a consistent shape.

        Returns:
            Dict with keys: id, email, created_at, confirmed_at, user_metadata, app_metadata.

        Raises:
            RuntimeError: If required fields are missing or malformed.
        """
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

    async def _get_user_raw(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch a raw user object from Supabase Admin API.

        Args:
            user_id: Supabase Auth user ID.

        Returns:
            Raw user dict as returned by Supabase.

        Raises:
            RuntimeError: On non-2xx responses or unexpected payload shapes.
        """
        url = f"{self.base}/auth/v1/admin/users/{user_id}"
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url, headers=self.headers)
        if r.status_code >= 300:
            raise RuntimeError(f"supabase_admin_get_user_failed[{r.status_code}]: {r.text}")

        data: Any = r.json()
        if isinstance(data, dict):
            inner = data.get("user")
            if isinstance(inner, dict):
                return cast(Dict[str, Any], inner)
            return cast(Dict[str, Any], data)

        raise RuntimeError(f"supabase_admin_get_user_unexpected_type: {type(data).__name__}")

    async def list_users(
        self,
        page: int = 1,
        per_page: int = 10,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List users with pagination and optional email filter.

        Args:
            page: 1-based page index.
            per_page: Items per page.
            email: Optional email filter.

        Returns:
            Dict with keys: items (normalized users), page, per_page, has_next.

        Raises:
            RuntimeError: On API failure or unexpected payload shapes.
        """
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

        mapped = sorted(
            mapped,
            key=lambda u: (
                u.get("confirmed_at") is None,  # unconfirmed first
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
        """
        Send an invitation email via Supabase.

        Args:
            body: InviteUserIn with email and optional redirect_to.

        Returns:
            Normalized invited user dict.

        Raises:
            RuntimeError: On non-2xx response or unexpected payload.
        """
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
        """
        Create a user directly through Supabase Admin API.

        Args:
            body: CreateUserIn with email, password, and optional metadata.

        Returns:
            Normalized created user dict.

        Raises:
            RuntimeError: On API failure or unexpected payload.
        """
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

    async def delete(self, user_id: str) -> Dict[str, Any]:
        """
        Delete a user by ID.

        Args:
            user_id: Supabase Auth user ID.

        Returns:
            Dict with deletion confirmation.

        Raises:
            RuntimeError: If the ID is invalid or the API call fails.
        """
        if not isinstance(user_id, str) or not user_id:
            raise RuntimeError("supabase_admin_delete_invalid_id")

        url = f"{self.base}/auth/v1/admin/users/{user_id}"
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.delete(url, headers=self.headers)
        if r.status_code >= 300:
            raise RuntimeError(f"supabase_admin_delete_failed[{r.status_code}]: {r.text}")
        return {"id": user_id, "deleted": True}

    async def update(self, user_id: str, body: UpdateUserIn) -> Dict[str, Any]:
        """
        Update user fields and metadata.

        Args:
            user_id: Supabase Auth user ID.
            body: UpdateUserIn with optional email, name, full_name, phone.

        Returns:
            Normalized updated user dict.

        Raises:
            RuntimeError: On invalid input or API failure.
        """
        if not user_id:
            raise RuntimeError("supabase_admin_update_invalid_id")

        current = await self._get_user_raw(user_id)
        if not isinstance(current, dict):
            raise RuntimeError("supabase_admin_update_unexpected_current_payload")
        meta = cast(Dict[str, Any], current.get("user_metadata") or {})

        payload: Dict[str, Any] = {}

        if body.email is not None:
            payload["email"] = body.email
            meta["email"] = body.email

        if body.name is not None:
            meta["name"] = body.name
            meta.setdefault("full_name", body.name)

        if body.full_name is not None:
            meta["full_name"] = body.full_name
            meta.setdefault("name", body.full_name)

        if body.phone is not None:
            meta["phone"] = body.phone
            if "phone_verified" not in meta:
                meta["phone_verified"] = False

        if any(v is not None for v in [body.email, body.name, body.full_name, body.phone]):
            payload["user_metadata"] = meta

        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.put(
                f"{self.base}/auth/v1/admin/users/{user_id}",
                headers=self.headers,
                json=payload,
            )
        if r.status_code >= 300:
            raise RuntimeError(f"supabase_admin_update_failed[{r.status_code}]: {r.text}")

        data = r.json()
        user = data.get("user") or data
        if not isinstance(user, dict):
            raise RuntimeError("supabase_admin_update_unexpected_payload: " + str(data)[:600])
        return self._normalize_user(user)

    async def set_role_metadata_dynamic(
        self,
        *,
        user_id: str,
        db: AsyncSession,
        role_code: Optional[str] = None,
        role_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Resolve role_id and role_code from DB if needed and sync them into `app_metadata`.

        Behavior:
            - If both role_code and role_id are None, clears both fields in app_metadata.
            - If only one is provided, resolves the other using the roles table.
            - Validates the pair consistency.

        Args:
            user_id: Supabase Auth user ID.
            db: Active DB session to resolve roles.
            role_code: Optional role code to set.
            role_id: Optional role ID to set.

        Returns:
            Normalized updated user dict.

        Raises:
            ValueError: If role lookup fails or values are inconsistent.
            RuntimeError: On API failure or invalid input.
        """
        if not user_id:
            raise RuntimeError("supabase_admin_set_role_invalid_id")

        if role_code is not None or role_id is not None:
            roles = await self.role_repository.list_all(db)
            id_by_code = {r.code: r.id for r in roles}
            code_by_id = {r.id: r.code for r in roles}

            if role_code is not None and role_id is None:
                if role_code not in id_by_code:
                    raise ValueError(f"role_code_not_found:{role_code}")
                role_id = id_by_code[role_code]

            if role_id is not None and role_code is None:
                if role_id not in code_by_id:
                    raise ValueError(f"role_id_not_found:{role_id}")
                role_code = code_by_id[role_id]

            if role_id is not None and role_code is not None:
                if code_by_id.get(role_id) != role_code:
                    raise ValueError(f"role_mismatch:id={role_id} code={role_code}")

        payload: Dict[str, Any] = {"app_metadata": {"role": role_code, "role_id": role_id}}

        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.put(
                f"{self.base}/auth/v1/admin/users/{user_id}",
                headers=self.headers,
                json=payload,
            )
        if r.status_code >= 300:
            raise RuntimeError(f"supabase_admin_set_role_failed[{r.status_code}]: {r.text}")

        data = r.json()
        user = data.get("user") or data
        if not isinstance(user, dict):
            raise RuntimeError("supabase_admin_set_role_unexpected_payload")
        return self._normalize_user(user)
