"""Contrôles Axe dans un navigateur réel sur les parcours prioritaires."""

from __future__ import annotations

from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AXE_SOURCE = REPOSITORY_ROOT / "node_modules" / "axe-core" / "axe.min.js"
WCAG_AA_TAGS = ["wcag2a", "wcag2aa"]
PRIORITY_PATHS = ["/scenarios/new", "/structure/wizard", "/validation"]


def _format_violations(violations: list[dict]) -> str:
    """Produce a concise, actionable pytest failure message."""

    lines: list[str] = []
    for violation in violations:
        nodes = ", ".join(
            " | ".join(node.get("target", []))
            for node in violation.get("nodes", [])[:3]
        )
        lines.append(
            f"{violation['id']} ({violation['impact']}): {violation['help']}"
            + (f" — {nodes}" if nodes else "")
        )
    return "\n".join(lines)


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
@pytest.mark.parametrize("path", PRIORITY_PATHS)
async def test_priority_workspaces_have_no_serious_or_critical_axe_violation(page, path: str) -> None:
    """Axe runs in Chromium, on the rendered DOM rather than on template text."""

    assert AXE_SOURCE.is_file(), "axe-core est requis : exécutez `npm ci` avant les tests navigateur."
    response = await page.goto(path, wait_until="networkidle")
    assert response is not None and response.status == 200
    await page.add_script_tag(path=str(AXE_SOURCE))
    result = await page.evaluate(
        """async (tags) => axe.run(document, {
          runOnly: { type: 'tag', values: tags },
          resultTypes: ['violations'],
        })""",
        WCAG_AA_TAGS,
    )
    blocking = [
        violation
        for violation in result["violations"]
        if violation.get("impact") in {"critical", "serious"}
    ]
    assert not blocking, _format_violations(blocking)


@pytest.mark.e2e_phase6
@pytest.mark.asyncio
@pytest.mark.parametrize("path", PRIORITY_PATHS)
async def test_priority_workspaces_expose_a_visible_keyboard_focus(page, path: str) -> None:
    """The first interactive element reached with Tab must be visibly focused."""

    response = await page.goto(path, wait_until="networkidle")
    assert response is not None and response.status == 200
    await page.keyboard.press("Tab")
    focus = await page.evaluate(
        """() => {
          const element = document.activeElement;
          const style = getComputedStyle(element);
          return {
            tag: element?.tagName,
            id: element?.id || null,
            className: element?.className || null,
            outline: style.outlineStyle !== 'none' && style.outlineWidth !== '0px',
            boxShadow: style.boxShadow !== 'none',
          };
        }"""
    )
    assert focus["tag"] in {"A", "BUTTON", "INPUT", "SELECT", "TEXTAREA"}
    assert focus["outline"] or focus["boxShadow"], (
        "Le focus clavier doit rester visuellement perceptible : "
        f"{focus['tag']}#{focus['id']} ({focus['className']})."
    )
