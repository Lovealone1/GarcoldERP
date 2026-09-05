"""
Root pytest configuration.

`app.core.settings.Settings` validates required secrets at import time, so the
whole test suite fails to collect unless those variables exist. Tests never talk
to Supabase, Postgres or R2 -- every repository is mocked -- so we inject inert
placeholders here instead of requiring a real `.env`.

This runs before test collection, which is what makes the suite runnable on a
clean checkout and in CI without provisioning secrets.
"""

import os

_TEST_ENV_DEFAULTS = {
    "APP_ENV": "local",
    "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_JWT_SECRET": "test-jwt-secret",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key",
    "CF_ACCOUNT_ID": "test-account",
    "R2_ACCESS_KEY_ID": "test-access-key",
    "R2_SECRET_ACCESS_KEY": "test-secret-key",
    "R2_BUCKET": "test-bucket",
    "R2_PREFIX": "test",
    "CORS_ORIGINS": "http://localhost:3000",
}

for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)
