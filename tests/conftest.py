import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-token")
os.environ.setdefault("TIMEZONE", "Asia/Tehran")
os.environ.setdefault("ADMIN_SERVICE_TOKEN", "test-admin-token")
