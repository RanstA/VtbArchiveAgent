import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SESSION_PATH = (
    BACKEND_ROOT
    / ".local"
    / "bilibili_session.json"
)

DEFAULT_SESSION_TTL = timedelta(
    hours=48
)


@dataclass(frozen=True, slots=True)
class BilibiliSession:
    sessdata: str
    created_at: datetime
    expires_at: datetime

    @property
    def expired(self) -> bool:
        return datetime.now(
            timezone.utc
        ) >= self.expires_at


class BilibiliSessionStore:
    """
    本地 Bilibili 登录态存储。

    注意：

    1. SESSDATA 是敏感登录凭证。
    2. session 文件必须位于 Git ignore 范围。
    3. 48h 是 VtbArchiveAgent 自己的缓存 TTL，
       不代表 Bilibili 保证 token 48h 有效。
    """

    def __init__(
        self,
        path: Path | None = None,
    ) -> None:
        self.path = (
            path
            if path is not None
            else DEFAULT_SESSION_PATH
        )

    def save(
        self,
        sessdata: str,
        *,
        ttl: timedelta = DEFAULT_SESSION_TTL,
        now: datetime | None = None,
    ) -> BilibiliSession:
        sessdata = sessdata.strip()

        if not sessdata:
            raise ValueError(
                "SESSDATA cannot be empty"
            )

        now = (
            now
            if now is not None
            else datetime.now(
                timezone.utc
            )
        )

        if now.tzinfo is None:
            now = now.replace(
                tzinfo=timezone.utc
            )

        session = BilibiliSession(
            sessdata=sessdata,
            created_at=now,
            expires_at=now + ttl,
        )

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "sessdata": session.sessdata,
            "created_at": (
                session.created_at.isoformat()
            ),
            "expires_at": (
                session.expires_at.isoformat()
            ),
        }

        temp_path = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )

        temp_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        os.replace(
            temp_path,
            self.path,
        )

        # Unix 下尽量限制权限。
        # Windows 上 chmod 语义有限，因此这里只做 best effort。
        try:
            os.chmod(
                self.path,
                0o600,
            )
        except OSError:
            pass

        return session

    def load(
        self,
        *,
        now: datetime | None = None,
    ) -> BilibiliSession | None:
        if not self.path.exists():
            return None

        try:
            payload = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )

            created_at = (
                datetime.fromisoformat(
                    payload["created_at"]
                )
            )

            expires_at = (
                datetime.fromisoformat(
                    payload["expires_at"]
                )
            )

            session = BilibiliSession(
                sessdata=str(
                    payload["sessdata"]
                ),
                created_at=created_at,
                expires_at=expires_at,
            )

        except (
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ):
            self.clear()
            return None

        now = (
            now
            if now is not None
            else datetime.now(
                timezone.utc
            )
        )

        if now.tzinfo is None:
            now = now.replace(
                tzinfo=timezone.utc
            )

        if now >= session.expires_at:
            self.clear()
            return None

        return session

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def exists(self) -> bool:
        return self.load() is not None