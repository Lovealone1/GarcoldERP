import os, json, time, asyncio
from typing import Any, Dict, List, Tuple
import httpx
from jose import jwk, jwt as jose_jwt
from jose.utils import base64url_decode
from app.core.logger import logger
from app.core.settings import settings
# Lee secreto (anon key) para HS256
_HS_SECRET = ""
try:
    _HS_SECRET = settings.SUPABASE_JWT_SECRET.get_secret_value()
except Exception:
    pass

# Cache JWKS por issuer (para RS256)
_JWKS_CACHE: Dict[str, Tuple[List[Dict[str, Any]], float]] = {}
_LOCKS: Dict[str, asyncio.Lock] = {}
_TTL = 600

def _b64json(part: str) -> Dict[str, Any]:
    return json.loads(base64url_decode(part.encode()).decode("utf-8"))

async def _fetch_jwks(iss: str) -> List[Dict[str, Any]]:
    base = iss.rstrip("/")
    urls = [f"{base}/keys", f"{base}/.well-known/jwks.json"]
    async with httpx.AsyncClient(timeout=10) as cli:
        for url in urls:
            r = await cli.get(url)
            logger.info("[JWT] JWKS %s -> %s", url, r.status_code)
            if r.status_code == 200:
                data = r.json()
                keys = data.get("keys", data if isinstance(data, list) else None)
                if keys:
                    return keys
    raise RuntimeError(f"no jwks for issuer: {iss}")

async def _get_jwks(iss: str) -> List[Dict[str, Any]]:
    keys, exp = _JWKS_CACHE.get(iss, (None, 0.0))
    now = time.time()
    if keys and now < exp:
        return keys
    lock = _LOCKS.setdefault(iss, asyncio.Lock())
    async with lock:
        keys, exp = _JWKS_CACHE.get(iss, (None, 0.0))
        if keys and now < exp:
            return keys
        keys = await _fetch_jwks(iss)
        _JWKS_CACHE[iss] = (keys, time.time() + _TTL)
        return keys

async def _verify_rs256(token: str, header: Dict[str, Any], claims: Dict[str, Any]) -> Dict[str, Any]:
    kid = header.get("kid")
    if not kid:
        raise ValueError("kid faltante")
    iss = claims.get("iss")
    if not isinstance(iss, str) or not iss:
        raise ValueError("issuer faltante en token")

    keys = await _get_jwks(iss)
    key = next((k for k in keys if k.get("kid") == kid), None)
    if not key:
        _JWKS_CACHE.pop(iss, None)
        keys = await _get_jwks(iss)
        key = next((k for k in keys if k.get("kid") == kid), None)
        if not key:
            raise ValueError("kid no encontrado en JWKS")

    header_b64, payload_b64, sig_b64 = token.split(".")
    msg = f"{header_b64}.{payload_b64}".encode()
    sig = base64url_decode(sig_b64.encode())
    public_key = jwk.construct(key, header.get("alg", "RS256"))
    if not public_key.verify(msg, sig):
        raise ValueError("firma inválida")
    return claims

async def _verify_hs256(token: str) -> Dict[str, Any]:
    if not _HS_SECRET:
        raise ValueError("HS256 requiere SUPABASE_JWT_SECRET/ANON_KEY")
    # aud de Supabase suele ser 'authenticated'; no la forzamos
    return jose_jwt.decode(
        token,
        _HS_SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False},
    )

async def verify_token(token: str) -> Dict[str, Any]:
    try:
        header_b64, payload_b64, _ = token.split(".")
    except ValueError:
        raise ValueError("token malformado")

    header = _b64json(header_b64)
    alg = header.get("alg", "")
    logger.info("[JWT] verify alg=%s", alg)

    if alg.upper() == "HS256":
        claims = await _verify_hs256(token)
    elif alg.upper() == "RS256":
        claims = await _verify_rs256(token, header, _b64json(payload_b64))
    else:
        raise ValueError(f"algoritmo no soportado: {alg}")

    exp = claims.get("exp")
    if isinstance(exp, (int, float)) and time.time() > float(exp):
        raise ValueError("token expirado")
    return claims
