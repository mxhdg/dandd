"""Statling - D&D 5e Character Sheet Renderer.

A tool for rendering D&D 5e character sheets from YAML data using
Jinja2 templates.
"""

from .render import CharacterRenderer

__version__ = '0.1.0'
__all__ = ['CharacterRenderer']
