"""Tests for Jinja2 template engine."""

from pathlib import Path

import pytest

from servers.event_mcp.template_engine import TemplateEngine


class TestTemplateEngine:
    """Tests for TemplateEngine class."""

    @pytest.fixture
    def template_engine(self) -> TemplateEngine:
        """Create template engine with project templates."""
        return TemplateEngine()

    @pytest.fixture
    def temp_template_engine(self, tmp_path: Path) -> TemplateEngine:
        """Create template engine with temporary directory."""
        # Create a simple test template
        template_file = tmp_path / "test.md"
        template_file.write_text("Hello, {{ name }}!")
        return TemplateEngine(template_dir=tmp_path)

    def test_render_simple_template(self, temp_template_engine: TemplateEngine):
        """Test rendering a simple template."""
        result = temp_template_engine.render("test.md", {"name": "World"})
        assert result == "Hello, World!"

    def test_render_string(self, template_engine: TemplateEngine):
        """Test rendering from a template string."""
        result = template_engine.render_string(
            "{{ greeting }}, {{ name }}!",
            {"greeting": "Hello", "name": "RVA"},
        )
        assert result == "Hello, RVA!"

    def test_template_exists(self, template_engine: TemplateEngine):
        """Test checking if template exists."""
        assert template_engine.template_exists("default.md")
        assert not template_engine.template_exists("nonexistent.md")

    def test_list_templates(self, template_engine: TemplateEngine):
        """Test listing available templates."""
        templates = template_engine.list_templates()
        assert "default.md" in templates

    def test_render_newsletter_template(
        self, template_engine: TemplateEngine, newsletter_context: dict
    ):
        """Test rendering the actual newsletter template."""
        result = template_engine.render("default.md", newsletter_context)

        # Check that key elements are present
        assert newsletter_context["newsletter_name"] in result
        assert newsletter_context["date_range"] in result
        assert "Don't Miss This Week" in result
        assert "Live Music & Concerts" in result

    def test_render_with_events(
        self, template_engine: TemplateEngine, newsletter_context: dict
    ):
        """Test rendering with event data."""
        result = template_engine.render("default.md", newsletter_context)

        # Check that highlight event is rendered
        assert "Reggae Night" in result
        assert "The Camel" in result

    def test_conditional_rendering(self, template_engine: TemplateEngine):
        """Test conditional template rendering."""
        template = "{% if show %}Visible{% endif %}"

        result_shown = template_engine.render_string(template, {"show": True})
        result_hidden = template_engine.render_string(template, {"show": False})

        assert result_shown == "Visible"
        assert result_hidden == ""

    def test_loop_rendering(self, template_engine: TemplateEngine):
        """Test loop rendering in templates."""
        template = "{% for item in items %}{{ item }}{% endfor %}"
        result = template_engine.render_string(template, {"items": ["a", "b", "c"]})
        assert result == "abc"

    def test_nested_object_access(self, template_engine: TemplateEngine):
        """Test accessing nested object properties."""
        template = "{{ event.venue.name }}"
        result = template_engine.render_string(
            template,
            {"event": {"venue": {"name": "The Camel"}}},
        )
        assert result == "The Camel"

    def test_missing_variable_handling(self, template_engine: TemplateEngine):
        """Test handling of missing variables."""
        template = "Hello, {{ name }}!"
        # Jinja2 renders missing variables as empty string by default
        result = template_engine.render_string(template, {})
        assert result == "Hello, !"

    def test_whitespace_control(self, template_engine: TemplateEngine):
        """Test that whitespace is properly controlled."""
        template = """{% for i in items %}
- {{ i }}
{% endfor %}"""
        result = template_engine.render_string(template, {"items": ["a", "b"]})
        # Should have clean output without extra blank lines
        lines = [l for l in result.strip().split("\n") if l.strip()]
        assert len(lines) == 2


class TestTemplateNotFound:
    """Tests for template not found handling."""

    def test_missing_template_raises_error(self):
        """Test that missing template raises appropriate error."""
        from jinja2 import TemplateNotFound

        engine = TemplateEngine()
        with pytest.raises(TemplateNotFound):
            engine.render("nonexistent_template.md", {})
