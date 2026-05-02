"""Thin legacy entrypoint for the persisted deep research workflow."""

from deep_research_from_scratch.core.research_graphs import build_research_graph


deep_researcher = build_research_graph(persist_report=True, output_name="deep_researcher")
