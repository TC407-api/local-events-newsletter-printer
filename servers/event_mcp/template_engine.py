"""Jinja2 template engine for newsletter rendering."""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape


class TemplateEngine:
    """Render newsletter templates using Jinja2."""

    def __init__(self, template_dir: Path | None = None):
        """Initialize template engine with template directory.

        Args:
            template_dir: Path to templates directory.
                         Defaults to project templates/ folder.
        """
        if template_dir is None:
            template_dir = Path(__file__).parent.parent.parent / "templates"

        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template with the given context.

        Args:
            template_name: Name of template file (e.g., 'default.md')
            context: Dictionary of template variables

        Returns:
            Rendered template string

        Raises:
            TemplateNotFound: If template doesn't exist
        """
        template = self.env.get_template(template_name)
        return template.render(**context)

    def render_string(self, template_string: str, context: dict[str, Any]) -> str:
        """Render a template from a string.

        Args:
            template_string: Jinja2 template string
            context: Dictionary of template variables

        Returns:
            Rendered string
        """
        template = self.env.from_string(template_string)
        return template.render(**context)

    def list_templates(self) -> list[str]:
        """List all available templates.

        Returns:
            List of template filenames
        """
        return self.env.list_templates()

    def template_exists(self, template_name: str) -> bool:
        """Check if a template exists.

        Args:
            template_name: Name of template file

        Returns:
            True if template exists
        """
        try:
            self.env.get_template(template_name)
            return True
        except TemplateNotFound:
            return False
