"""Garde-fou contre le retour des boîtes de dialogue navigateur dans les écrans actifs."""

import re
from pathlib import Path


TEMPLATE_ROOT = Path("app/templates")
LEGACY_OR_COMPONENT_TEMPLATES = {
    Path("base.html"),  # repli progressif centralisé dans PameliaUi.
    Path("components.html"),
    Path("home.html"),
    Path("macros/ui.html"),
    Path("hprim_cotation_modern.html"),  # écran historique non routé.
    Path("cotations/liste.html"),  # remplacé par le workspace de saisie rapide.
    Path("components/cotations_inline.html"),  # composant historique non inclus.
}
NATIVE_DIALOG_PATTERN = re.compile(r"(?<![.\w])(?:alert|confirm)\s*\(")


def test_active_templates_do_not_use_native_browser_dialogs() -> None:
    offenders = []
    for template in TEMPLATE_ROOT.rglob("*.html"):
        relative_path = template.relative_to(TEMPLATE_ROOT)
        if relative_path in LEGACY_OR_COMPONENT_TEMPLATES:
            continue
        if NATIVE_DIALOG_PATTERN.search(template.read_text(encoding="utf-8")):
            offenders.append(str(relative_path))

    assert offenders == [], f"Dialogues natifs à migrer : {', '.join(offenders)}"
