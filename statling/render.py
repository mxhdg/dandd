#!/usr/bin/env python3
"""Statling - D&D 5e Character Sheet Renderer.

Render D&D 5e character sheets from YAML using Jinja2 templates.

Usage:
    python statling/render.py <yaml_file> [options]

    Or from project root:
    python -m statling.render <yaml_file> [options]

Options:
    -t, --template TEMPLATE    Template file to use
                               (default: character_sheet_5e_2014.j2)
    -o, --output OUTPUT        Output file path (default: stdout)

Examples:
    python statling/render.py characters/2014_elowen_turnerleaf.yaml
    python statling/render.py characters/2014_elowen_turnerleaf.yaml \
        -o output.md
    python -m statling.render characters/character.yaml \
        -t custom_template.j2
"""

import argparse
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape


class CharacterRenderer:
    """Renders D&D character sheets from YAML data."""

    def __init__(self, template_dir: Path | str | None = None) -> None:
        """Initialize the renderer.

        Args:
            template_dir: Directory containing Jinja2 templates.
                         Defaults to statling/templates.

        """
        if template_dir is None:
            # Default to templates dir relative to this script
            template_dir = Path(__file__).parent / 'templates'

        self.template_dir = Path(template_dir)

        # Set up Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    
    def render(
        self,
        yaml_path: Path | str,
        template_name: str = 'character_sheet_5e_2014.j2',
    ) -> str:
        """Render a character sheet from YAML data.

        Args:
            yaml_path: Path to the YAML character data file.
            template_name: Name of the template file to use.

        Returns:
            Rendered character sheet as a string.

        """
        yaml_path = Path(yaml_path)

        # Load YAML data
        with open(yaml_path, 'r', encoding='utf-8') as f:
            character_data = yaml.safe_load(f)

        # Load and render template
        template = self.env.get_template(template_name)
        return template.render(**character_data)
    
    def render_to_file(
        self,
        yaml_path: Path | str,
        output_path: Path | str,
        template_name: str = 'character_sheet_5e_2014.j2',
    ) -> None:
        """Render a character sheet and save to file.

        Args:
            yaml_path: Path to the YAML character data file.
            output_path: Path for the output file.
            template_name: Name of the template file to use.

        """
        rendered = self.render(yaml_path, template_name)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(rendered)


def main() -> None:
    """Command-line interface for the character renderer."""
    parser = argparse.ArgumentParser(
        description='Render D&D 5e character sheets from YAML',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s characters/character.yaml
  %(prog)s characters/character.yaml -o output.md
  %(prog)s characters/character.yaml -t custom.j2 -o output.md
        """,
    )

    parser.add_argument(
        'yaml_file',
        help='Path to YAML character file',
    )

    parser.add_argument(
        '-t',
        '--template',
        default='character_sheet_5e_2014.j2',
        help='Template file to use (default: character_sheet_5e_2014.j2)',
    )

    parser.add_argument(
        '-o',
        '--output',
        help='Output file path (default: print to stdout)',
    )

    args = parser.parse_args()

    # Initialize renderer
    renderer = CharacterRenderer()

    try:
        if args.output:
            renderer.render_to_file(
                args.yaml_file,
                args.output,
                args.template,
            )
            msg = f"Character sheet rendered to {args.output}"
            print(msg, file=sys.stderr)
        else:
            rendered = renderer.render(args.yaml_file, args.template)
            print(rendered)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
