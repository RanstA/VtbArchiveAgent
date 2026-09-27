from collections import Counter
from typing import Any
from app.investigation.tools import EventScoutTools


class EvalEventScoutTools:
    """
    Event Scout 语义评测使用的固定 Fixture Tools。
    每个 Eval Case 提供固定的：
    - Highlight
    - Danmaku
    """

    def __init__(
        self,
        *,
        case: dict[str, Any],
        vtuber_id: str = "aza",
    ) -> None:
        self.case = case
        self.vtuber_id = vtuber_id

        self.calls: list[tuple[str, dict[str, Any]]] = []

    @staticmethod
    def tool_schemas() -> list[dict[str, Any]]:
        """
        复用生产环境的 Tool Schema
        """
        return EventScoutTools.tool_schemas()

    def execute(self, name: str, arguments: dict[str, Any]) -> dict:
        """
        EventScout Runtime 的统一 Tool 入口。
        """
        self.calls.append(name, dict(arguments))
        if name == "search_highlights":
            return self.research_highlights(
                top_k=arguments.get("top_k", 8),
                min_score=arguments.get("min_score", 0.85),
            )
        if name == "get_danmaku_window":
            return self.get_danmaku_window(
                highlight_id=str(arguments.get("highlight_id", "")),
                limit=arguments.get("limit", 80),
            )
        raise ValueError(f"unknown Event Scout eval tool: {name}")

    def search_highlights(self, *, top_k: int = 8, min_score: float = 0.85) -> dict:
        """
        返回当前 Eval Case 中固定的 Highlight。
        第一版 Eval 的目标是测试 Agent 对固定证据的理解，
        因此这里不使用 min_score 对 Fixture 做动态过滤。
        min_score / top_k 参数仍然保留，
        以保持与生产 Tool 的调用接口一致
        """
        top_k = min(max(int(top_k), 1), 12)
        _ = min(max(float(min_score), 0.0), 1.0)
        highlight = self.case.get("highlight")
        if highlight is None: candidates = []
        else: 
            candidate = dict(highlight)
            candidate["evidence_id"] = "highlight:" + f"{candidate['highlight_id']}"

            candidates = [candidate][:top_k]
            
        return{
            "vtuber_id": self.vtuber_id,
            "candidate_count": len(candidates),
            "candidates": candidates
        }
        
    def get_danmaku_window(self,*,highlight_id: str, limit: int = 80) -> dict:
        """
        返回当前 Eval Case 中固定的 Danmaku Evidence。
        """
        highlight_id = highlight_id.strip()
        if not highlight_id:
            raise ValueError(
                "highlight_id cannot be empty"
            )
        highlight = self.case.get("highlight")
        if highlight is None:
            raise ValueError(
                "Eval case has no Highlight"
            )
        expected_highlight_id = str(highlight["highlight_id"])
        
        if(highlight_id != expected_highlight_id):
            raise ValueError("Highlight not found in current eval case")
    
        limit = min(max(int(limit),1),120)
        raw_danmaku = list(self.case.get("danmaku",[]))
        danmaku = raw_danmaku[:limit]
        text_counter = Counter(
            str(item.get("text",""))
            for item in danmaku
            if str(item.get("text","")).strip()
        )
        top_texts = [
            {
                "text": text,
                "count": count,
            }
            for text, count
            in text_counter.most_common(10)
        ]
        
        evidence_items = []
        
        for item in danmaku: 
            evidence_item = dict(item)
            evidence_item["evidence_id"] = "danmaku: "+ f"{item['id']}"
            evidence_items.append(evidence_item)
            
        return{
            "highlight_id": highlight["highlight_id"],
            "stream_id": highlight["stream_id"],
            "stream_title": highlight["stream_title"],
            "live_time": highlight["live_time"],
            "part_id": highlight["part_id"],
            "start_ms": highlight["start_ms"],
            "end_ms": highlight["end_ms"],
            "peak_ms": highlight["peak_ms"],
            "score": highlight["score"],
            "returned_count": len(evidence_items),
            "top_texts": top_texts,
            "danmaku": evidence_items,
            "evidence_boundary": (
                "These are audience reactions. "
                "They do not prove streamer "
                "speech or actions."
            ),
        }