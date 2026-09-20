import uuid
from typing import Literal
from pydantic import BaseModel, Field

VtuberSourceType = Literal[
    "local",
    "bilibili",
]

def make_vtuber_id(
    source: str,
    source_user_id: str,
) -> str:
    """
    根据一个稳定的外部来源身份生成 Vtuber ID。

    display_name 不参与 ID，
    因为主播改名不应该改变 Creator 身份。
    """
    source = source.strip()
    source_user_id = source_user_id.strip()
    if not source:
        raise ValueError("source cannot be empty")
    if not source_user_id:
        raise ValueError("source_user_id cannot be empty")
    
    key = f"vtuber|{source}|{source_user_id}"
    
    return str(
        uuid.uuid5(
            uuid.NAMESPACE_URL,
            key,
        )
    )
    
class Vtuber(BaseModel):
    """
    系统中的主播实体。

    Vtuber 是平台无关身份。

    同一个 Vtuber 后面可以同时对应：
    - 本地 Archive
    - Bilibili
    """
    
    id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    
class VtuberSource(BaseModel):
    """
    Vtuber 在某个 Archive Source
    中的身份描述。

    当前 external_id 可以为空。
    """
    
    vtuber_id: str = Field(min_length=1)
    source: VtuberSourceType
    external_id: str | None = None
    display_name: str | None = None
    
    