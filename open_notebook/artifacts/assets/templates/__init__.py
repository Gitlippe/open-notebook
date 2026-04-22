"""Jinja2 templates for artifact rendering.

Templates are discovered at runtime via importlib.resources:
    from importlib.resources import files
    tmpl = files('open_notebook.artifacts.assets.templates') / 'infographic_default.svg.j2'
"""
