""" Sphinx configuration for the PyLabTools documentation.

Build with:  sphinx-build -W -b html docs docs/_build/html
"""
import os
import sys

sys.path.insert(0, os.path.abspath(".."))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pylabtools  # noqa: E402

project = "PyLabTools"
author = "Sam Condon"
copyright = "2022-2026, Sam Condon"
release = pylabtools.__version__
version = ".".join(release.split(".")[:2])

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]
autosectionlabel_prefix_document = True
autodoc_member_order = "bysource"
autodoc_default_options = {"members": True, "show-inheritance": True}

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pandas": ("https://pandas.pydata.org/docs", None),
    "pymeasure": ("https://pymeasure.readthedocs.io/en/latest", None),
}
# - intersphinx inventories are a network fetch; a failure must not break offline builds - #
suppress_warnings = ["intersphinx.external"]

exclude_patterns = ["_build"]
html_theme = "sphinx_book_theme"
html_title = f"PyLabTools {release}"
html_theme_options = {
    "repository_url": "https://github.com/samcondon4/PyLabTools",
    "use_repository_button": True,
}
