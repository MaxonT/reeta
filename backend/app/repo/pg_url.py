"""DATABASE_URL -> what asyncpg (the repository) and SQLAlchemy (Alembic) each accept.

Neon hands out `postgresql://...?sslmode=require&channel_binding=require`. asyncpg passes unknown query
params to the server as settings, so channel_binding would be rejected; sslmode is lifted into `ssl`.
"""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_DROP = {"channel_binding"}


def split_url(url: str) -> tuple[str, str | None]:
    """-> (postgresql:// dsn without sslmode or channel_binding, ssl mode or None)"""
    if not url:
        raise ValueError("DATABASE_URL is not set (needed for DB_PROVIDER=postgres)")
    parts = urlsplit(url)
    scheme = parts.scheme.split("+")[0]
    if scheme not in ("postgres", "postgresql"):
        raise ValueError(f"DATABASE_URL must be a postgresql:// URL, got {parts.scheme}://")
    query = dict(parse_qsl(parts.query))
    ssl = query.pop("sslmode", None)
    for k in _DROP:
        query.pop(k, None)
    dsn = urlunsplit(("postgresql", parts.netloc, parts.path, urlencode(query), ""))
    return dsn, ssl


def sqlalchemy_url(url: str) -> tuple[str, dict]:
    """-> (postgresql+asyncpg:// URL, connect_args) for Alembic."""
    dsn, ssl = split_url(url)
    # statement cache off so it also works through a transaction-mode pooler (Neon's -pooler host)
    connect_args = {"statement_cache_size": 0, **({"ssl": ssl} if ssl else {})}
    return dsn.replace("postgresql://", "postgresql+asyncpg://", 1), connect_args
