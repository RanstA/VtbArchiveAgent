from pydantic import BaseModel, Field
import uuid


def make_vtuber_id() -> str:
    """
    生成系统内部稳定的 Vtuber ID。
    ID 与主播名称、平台账号等外部信息无关。
    创建后应持久化保存，不重新生成。
    """
    return str(uuid.uuid4())


class Vtuber(BaseModel):
    """
    Vtuber 表示系统中的主播实体，本身与具体平台解耦
    """

    id: str = Field(
        default_factory=make_vtuber_id,
        min_length=1,
        description="系统内部稳定唯一标识",
    )
    display_name: str = Field(min_length=1, description="前端展示使用的主播名称")

