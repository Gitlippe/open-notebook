"""Data Tables generator — structured tabular extraction.

Extracts structured tabular data from source material and renders:
  - Markdown table(s) — immediate output
  - JSON — machine-readable schema dump

Phase 2 Stream F will add:
  - XLSX renderer via openpyxl (rich formatting, column widths)
  - HTML renderer via pandas (sortable, styled)
  - CSV renderer (one file per table)

Coordination notes for Stream F:
  - JSON schema root: {"tables": [{title, columns, rows, caption}]}
  - columns: List[str] — header names
  - rows: List[List[Any]] — row data aligned to columns
  - caption: Optional[str] — table footnote
  - Stream F should look for ArtifactFile with mime_type application/json + description "tables.json"
"""
from __future__ import annotations

import json
from typing import Any, List, Optional

from pydantic import BaseModel, Field

from open_notebook.artifacts.base import (
    ArtifactFile,
    ArtifactRequest,
    ArtifactResult,
    BaseArtifactGenerator,
)
from open_notebook.artifacts.llm import combine_prompts
from open_notebook.artifacts.prompts import (
    DATA_TABLES_MAP_PROMPT,
    DATA_TABLES_REDUCE_PROMPT,
)
from open_notebook.artifacts.registry import register_generator


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TableSchema(BaseModel):
    title: str = Field(..., description="Descriptive table title")
    columns: List[str] = Field(
        ...,
        min_length=2,
        description="Column header names (2+ columns required)",
    )
    rows: List[List[Any]] = Field(
        ...,
        description=(
            "Table rows — each row is a list aligned to columns. "
            "Preserve numeric types where possible; use strings for mixed data."
        ),
    )
    caption: Optional[str] = Field(
        None,
        description="Optional footnote or source attribution for the table",
    )


class DataTablesSchema(BaseModel):
    tables: List[TableSchema] = Field(
        ...,
        min_length=1,
        description="One or more extracted tables (at least 1 required)",
    )


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _render_markdown_table(table: TableSchema) -> str:
    """Render a single table as a GitHub-Flavored Markdown table."""
    lines = [f"### {table.title}", ""]
    header = "| " + " | ".join(str(c) for c in table.columns) + " |"
    sep = "| " + " | ".join("---" for _ in table.columns) + " |"
    lines.append(header)
    lines.append(sep)
    for row in table.rows:
        # Pad or truncate row to match column count
        cells = list(row) + [""] * max(0, len(table.columns) - len(row))
        cells = cells[: len(table.columns)]
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    if table.caption:
        lines.append("")
        lines.append(f"*{table.caption}*")
    return "\n".join(lines)


def _render_markdown_all(schema: DataTablesSchema) -> str:
    """Render all tables into a single Markdown document."""
    sections = [_render_markdown_table(t) for t in schema.tables]
    return "\n\n".join(sections).strip() + "\n"


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

@register_generator
class DataTablesGenerator(BaseArtifactGenerator):
    artifact_type = "data_tables"
    description = (
        "Structured tabular extraction rendered as Markdown + JSON. "
        "Phase 2 Stream F adds XLSX/HTML/CSV renderers."
    )
    default_model_type = "transformation"

    async def generate(self, request: ArtifactRequest) -> ArtifactResult:
        focus = request.config.get(
            "focus",
            "Extract all tabular data, comparisons, and structured lists from the sources.",
        )
        max_tables = request.config.get("max_tables", 10)

        def map_prompt(chunk: str) -> str:
            directive = DATA_TABLES_MAP_PROMPT + (
                f"\nFocus: {focus}. Maximum tables to extract: {max_tables}."
            )
            return combine_prompts(directive, chunk)

        def reduce_prompt(partials: list[DataTablesSchema]) -> str:
            combined_json = json.dumps(
                [p.model_dump() for p in partials], indent=2
            )
            return combine_prompts(
                DATA_TABLES_REDUCE_PROMPT + (
                    f"\nFocus: {focus}. Maximum tables to retain: {max_tables}."
                ),
                combined_json,
            )

        result: DataTablesSchema = await self.chunked_generate(
            request,
            schema=DataTablesSchema,
            map_prompt_builder=map_prompt,
            reduce_prompt_builder=reduce_prompt,
        )

        data = result.model_dump()

        # tables.json — primary output consumed by Phase 2 Stream F
        json_path = self.output_path(request, "json")
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Markdown tables — immediate human-readable output
        md_path = self.output_path(request, "md")
        md_path.write_text(_render_markdown_all(result), encoding="utf-8")

        # TODO (Phase 2 Stream F): add table_renderer.py that reads tables.json and:
        #   1. Writes XLSX via openpyxl (one sheet per table, column widths, header styling)
        #   2. Writes HTML via pandas .to_html() (sortable, zebra-striped)
        #   3. Writes CSV per table (one file each)
        #   These renderers should append their ArtifactFile entries to result.files.

        total_rows = sum(len(t.rows) for t in result.tables)
        table_titles = [t.title for t in result.tables]

        return ArtifactResult(
            artifact_type=self.artifact_type,
            title=request.title or f"{len(result.tables)} Extracted Table(s)",
            summary=(
                f"{len(result.tables)} table(s), {total_rows} total rows"
            ),
            structured=data,
            files=[
                ArtifactFile(
                    path=str(json_path),
                    mime_type="application/json",
                    description="tables.json — structured schema for Phase 2 Stream F renderer",
                ),
                ArtifactFile(
                    path=str(md_path),
                    mime_type="text/markdown",
                    description="Extracted tables (Markdown)",
                ),
            ],
            provenance=self.llm.provenance,
            metadata={
                "table_count": len(result.tables),
                "total_rows": total_rows,
                "table_titles": table_titles,
                "phase2_renderer": "TODO: Stream F",
            },
        )
