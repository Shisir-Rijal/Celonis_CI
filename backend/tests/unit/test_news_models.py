"""Unit tests for to_rag_document(), to_rag_documents(), get_frequency(), to_source().

Issue #109
"""

from datetime import datetime
from app.agents.research.state import (
    NewsItem,
    NewsData,
    to_rag_document,
    to_rag_documents,
    get_frequency,
    to_source,
)


def _make_item(**kwargs) -> NewsItem:
    """Helper: create a NewsItem with required BaseData fields."""
    defaults = {"company": "celonis", "url": "https://celonis.com"}
    defaults.update(kwargs)
    return NewsItem(**defaults)


# --- to_rag_document() ---

def test_to_rag_document_all_fields():
    item = _make_item(
        heading="Celonis raises $1B",
        text="Celonis announced today that it has raised one billion dollars in a new funding round. " * 3,
        summary="Celonis raises $1B",
        url="https://techcrunch.com/celonis",
        published_date="2024-01-15",
    )
    doc = to_rag_document(item, company="celonis")

    assert doc["content"] == item.text
    assert doc["metadata"]["company"] == "celonis"
    assert doc["metadata"]["source_type"] == "news"
    assert doc["metadata"]["source_origin"] == "earned"
    assert doc["metadata"]["url"] == "https://techcrunch.com/celonis"
    assert doc["metadata"]["title"] == "Celonis raises $1B"
    assert doc["metadata"]["language"] == "en"
    assert doc["metadata"]["topic"] == ["news"]
    assert doc["metadata"]["content_type"] == "text"
    assert doc["metadata"]["visual_type"] is None
    assert doc["metadata"]["chunking_strategy"] == "structural"


def test_to_rag_document_only_heading():
    item = _make_item(heading="Celonis news")
    doc = to_rag_document(item, company="celonis")
    assert doc["content"] == "Celonis news"
    assert doc["metadata"]["chunking_strategy"] == "none"


def test_to_rag_document_short_text():
    item = _make_item(heading="Short", text="Short text.")
    doc = to_rag_document(item, company="celonis")
    assert doc["content"] == "Short text."
    assert doc["metadata"]["chunking_strategy"] == "agentic"


def test_to_rag_document_text_longer_than_100():
    item = _make_item(text="a" * 101)
    doc = to_rag_document(item, company="celonis")
    assert doc["metadata"]["chunking_strategy"] == "structural"


def test_to_rag_document_content_fallback_order():
    item = _make_item(text="full text", summary="summary", heading="heading")
    assert to_rag_document(item, company="celonis")["content"] == "full text"

    item2 = _make_item(summary="summary", heading="heading")
    assert to_rag_document(item2, company="celonis")["content"] == "summary"

    item3 = _make_item(heading="heading")
    assert to_rag_document(item3, company="celonis")["content"] == "heading"


def test_to_rag_document_no_url():
    item = _make_item(heading="Test", url="")
    doc = to_rag_document(item, company="celonis")
    assert doc["metadata"]["url"] == ""


# --- to_rag_documents() ---

def test_to_rag_documents_skips_empty_content():
    data = NewsData(news=[
        _make_item(heading="Has content"),
        _make_item(),  # no text, no summary, no heading → empty content
    ])
    docs = to_rag_documents(data, company="celonis")
    assert len(docs) == 1
    assert docs[0]["content"] == "Has content"


def test_to_rag_documents_all_valid():
    data = NewsData(news=[
        _make_item(heading="Article 1"),
        _make_item(heading="Article 2"),
    ])
    docs = to_rag_documents(data, company="celonis")
    assert len(docs) == 2


# --- get_frequency() ---

def test_get_frequency_aggregates_same_date():
    data = NewsData(news=[
        _make_item(heading="A", published_date="2024-01-15"),
        _make_item(heading="B", published_date="2024-01-15"),
        _make_item(heading="C", published_date="2024-01-16"),
    ])
    freq = get_frequency(data)
    assert freq["2024-01-15"] == 2
    assert freq["2024-01-16"] == 1


def test_get_frequency_skips_none_date():
    data = NewsData(news=[
        _make_item(heading="A", published_date="2024-01-15"),
        _make_item(heading="B", published_date=None),
    ])
    freq = get_frequency(data)
    assert len(freq) == 1
    assert "2024-01-15" in freq


def test_get_frequency_empty():
    data = NewsData(news=[])
    assert get_frequency(data) == {}


# --- to_source() ---

def test_to_source_all_fields():
    item = _make_item(
        heading="Celonis raises $1B",
        url="https://techcrunch.com/celonis",
    )
    source = to_source(item)
    assert source.url == "https://techcrunch.com/celonis"
    assert source.title == "Celonis raises $1B"
    assert source.relevance_score == 1.0


def test_to_source_no_heading():
    item = _make_item(url="https://techcrunch.com/celonis")
    source = to_source(item)
    assert source.title is None


def test_to_source_empty_url():
    item = _make_item(heading="Test", url="")
    source = to_source(item)
    assert source.url == ""