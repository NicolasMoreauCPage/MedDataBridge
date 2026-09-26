from app.utils.safe_html import sanitize_document_html, sanitize_icon_svg


def test_document_html_sanitizer_removes_active_markup_and_urls():
    rendered = sanitize_document_html(
        '<p>Guide</p><script>alert(1)</script><a href="javascript:alert(1)">lien</a>'
    )

    assert '<script' not in rendered
    assert 'javascript:' not in rendered
    assert '<p>Guide</p>' in rendered


def test_icon_svg_sanitizer_keeps_paths_without_event_handlers():
    rendered = sanitize_icon_svg(
        '<svg class="w-4" onclick="alert(1)"><path d="M0 0" onload="alert(1)"/></svg>'
    )

    assert '<svg class="w-4">' in rendered
    assert '<path d="M0 0">' in rendered
    assert 'onload' not in rendered
    assert 'onclick' not in rendered
