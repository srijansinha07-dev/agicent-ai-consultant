"""Targeted checks for website retrieval improvements (no live LLM/Chroma required)."""
from __future__ import annotations

from models import Chunk, QueryType
from services import retriever as ret_svc
from services.website_support import (
    apply_website_metadata_boosts,
    expand_website_retrieval_query,
    extract_website_metadata,
    is_website_company_query,
    is_website_doc,
)


def test_company_query_detection():
    assert is_website_company_query("What AI services does Agicent provide?")
    assert is_website_company_query("What hiring models does Agicent offer?")
    assert not is_website_company_query("What is on page 3?")


def test_query_expansion():
    q = "What AI services does Agicent provide?"
    expanded = expand_website_retrieval_query(q)
    assert "generative AI" in expanded
    assert "Agicent" in expanded
    assert expanded.startswith(q)


def test_metadata_boost_prefers_services_over_blog_tag():
    good = Chunk(
        text="AI Development Services\n\nURL: https://www.agicent.com/ai-development-services\n\nAI | Services\n\nContent",
        page=1,
        chunk_id="a",
        doc_id="x",
        score=0.5,
    )
    bad = Chunk(
        text="Tag Archive\n\nURL: https://www.agicent.com/blog/tag/mobile\n\nTags\n\nContent",
        page=2,
        chunk_id="b",
        doc_id="x",
        score=0.5,
    )
    apply_website_metadata_boosts(good)
    apply_website_metadata_boosts(bad)
    assert good.score > bad.score


def test_extract_metadata():
    c = Chunk(
        text="AI Services\n\nURL: https://example.com/services\n\nHeading A | B\n\nBody",
        page=1,
        chunk_id="c",
        doc_id="x",
        score=0.0,
    )
    url, title, _ = extract_website_metadata(c)
    assert "services" in url
    assert "ai services" in title


def test_pdf_classify_unchanged():
    qtype, page = ret_svc.classify("What is the z-test formula on page 4?")
    assert qtype == QueryType.FORMULA or qtype == QueryType.PAGE


def test_is_website_doc_with_mock(monkeypatch):
    monkeypatch.setattr(
        "services.docstore.get_pdf_path",
        lambda doc_id: "website://agicent" if doc_id == "web1" else "/tmp/file.pdf",
    )
    assert is_website_doc("web1")
    assert not is_website_doc("pdf1")


if __name__ == "__main__":
    test_company_query_detection()
    test_query_expansion()
    test_metadata_boost_prefers_services_over_blog_tag()
    test_extract_metadata()
    test_pdf_classify_unchanged()
    print("All website_support unit checks passed.")
