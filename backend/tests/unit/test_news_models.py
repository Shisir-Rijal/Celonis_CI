"""Unit tests for NewsItem.to_rag_document() and NewsData.to_rag_documents() / get_frequency().

Issue #98
"""

from datetime import datetime
from app.agents.research.state import NewsItem, NewsData


# --- NewsItem.to_rag_document() ---

def test_to_rag_document_all_fields():
    item = NewsItem(
        heading="Celonis raises $1B",
        text="Celonis announced today that it has raised one billion dollars in a new funding round. " * 3,
        summary="Celonis raises $1B",
        source="serper",
        source_link="https://techcrunch.com/celonis",
        date="2024-01-15",
    )
    doc = item.to_rag_document(company="celonis")

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
    assert isinstance(doc["metadata"]["date"], datetime)


def test_to_rag_document_only_heading():
    item = NewsItem(heading="Celonis news")
    doc = item.to_rag_document(company="celonis")

    assert doc["content"] == "Celonis news"
    assert doc["metadata"]["chunking_strategy"] == "none"


def test_to_rag_document_short_text():
    item = NewsItem(
        heading="Short",
        text="Short text.",
    )
    doc = item.to_rag_document(company="celonis")

    assert doc["content"] == "Short text."
    assert doc["metadata"]["chunking_strategy"] == "agentic"


def test_to_rag_document_text_longer_than_100():
    item = NewsItem(
        text="a" * 101,
    )
    doc = item.to_rag_document(company="celonis")

    assert doc["metadata"]["chunking_strategy"] == "structural"


def test_to_rag_document_content_fallback_order():
    # text takes priority over summary
    item = NewsItem(text="full text", summary="summary", heading="heading")
    assert item.to_rag_document(company="celonis")["content"] == "full text"

    # summary takes priority over heading
    item2 = NewsItem(summary="summary", heading="heading")
    assert item2.to_rag_document(company="celonis")["content"] == "summary"

    # heading is last fallback
    item3 = NewsItem(heading="heading")
    assert item3.to_rag_document(company="celonis")["content"] == "heading"


def test_to_rag_document_invalid_date_fallback():
    item = NewsItem(heading="Test", date="not-a-date")
    doc = item.to_rag_document(company="celonis")
    assert isinstance(doc["metadata"]["date"], datetime)


def test_to_rag_document_no_source_link():
    item = NewsItem(heading="Test")
    doc = item.to_rag_document(company="celonis")
    assert doc["metadata"]["url"] == ""


# --- NewsData.to_rag_documents() ---

def test_to_rag_documents_skips_empty_content():
    data = NewsData(news=[
        NewsItem(heading="Has content"),
        NewsItem(),  # no text, no summary, no heading → empty content
    ])
    docs = data.to_rag_documents(company="celonis")
    assert len(docs) == 1
    assert docs[0]["content"] == "Has content"


def test_to_rag_documents_all_valid():
    data = NewsData(news=[
        NewsItem(heading="Article 1"),
        NewsItem(heading="Article 2"),
    ])
    docs = data.to_rag_documents(company="celonis")
    assert len(docs) == 2


# --- NewsData.get_frequency() ---

def test_get_frequency_aggregates_same_date():
    data = NewsData(news=[
        NewsItem(heading="A", date="2024-01-15"),
        NewsItem(heading="B", date="2024-01-15"),
        NewsItem(heading="C", date="2024-01-16"),
    ])
    freq = data.get_frequency()
    assert freq["2024-01-15"] == 2
    assert freq["2024-01-16"] == 1


def test_get_frequency_skips_none_date():
    data = NewsData(news=[
        NewsItem(heading="A", date="2024-01-15"),
        NewsItem(heading="B", date=None),
    ])
    freq = data.get_frequency()
    assert len(freq) == 1
    assert "2024-01-15" in freq


def test_get_frequency_empty():
    data = NewsData(news=[])
    assert data.get_frequency() == {}