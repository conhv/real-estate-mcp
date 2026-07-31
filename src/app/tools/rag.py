"""RAG tools (US3: policy / FAQ / legal Q&A) — PHASE-2 STUB, disabled by default.

We are intentionally SKIPPING RAG in phase 1. The DB currently has no documents/embeddings table
and pgvector is not installed. This module registers the tool but leaves it DISABLED so it does
not show up to the agent yet, while documenting the exact contract for the student to implement.

Phase-2 implementation checklist lives in docs/TOOLS_TODO.md (section "US3 / RAG"). In short:
  1. `CREATE EXTENSION vector;` and add a `documents` table (project_id, doc_type, chunk, embedding).
  2. Ingest policy/FAQ/legal docs -> chunk -> embed -> store.
  3. Implement hybrid search (BM25/pgroonga + vector) merged with RRF, then rerank.
  4. Enforce the similarity THRESHOLD: if top score < threshold, REFUSE and offer a human handoff
     (this is the PRD's hallucination<1% guardrail — US3 explicitly requires the refusal path).
"""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.tools import Tool


def register(mcp: FastMCP) -> None:
    def answer_project_policy(
        project_id: str,
        question: str,
        doc_type: str | None = None,
    ) -> dict:
        """[PHASE 2 — not yet implemented] Answer a policy/FAQ/legal question about a project (US3).

        Contract for when this is enabled:
          Args:
            project_id: the project the question is about.
            question: the user's natural-language question.
            doc_type: optional filter, e.g. "sales_policy", "faq", "legal", "amenities".
          Returns: {"answer": str, "sources": [{doc_id, chunk, score}], "confident": bool}.
          If retrieval is below the similarity threshold, `confident` MUST be false and `answer`
          should be the standard refusal offering a human advisor (do NOT fabricate).
        """
        raise ToolError(
            "answer_project_policy is not implemented yet (phase 2). "
            "See docs/TOOLS_TODO.md > 'US3 / RAG'."
        )

    # Register but keep DISABLED (hidden from the agent) until phase 2. The tool is defined here so
    # its contract is documented and easy to switch on: delete the `.disable()` line to enable.
    tool = Tool.from_function(answer_project_policy, tags={"phase2", "rag"})
    mcp.add_tool(tool)
    mcp.disable(keys=[f"tool:{tool.name}@"])
