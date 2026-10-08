"""Validate every excerpt against evidence actually supplied to the model.

This is an extractive guard, not a semantic entailment classifier. Runtime-owned
wording prevents an audience quotation being promoted to a streamer fact, and
prevents an unvalidated free-text answer bypassing finding validation.
"""

from app.investigation.deep_research_models import (
    CitationGuardError,
    ResearchDraft,
    ResearchEvidence,
    ResearchFinding,
    ResearchReport,
)


_SOURCE_LABELS = {
    "speech": "字幕转写记载",
    "audience_reaction": "观众弹幕中出现",
    "archived_interpretation": "已有话题档案的解释为",
}
_LIMITATIONS = {
    "insufficient_context": "当前上下文不足以回答问题的全部细节。",
    "ambiguous_reference": "证据中的指代存在歧义，无法确认具体对象。",
}


def validate_research_report(
    draft: ResearchDraft,
    whitelist: dict[str, ResearchEvidence],
    *,
    query: str,
    vtuber_id: str,
    search_terms: list[str],
    limitations: list[str],
) -> ResearchReport:
    findings = []
    refs: list[str] = []
    for finding in draft.findings:
        finding_refs = []
        excerpts = []
        for citation in finding.citations:
            record = whitelist.get(citation.evidence_ref)
            if record is None:
                raise CitationGuardError(f"unretrieved citation: {citation.evidence_ref}")
            if record.kind != finding.kind:
                raise CitationGuardError(f"evidence source cannot support finding kind: {citation.evidence_ref}")
            if citation.quote not in record.text:
                raise CitationGuardError(f"quotation is not in supplied evidence: {citation.evidence_ref}")
            if citation.evidence_ref in finding_refs:
                raise CitationGuardError(f"duplicate citation in finding: {citation.evidence_ref}")
            finding_refs.append(citation.evidence_ref)
            excerpts.append(f"“{citation.quote}”〔{citation.evidence_ref}〕")
            if citation.evidence_ref not in refs:
                refs.append(citation.evidence_ref)
        findings.append(ResearchFinding(
            kind=finding.kind,
            statement=_SOURCE_LABELS[finding.kind] + "：" + "；".join(excerpts),
            evidence_refs=finding_refs,
            citations=finding.citations,
        ))

    notes = list(limitations)
    notes.extend(_LIMITATIONS[item] for item in draft.limitations)
    kinds = {whitelist[ref].kind for ref in refs}
    if kinds == {"audience_reaction"}:
        notes.append("目前仅有观众反应证据，不能据此确认主播说过什么或做过什么。")
    if "archived_interpretation" in kinds:
        notes.append("Topic 是已有归档解释，不等同于直接观察或主播原话。")
    if "speech" in kinds:
        notes.append("字幕转写可能存在识别或说话人归属误差。")
    insufficient = draft.insufficient_evidence or not findings
    if insufficient:
        notes.append("证据不足以形成完整结论；未命中不代表相关事件没有发生。")
    intro = "现有证据不足以完整回答问题。" if insufficient else "检索到以下可追溯记录："
    answer = "\n".join([intro, *(finding.statement for finding in findings)])
    return ResearchReport(
        query=query, vtuber_id=vtuber_id, search_terms=search_terms,
        answer=answer, findings=findings, evidence_refs=refs,
        locations=[whitelist[ref].location for ref in refs],
        limitations=list(dict.fromkeys(notes)),
    )
