# Sphinx configuration for the cloudlib documentation.
# Pages are written in Markdown (MyST); API docs come from docstrings via autodoc.
from importlib.metadata import version as _pkg_version

# -- Project information -----------------------------------------------------
project = "cloudlib"
author = "Phil Austin"
copyright = "2024, Phil Austin"
release = _pkg_version("cloudlib")
version = release

# -- General configuration ---------------------------------------------------
extensions = [
    "myst_parser",
    "sphinx.ext.mathjax",
    "sphinx.ext.viewcode",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
root_doc = "index"
exclude_patterns = ["_build", ".pixi", "src", "README.md", "Thumbs.db", ".DS_Store"]

# MyST: $...$ / $$...$$ math, ::: fenced directives, auto anchors for headings
myst_enable_extensions = ["dollarmath", "amsmath", "colon_fence"]
myst_heading_anchors = 3

# autodoc / napoleon (docstrings are NumPy style)
autodoc_member_order = "bysource"
napoleon_numpy_docstring = True
napoleon_google_docstring = False

pygments_style = "sphinx"

# -- HTML output -------------------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_title = "cloudlib"
html_short_title = "cloudlib"
