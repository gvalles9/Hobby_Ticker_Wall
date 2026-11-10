"""Guards against version drift between version.py, CHANGELOG, and README."""

import re
from pathlib import Path

from version import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]
VERSION = ".".join(map(str, APP_VERSION))


def test_changelog_has_a_dated_release_for_the_current_version():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = rf"^## \[{re.escape(VERSION)}\] - \d{{4}}-\d{{2}}-\d{{2}}$"

    assert re.search(heading, text, re.MULTILINE), (
        f"CHANGELOG.md has no dated release heading for {VERSION}; bump "
        "version.py or fold [Unreleased] into a release section first."
    )


def test_readme_names_the_current_product_version():
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    assert f"`{VERSION}`" in text, (
        f"README.md does not mention version {VERSION}; update the "
        "product-version sentence before shipping."
    )
