"""Unit tests for DataTablesGenerator — schema, registry, and config contract.

No real LLM calls. All assertions are structural / contract-level.
"""
from __future__ import annotations

import pytest

from open_notebook.artifacts.generators.data_tables import (
    DataTablesGenerator,
    DataTablesSchema,
    TableSchema,
    _render_markdown_table,
    _render_markdown_all,
)
from open_notebook.artifacts.registry import ARTIFACT_TYPES


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1. Schema has required fields
# ---------------------------------------------------------------------------

class TestDataTablesSchema:
    def test_schema_has_tables(self):
        assert "tables" in DataTablesSchema.model_fields

    def test_table_schema_has_title(self):
        assert "title" in TableSchema.model_fields

    def test_table_schema_has_columns(self):
        assert "columns" in TableSchema.model_fields

    def test_table_schema_has_rows(self):
        assert "rows" in TableSchema.model_fields

    def test_table_schema_has_caption(self):
        assert "caption" in TableSchema.model_fields

    def test_table_requires_minimum_two_columns(self):
        """columns must have at least 2 entries."""
        with pytest.raises(Exception):
            TableSchema(
                title="Bad",
                columns=["Only one"],  # < 2
                rows=[["value"]],
            )

    def test_tables_schema_requires_at_least_one_table(self):
        """DataTablesSchema.tables must have at least 1 entry."""
        with pytest.raises(Exception):
            DataTablesSchema(tables=[])

    def test_schema_validates_single_table(self):
        dt = DataTablesSchema(
            tables=[
                TableSchema(
                    title="Accuracy Comparison",
                    columns=["Model", "AIME 2024", "Cost"],
                    rows=[
                        ["DeepSeek-V3.1", "80.0%", "$0.10"],
                        ["Training-Free GRPO", "82.7%", "$0.001"],
                    ],
                    caption="Source: arXiv 2025",
                )
            ]
        )
        assert len(dt.tables) == 1
        assert dt.tables[0].title == "Accuracy Comparison"
        assert len(dt.tables[0].rows) == 2

    def test_schema_validates_multiple_tables(self):
        dt = DataTablesSchema(
            tables=[
                TableSchema(
                    title="Table 1",
                    columns=["A", "B"],
                    rows=[["a1", "b1"]],
                ),
                TableSchema(
                    title="Table 2",
                    columns=["X", "Y", "Z"],
                    rows=[[1, 2, 3], [4, 5, 6]],
                    caption="Numeric data.",
                ),
            ]
        )
        assert len(dt.tables) == 2

    def test_schema_allows_mixed_types_in_rows(self):
        """Rows can contain a mix of str, int, float."""
        t = TableSchema(
            title="Mixed",
            columns=["Name", "Score", "Pass"],
            rows=[["Alice", 95.5, True], ["Bob", 42, False]],
        )
        assert t.rows[0][1] == 95.5

    def test_schema_round_trips(self):
        dt = DataTablesSchema(
            tables=[
                TableSchema(
                    title="RT",
                    columns=["K", "V"],
                    rows=[["key", "value"]],
                )
            ]
        )
        restored = DataTablesSchema.model_validate(dt.model_dump())
        assert restored.tables[0].title == "RT"


# ---------------------------------------------------------------------------
# 1b. Markdown rendering correctness
# ---------------------------------------------------------------------------

class TestMarkdownRenderer:
    def test_render_single_table_has_headers(self):
        t = TableSchema(
            title="Test Table",
            columns=["Col A", "Col B"],
            rows=[["val1", "val2"]],
        )
        md = _render_markdown_table(t)
        assert "### Test Table" in md
        assert "| Col A | Col B |" in md
        assert "| val1 | val2 |" in md

    def test_render_table_includes_separator_row(self):
        t = TableSchema(title="T", columns=["X", "Y"], rows=[])
        md = _render_markdown_table(t)
        assert "| --- | --- |" in md

    def test_render_table_includes_caption(self):
        t = TableSchema(
            title="T", columns=["A", "B"], rows=[], caption="From source X."
        )
        md = _render_markdown_table(t)
        assert "From source X." in md

    def test_render_all_tables(self):
        dt = DataTablesSchema(
            tables=[
                TableSchema(title="T1", columns=["A", "B"], rows=[["1", "2"]]),
                TableSchema(title="T2", columns=["C", "D"], rows=[["3", "4"]]),
            ]
        )
        md = _render_markdown_all(dt)
        assert "### T1" in md
        assert "### T2" in md


# ---------------------------------------------------------------------------
# 2. Generator class is in ARTIFACT_TYPES
# ---------------------------------------------------------------------------

class TestDataTablesGeneratorRegistry:
    def test_generator_registered(self):
        assert "data_tables" in ARTIFACT_TYPES

    def test_registered_class_is_data_tables_generator(self):
        assert ARTIFACT_TYPES["data_tables"] is DataTablesGenerator


# ---------------------------------------------------------------------------
# 3. Generator's default_model_type is set
# ---------------------------------------------------------------------------

class TestDataTablesGeneratorConfig:
    def test_default_model_type_is_set(self):
        assert DataTablesGenerator.default_model_type
        assert isinstance(DataTablesGenerator.default_model_type, str)

    def test_artifact_type_is_data_tables(self):
        assert DataTablesGenerator.artifact_type == "data_tables"

    def test_description_is_non_empty(self):
        assert DataTablesGenerator.description

    def test_description_mentions_phase2(self):
        """Description should note that XLSX/HTML rendering is Phase 2."""
        desc_lower = DataTablesGenerator.description.lower()
        assert "phase 2" in desc_lower or "stream f" in desc_lower or "xlsx" in desc_lower
