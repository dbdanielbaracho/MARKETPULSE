from pathlib import Path


def test_i18n_policy_documents_english_as_default_and_no_browser_translation():
    text = Path("docs/I18N.md").read_text(encoding="utf-8")
    assert "English (`en`) is the canonical and default public interface language" in text
    assert "must not depend on browser automatic translation" in text
    assert "Provider market titles and contract identity remain in their original source wording" in text
