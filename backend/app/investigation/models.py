from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

def to_camel(value: str) -> str:
    parts = value.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])

class ApiModel(BaseModel):
    """
    API 层统一数据模型基类。
    所有对外返回的 Pydantic Model 继承该类，统一处理：
    1. Python 风格字段名（snake_case）
       转换为 API JSON 风格字段名（camelCase）。
    2. 允许通过字段名或别名进行数据填充。
    主要用于：
    - FastAPI Response
    - 前后端接口通信
    - 保持 Python 代码风格与 API 格式解耦

    """
    
    model_config = ConfigDict(
        alias_generator=to_camel, 
        populate_by_name=True
    )

class EvidenceRef(ApiModel):
    """
    Agent 输出中的证据引用。
    用于标记某个 Finding 使用了哪些底层证据，
    但不直接保存证据内容。
    当前支持两类证据：
    1. highlight:
       来自 Highlight Pipeline 生成的高光候选，
       表示该时间段具有较高互动信号。
    2. danmaku:
       来自具体弹幕记录，
       用于提供观众反应层面的原始证据。
    """
    
    kind: Literal["highlight", "danmaku"]
    id: str

class EventScoutTraceStep(ApiModel):
    """
    Event Scout Agent 单步执行轨迹。
    记录 Agent Runtime 在一次查询过程中的行为。
    每一个 TraceStep 对应 Agent 执行过程中的一个节点。
    action 类型：
    1. model: 表示一次模型调用。
    2. tool: 表示一次工具调用。
    3. final: 表示 Agent 完成调查并生成最终结果。
    
    示例：

        {
            "step": 2,
            "action": "tool",
            "toolName": "get_danmaku_window",
            "arguments": {
                "highlightId": "xxx"
            }
        }
    """
    step: int
    action: Literal["model", "tool", "final"]
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None

class EventScoutFinding(ApiModel):
    """
    Event Scout 输出的单个事件发现结果。
    一个 Finding 表示 Agent 基于证据发现的一个值得调查的直播片段。
    数据来源分为三类：
    1. 直播元数据：
       - stream_id
       - stream_title
       - live_time
       - part_id
       用于定位原始直播。
    2. Highlight 定位信息：
       - start_ms
       - end_ms
       - peak_ms
       - score
       来自离线 Highlight Pipeline，
       描述该时间段的互动强度和位置。
    3. Agent 分析结果：
       - observation：基于实际检索到的弹幕证据，对可观察现象进行总结。
       - interpretation：基于 observation 的有限解释。
    4. 量化指标：
       - confidence：对当前 interpretation 的可信程度。
       - evidence_level：当前 Finding 使用的证据等级。
       - evidence：支撑当前 Finding 的具体证据引用。
    """
    
    highlight_id: str
    
    stream_id: str
    stream_title: str
    live_time: str
    part_id: str
    
    start_ms: int
    end_ms: int
    peak_ms: int
    score: float

    observation: str
    interpretation: str | None = None
    
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_level: Literal["audience_reaction"] = "audience_reaction"
    evidence: list[EvidenceRef]

class EventScoutResult(ApiModel):
    """
    Event Scout 一次完整调查任务的最终结果。
    是 Event Scout 对外返回的主结果结构。
    - 用户查询
    - 当前 VTuber workspace
    - Scout 类型
    - 当前证据边界
    - 最终回答
    - 结构化 Finding
    - Agent 执行轨迹
    """
    
    query: str
    vtuber_id: str
    scout: Literal["event_scout"] = "event_scout"
    boundary: Literal["audience_reaction_only"] = "audience_reaction_only"
    answer: str
    findings: list[EventScoutFinding]
    trace: list[EventScoutTraceStep]

class EventScoutDraftFinding(BaseModel):
    """
    LLM 生成的单个 Finding 草稿。
    这是模型完成 Tool Calling 后返回的原始结构化结果，
    尚未经过 Runtime 的证据校验和回填。
    LLM 负责：
    - 指定准备引用的 highlight_id
    - 总结 observation
    - 给出有限 interpretation
    - 给出 confidence
    - 指定希望引用的 danmaku_ids
    Draft 不能直接作为最终 API Finding 使用。
    """
    
    highlight_id: str
    observation: str
    interpretation: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    danmaku_ids: list[int] = Field(default_factory=list)

class EventScoutDraft(BaseModel):
    """
    Event Scout 的 LLM 原始结构化输出。
    该模型用于解析模型最终返回的 JSON，
    属于 Agent Runtime 的中间数据结构，不是最终 API 输出。

    """
    
    answer: str
    findings: list[EventScoutDraftFinding]