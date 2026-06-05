"""Unit tests for app/ingestion/chunking/entity_extractor.py."""

from app.ingestion.chunking.entity_extractor import extract_entities


class TestEmailExtraction:
    def test_detects_standard_email(self):
        result = extract_entities("Contact us at hello@celonis.com for more info.")
        assert "hello@celonis.com" in result

    def test_detects_multiple_emails(self):
        result = extract_entities("From: a@x.com, b@y.com")
        assert "a@x.com" in result
        assert "b@y.com" in result


class TestUrlExtraction:
    def test_detects_https_url(self):
        result = extract_entities("Visit https://celonis.com for details.")
        assert "https://celonis.com" in result

    def test_detects_http_url(self):
        result = extract_entities("See http://example.com/path?q=1")
        assert "http://example.com/path?q=1" in result


class TestPhoneExtraction:
    def test_detects_international_format(self):
        result = extract_entities("Call us: +49 89 123456")
        assert any("49" in e and "123456" in e for e in result)

    def test_detects_slash_format(self):
        result = extract_entities("Phone: 089/123456")
        assert any("089" in e for e in result)


class TestDeduplication:
    def test_duplicate_entity_appears_once(self):
        result = extract_entities("hello@celonis.com and hello@celonis.com again")
        assert result.count("hello@celonis.com") == 1


class TestEdgeCases:
    def test_empty_text_returns_empty_list(self):
        assert extract_entities("") == []

    def test_no_entities_returns_empty_list(self):
        assert extract_entities("This text has no structured entities at all.") == []

    def test_mixed_entities_all_detected(self):
        text = "Email: ceo@celonis.com | Web: https://celonis.com | Phone: +49 89 123456"
        result = extract_entities(text)
        assert any("@" in e for e in result)
        assert any("https" in e for e in result)
        assert any("49" in e for e in result)
