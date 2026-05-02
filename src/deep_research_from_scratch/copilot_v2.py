"""Unified research and learning copilot graph for the product layer."""

from __future__ import annotations

import re
from typing import Any
from typing_extensions import Literal, NotRequired, TypedDict

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from deep_research_from_scratch.utils import (
    deduplicate_search_results,
    get_today_str,
    summarize_webpage_content,
    tavily_search_multiple,
)


class CopilotInputState(TypedDict):
    """Public input contract for the unified product graph."""

    workspace_id: str
    project_id: str
    mode: Literal["research", "learn", "research_then_learn"]
    messages: list[dict[str, str]]
    report_id: NotRequired[str | None]
    learning_preferences: NotRequired[dict[str, Any] | None]
    report_body: NotRequired[str | None]
    knowledge_hits: NotRequired[list[dict[str, Any]] | None]


class CopilotState(TypedDict, total=False):
    """Internal working state for the unified product graph."""

    workspace_id: str
    project_id: str
    mode: Literal["research", "learn", "research_then_learn"]
    messages: list[dict[str, str]]
    report_id: str | None
    learning_preferences: dict[str, Any]
    report_body: str
    knowledge_hits: list[dict[str, Any]]
    conversation_text: str
    search_queries: list[str]
    sources: list[dict[str, Any]]
    report_title: str
    report_summary: str
    report_body_final: str
    cited_sections: list[dict[str, Any]]
    checkpoint_list: list[dict[str, Any]]
    mastery_updates: list[dict[str, Any]]
    next_actions: list[str]


class CopilotOutputState(TypedDict):
    """Structured output returned by the unified graph."""

    mode: Literal["research", "learn", "research_then_learn"]
    report_title: str
    report_summary: str
    report_body: str
    sources: list[dict[str, Any]]
    cited_sections: list[dict[str, Any]]
    checkpoint_list: list[dict[str, Any]]
    mastery_updates: list[dict[str, Any]]
    next_actions: list[str]


class SearchPlan(BaseModel):
    """Structured search plan for research runs."""

    queries: list[str] = Field(
        description="Three to five web search queries that cover the user's task comprehensively.",
        min_length=1,
        max_length=5,
    )


class ReportSectionDraft(BaseModel):
    """A report section with linked citations."""

    heading: str = Field(description="Clear section heading.")
    body: str = Field(description="Detailed section body in markdown-friendly prose.")
    citation_numbers: list[int] = Field(
        description="One-based source numbers that support this section.",
        default_factory=list,
    )


class StructuredReport(BaseModel):
    """A cited report draft."""

    title: str = Field(description="Short report title.")
    executive_summary: str = Field(description="A concise executive summary.")
    sections: list[ReportSectionDraft] = Field(
        description="Detailed report sections with numbered citations."
    )
    next_actions: list[str] = Field(
        description="Recommended follow-up steps after reading the report.",
        default_factory=list,
    )


class CheckpointDraft(BaseModel):
    """Learning checkpoint derived from a report."""

    title: str = Field(description="Checkpoint title.")
    objective: str = Field(description="Learning objective for this checkpoint.")
    study_material: str = Field(description="Study material that explains the concept.")
    quiz_questions: list[str] = Field(
        description="Exactly three quiz questions for the learner.",
        min_length=3,
        max_length=3,
    )
    citation_numbers: list[int] = Field(
        description="One-based source numbers that support this checkpoint.",
        default_factory=list,
    )


class CheckpointBundle(BaseModel):
    """Checkpoint plan for a learning session."""

    checkpoints: list[CheckpointDraft] = Field(
        description="Ordered checkpoints for the learning session.",
        min_length=1,
    )
    next_actions: list[str] = Field(
        description="Recommended actions for the learner after the checkpoints are generated.",
        default_factory=list,
    )


copilot_model = init_chat_model("google_genai:models/gemini-flash-latest", max_retries=0)
planning_model = copilot_model.with_structured_output(SearchPlan)
report_model = copilot_model.with_structured_output(StructuredReport)
checkpoint_model = copilot_model.with_structured_output(CheckpointBundle)

STOPWORDS = {
    "about",
    "agent",
    "autonomous",
    "build",
    "clear",
    "from",
    "into",
    "learning",
    "practical",
    "produce",
    "project",
    "report",
    "research",
    "students",
    "style",
    "their",
    "them",
    "this",
    "using",
    "with",
}


def _messages_to_text(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = message.get("role", "user").strip() or "user"
        content = message.get("content", "").strip()
        if content:
            lines.append(f"{role.upper()}: {content}")
    return "\n".join(lines).strip()


def _normalize_source_index(index: int, max_sources: int) -> int | None:
    if max_sources <= 0:
        return None
    if index < 1 or index > max_sources:
        return None
    return index


def _keyword_candidates(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", text.lower())
    seen: list[str] = []
    for word in words:
        if word in STOPWORDS or word in seen:
            continue
        seen.append(word)
    return seen


def _fallback_queries(state: CopilotState) -> list[str]:
    conversation = state.get("conversation_text", "")
    keywords = _keyword_candidates(conversation)
    if not keywords:
        keywords = ["checkpoint verification", "feynman pedagogy", "adaptive learning"]

    queries = [
        " ".join(keywords[:4]),
        "engineering education " + " ".join(keywords[:3]),
        "best practices " + " ".join(keywords[:3]),
    ]
    normalized: list[str] = []
    for query in queries:
        clean = " ".join(query.split()).strip()
        if clean and clean not in normalized:
            normalized.append(clean)
    return normalized[:3]


def _render_report_markdown(summary: str, sections: list[dict[str, Any]]) -> str:
    chunks = ["## Executive Summary", summary.strip()]
    for section in sections:
        chunks.append(f"## {section['heading']}")
        chunks.append(section["body"].strip())
        if section["citations"]:
            citations = ", ".join(
                f"[{citation['number']}]({citation['url']})"
                for citation in section["citations"]
            )
            chunks.append(f"Sources: {citations}")
    return "\n\n".join(chunk for chunk in chunks if chunk)


def _source_digest(sources: list[dict[str, Any]]) -> str:
    if not sources:
        return "No sources gathered."

    lines = []
    for index, source in enumerate(sources, start=1):
        lines.append(
            f"[{index}] {source['title']}\n"
            f"URL: {source['url']}\n"
            f"Confidence: {source['confidence']}\n"
            f"Excerpt: {source['excerpt']}\n"
            f"Summary: {source['summary']}"
        )
    return "\n\n".join(lines)


def _report_sections_with_citations(
    raw_sections: list[ReportSectionDraft],
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for section in raw_sections:
        citations = []
        for number in section.citation_numbers:
            normalized = _normalize_source_index(number, len(sources))
            if normalized is None:
                continue
            source = sources[normalized - 1]
            citations.append(
                {
                    "number": normalized,
                    "source_id": source["source_id"],
                    "title": source["title"],
                    "url": source["url"],
                }
            )
        sections.append(
            {
                "heading": section.heading,
                "body": section.body,
                "citation_numbers": [citation["number"] for citation in citations],
                "citations": citations,
            }
        )
    return sections


def _checkpoint_payload(
    raw_checkpoints: list[CheckpointDraft],
    sources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for order_index, checkpoint in enumerate(raw_checkpoints):
        citation_numbers = []
        citation_source_ids = []
        for number in checkpoint.citation_numbers:
            normalized = _normalize_source_index(number, len(sources))
            if normalized is None:
                continue
            citation_numbers.append(normalized)
            citation_source_ids.append(sources[normalized - 1]["source_id"])
        payload.append(
            {
                "title": checkpoint.title,
                "objective": checkpoint.objective,
                "study_material": checkpoint.study_material,
                "quiz_questions": checkpoint.quiz_questions,
                "citation_numbers": citation_numbers,
                "citation_source_ids": citation_source_ids,
                "order_index": order_index,
            }
        )
    return payload


def _fallback_report(state: CopilotState, sources: list[dict[str, Any]]) -> dict[str, Any]:
    conversation = state.get("conversation_text", "").strip()
    title_seed = conversation.split(".")[0].strip() or "Autonomous Learning Agent Research Brief"
    title = title_seed[:96]
    summary_parts = []
    if sources:
        summary_parts.append(f"This fallback report was assembled from {len(sources)} available sources.")
    if state.get("knowledge_hits"):
        summary_parts.append("It also incorporates private workspace knowledge already stored in the project.")
    if conversation:
        summary_parts.append(f"Focus: {conversation[:220]}")
    summary = " ".join(summary_parts).strip() or "Fallback report generated from available context."

    sections: list[dict[str, Any]] = []
    for number, source in enumerate(sources[:3], start=1):
        sections.append(
            {
                "heading": source["title"][:96] or f"Source {number}",
                "body": (source.get("summary") or source.get("excerpt") or "No summary available.").strip(),
                "citation_numbers": [number],
                "citations": [
                    {
                        "number": number,
                        "source_id": source["source_id"],
                        "title": source["title"],
                        "url": source["url"],
                    }
                ],
            }
        )
    if not sections:
        sections.append(
            {
                "heading": "Request Overview",
                "body": conversation or "No detailed research request was provided.",
                "citation_numbers": [],
                "citations": [],
            }
        )

    return {
        "report_title": title,
        "report_summary": summary,
        "cited_sections": sections,
        "report_body_final": _render_report_markdown(summary, sections),
        "next_actions": [
            "Review the synthesized sources and refine the question when model quota is restored.",
            "Add more private knowledge documents to improve project-specific grounding.",
        ],
    }


def _fallback_checkpoints(state: CopilotState) -> dict[str, Any]:
    report_body = state.get("report_body") or state.get("report_body_final") or state.get("conversation_text", "")
    sections = [segment.strip() for segment in report_body.split("##") if segment.strip()]
    source_ids = [source["source_id"] for source in state.get("sources", [])[:2]]
    checkpoint_list: list[dict[str, Any]] = []
    for index, section in enumerate(sections[:3]):
        lines = [line.strip() for line in section.splitlines() if line.strip()]
        heading = lines[0][:80] if lines else f"Checkpoint {index + 1}"
        material = " ".join(lines[1:])[:900] if len(lines) > 1 else report_body[:900]
        checkpoint_list.append(
            {
                "title": heading,
                "objective": f"Explain the main idea behind {heading.lower()}.",
                "study_material": material or report_body[:900] or "Review the generated report and summarize it in your own words.",
                "quiz_questions": [
                    f"What is the core idea in {heading}?",
                    f"Why does {heading} matter for this project or learning workflow?",
                    f"How would you apply {heading} in practice?",
                ],
                "citation_numbers": [1] if state.get("sources") else [],
                "citation_source_ids": source_ids,
                "order_index": index,
            }
        )
    if not checkpoint_list:
        checkpoint_list.append(
            {
                "title": "Foundational Understanding",
                "objective": "Summarize the project topic in simple language.",
                "study_material": report_body[:900] or "Review the project request and explain it simply.",
                "quiz_questions": [
                    "What problem is the project trying to solve?",
                    "Which concepts matter most here?",
                    "How would you explain the topic to another student?",
                ],
                "citation_numbers": [],
                "citation_source_ids": [],
                "order_index": 0,
            }
        )
    return {
        "checkpoint_list": checkpoint_list,
        "next_actions": [
            "Answer the checkpoints and use the feedback loop to reinforce weak areas.",
            "Rerun with live model capacity later for richer adaptive checkpoints.",
        ],
    }


def normalize_input(state: CopilotState) -> dict[str, Any]:
    """Normalize incoming messages and defaults."""
    learning_preferences = state.get("learning_preferences") or {}
    conversation_text = _messages_to_text(state.get("messages", []))
    report_body = state.get("report_body") or ""
    knowledge_hits = state.get("knowledge_hits") or []

    if state["mode"] == "learn" and not report_body:
        report_body = conversation_text

    return {
        "conversation_text": conversation_text,
        "learning_preferences": learning_preferences,
        "report_body": report_body,
        "knowledge_hits": knowledge_hits,
        "mastery_updates": [],
        "next_actions": [],
    }


def route_after_normalize(
    state: CopilotState,
) -> Literal["plan_research", "generate_checkpoints"]:
    """Route by requested copilot mode."""
    if state["mode"] == "learn":
        return "generate_checkpoints"
    return "plan_research"


def plan_research(state: CopilotState) -> dict[str, Any]:
    """Generate focused search queries for research-oriented runs."""
    prompt = f"""
You are preparing a research plan for a team workspace copilot.
Today's date is {get_today_str()}.

Conversation:
{state.get('conversation_text', '')}

Private knowledge hints:
{_source_digest(state.get('knowledge_hits', []))}

Generate search queries that will help produce a source-grounded report.
Balance breadth and specificity. Prefer primary and authoritative sources.
"""
    try:
        plan = planning_model.invoke([HumanMessage(content=prompt)])
        return {"search_queries": plan.queries[:5]}
    except Exception:
        return {"search_queries": _fallback_queries(state)}


def gather_sources(state: CopilotState) -> dict[str, Any]:
    """Run Tavily searches and normalize results into source objects."""
    queries = state.get("search_queries", [])
    collected_sources = list(state.get("knowledge_hits", []))
    if not queries:
        return {"sources": collected_sources}

    search_results = tavily_search_multiple(
        queries,
        max_results=3,
        topic="general",
        include_raw_content=False,
    )
    unique_results = deduplicate_search_results(search_results)

    sources: list[dict[str, Any]] = collected_sources[:]
    for index, result in enumerate(unique_results.values(), start=1):
        raw_content = result.get("raw_content")
        summary = (
            summarize_webpage_content(raw_content)
            if raw_content
            else result.get("content", "")
        )
        excerpt = (result.get("content") or summary or "")[:320]
        confidence = float(result.get("score") or 0.0)
        sources.append(
            {
                "source_id": f"src-web-{index}",
                "url": result.get("url", ""),
                "title": result.get("title", "Untitled source"),
                "excerpt": excerpt,
                "summary": summary,
                "published_at": result.get("published_date")
                or result.get("publishedAt"),
                "confidence": round(confidence, 4),
                "retrieved_at": get_today_str(),
                "metadata_json": {"kind": "web"},
            }
        )

    return {"sources": sources[:8]}


def write_report(state: CopilotState) -> dict[str, Any]:
    """Draft a cited report from gathered sources."""
    sources = state.get("sources", [])
    prompt = f"""
You are writing a report for a collaborative AI copilot workspace.
Today's date is {get_today_str()}.

User request:
{state.get('conversation_text', '')}

Available sources:
{_source_digest(sources)}

Requirements:
- Produce a polished, source-grounded report.
- Every section should use citation numbers from the provided source list.
- Do not invent sources or citation numbers.
- Keep the writing clear for teams, not just individual students.
"""
    try:
        report = report_model.invoke([HumanMessage(content=prompt)])
        sections = _report_sections_with_citations(report.sections, sources)
        report_body = _render_report_markdown(report.executive_summary, sections)
        return {
            "report_title": report.title,
            "report_summary": report.executive_summary,
            "cited_sections": sections,
            "report_body_final": report_body,
            "next_actions": report.next_actions,
        }
    except Exception:
        return _fallback_report(state, sources)


def route_after_report(
    state: CopilotState,
) -> Literal["generate_checkpoints", "finalize_output"]:
    """Continue into learning when requested."""
    if state["mode"] == "research_then_learn":
        return "generate_checkpoints"
    return "finalize_output"


def generate_checkpoints(state: CopilotState) -> dict[str, Any]:
    """Create study checkpoints from a report body."""
    report_body = state.get("report_body") or state.get("report_body_final") or ""
    if not report_body:
        report_body = state.get("conversation_text", "")

    preferences = state.get("learning_preferences") or {}
    prompt = f"""
You are generating adaptive learning checkpoints for a team-oriented AI copilot.
Today's date is {get_today_str()}.

Learning preferences:
{preferences}

Source digest:
{_source_digest(state.get('sources', []))}

Report to teach from:
{report_body}

Requirements:
- Create 3 to 5 meaningful checkpoints.
- Each checkpoint must include exactly 3 quiz questions.
- Use citation numbers from the provided source digest when possible.
- The study material should be practical, clear, and suitable for collaborative learning.
"""
    try:
        bundle = checkpoint_model.invoke([HumanMessage(content=prompt)])
        checkpoint_list = _checkpoint_payload(bundle.checkpoints, state.get("sources", []))
        next_actions = list(state.get("next_actions", []))
        next_actions.extend(bundle.next_actions)
        return {"checkpoint_list": checkpoint_list, "next_actions": next_actions}
    except Exception:
        fallback = _fallback_checkpoints(state)
        next_actions = list(state.get("next_actions", []))
        next_actions.extend(fallback["next_actions"])
        return {"checkpoint_list": fallback["checkpoint_list"], "next_actions": next_actions}


def finalize_output(state: CopilotState) -> CopilotOutputState:
    """Shape the final graph response."""
    return {
        "mode": state["mode"],
        "report_title": state.get("report_title", ""),
        "report_summary": state.get("report_summary", ""),
        "report_body": state.get("report_body_final", state.get("report_body", "")),
        "sources": state.get("sources", []),
        "cited_sections": state.get("cited_sections", []),
        "checkpoint_list": state.get("checkpoint_list", []),
        "mastery_updates": state.get("mastery_updates", []),
        "next_actions": state.get("next_actions", []),
    }


builder = StateGraph(CopilotState, input_schema=CopilotInputState, output_schema=CopilotOutputState)
builder.add_node("normalize_input", normalize_input)
builder.add_node("plan_research", plan_research)
builder.add_node("gather_sources", gather_sources)
builder.add_node("write_report", write_report)
builder.add_node("generate_checkpoints", generate_checkpoints)
builder.add_node("finalize_output", finalize_output)

builder.add_edge(START, "normalize_input")
builder.add_conditional_edges(
    "normalize_input",
    route_after_normalize,
    {
        "plan_research": "plan_research",
        "generate_checkpoints": "generate_checkpoints",
    },
)
builder.add_edge("plan_research", "gather_sources")
builder.add_edge("gather_sources", "write_report")
builder.add_conditional_edges(
    "write_report",
    route_after_report,
    {
        "generate_checkpoints": "generate_checkpoints",
        "finalize_output": "finalize_output",
    },
)
builder.add_edge("generate_checkpoints", "finalize_output")
builder.add_edge("finalize_output", END)

copilot_v2 = builder.compile()
