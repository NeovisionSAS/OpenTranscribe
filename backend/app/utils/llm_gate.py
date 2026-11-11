"""Whether an LLM provider is configured — the one gate every LLM stage consults.

DB-only (no network): a user's active LLM config, else the system-level
``LLM_PROVIDER``. With neither, LLM stages are neither dispatched nor reported,
so a transcription-only deployment never queues work that can only fail or
no-op, and its task list shows only the stages that actually run.
"""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session_utils import session_scope
from app.models.media import MediaFile
from app.models.prompt import UserSetting
from app.models.user_llm_settings import UserLLMSettings

LLM_TASK_TYPES: frozenset[str] = frozenset(
    {"speaker_identification", "summarization", "topic_extraction"}
)


def llm_configured_for_user(db: Session, user_id: int) -> bool:
    """True when ``user_id`` has an existing active LLM config or the system sets one."""
    active = (
        db.query(UserSetting.setting_value)
        .filter(
            UserSetting.user_id == user_id,
            UserSetting.setting_key == "active_llm_config_id",
        )
        .first()
    )
    if active and active[0] and str(active[0]).isdigit():
        exists = db.query(UserLLMSettings.id).filter(UserLLMSettings.id == int(active[0])).first()
        if exists:
            return True
    return bool(settings.LLM_PROVIDER)


def llm_configured_for_file(file_uuid: str) -> bool:
    """True when the owner of ``file_uuid`` has an LLM configured (own short session)."""
    with session_scope() as db:
        owner = db.query(MediaFile.user_id).filter(MediaFile.uuid == file_uuid).first()
        return owner is not None and llm_configured_for_user(db, int(owner[0]))
