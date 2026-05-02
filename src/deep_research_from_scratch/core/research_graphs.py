"""Shared builders for the legacy research-oriented graphs."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph

from deep_research_from_scratch.multi_agent_supervisor import supervisor_agent
from deep_research_from_scratch.prompts import final_report_generation_prompt
from deep_research_from_scratch.research_agent_scope import clarify_with_user, write_research_brief
from deep_research_from_scratch.state_scope import AgentInputState, AgentState
from deep_research_from_scratch.utils import get_today_str


writer_model = init_chat_model("google_genai:models/gemini-flash-latest")


async def final_report_generation(state: AgentState) -> dict[str, object]:
    """Synthesize research notes into a final report."""
    notes = state.get("notes", [])
    findings = "\n".join(notes)
    final_report_prompt = final_report_generation_prompt.format(
        research_brief=state.get("research_brief", ""),
        findings=findings,
        date=get_today_str(),
    )
    final_report = await writer_model.ainvoke([HumanMessage(content=final_report_prompt)])
    return {
        "final_report": final_report.content,
        "messages": ["Here is the final report: " + final_report.content],
    }


async def save_report_to_file(state: AgentState) -> dict[str, object]:
    """Persist a final report into the local legacy files directory."""
    final_report = state.get("final_report", "")
    files_dir = Path(__file__).resolve().parent.parent / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    filepath = files_dir / f"report_{uuid4()}.md"
    filepath.write_text(final_report, encoding="utf-8")
    return {"messages": [f"Report saved to: {filepath}"]}


def build_research_graph(*, persist_report: bool, output_name: str) -> object:
    """Build a legacy research graph while keeping orchestration centralized."""
    builder = StateGraph(AgentState, input_schema=AgentInputState)
    builder.add_node("clarify_with_user", clarify_with_user)
    builder.add_node("write_research_brief", write_research_brief)
    builder.add_node("supervisor_subgraph", supervisor_agent)
    builder.add_node("final_report_generation", final_report_generation)

    builder.add_edge(START, "clarify_with_user")
    builder.add_edge("write_research_brief", "supervisor_subgraph")
    builder.add_edge("supervisor_subgraph", "final_report_generation")

    if persist_report:
        builder.add_node("save_report_to_file", save_report_to_file)
        builder.add_edge("final_report_generation", "save_report_to_file")
        builder.add_edge("save_report_to_file", END)
    else:
        builder.add_edge("final_report_generation", END)

    graph = builder.compile()
    graph.name = output_name
    return graph
