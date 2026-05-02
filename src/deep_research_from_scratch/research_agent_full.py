"""Thin legacy entrypoint for the full multi-agent research graph."""

from deep_research_from_scratch.core.research_graphs import build_research_graph


agent = build_research_graph(persist_report=False, output_name="research_agent_full")
