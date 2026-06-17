import json
import uuid

from services.chunker import (
    chunk_pages
)

from services.vectorstore import (
    index_chunks
)

from services import docstore

from models import (
    IndexStatus
)


INPUT_FILE = (
    "data/cleaned_pages.json"
)


def build_pages(
    website_pages
):
    """
    Convert website JSON into
    PDF-style page format so we
    can reuse chunk_pages().
    """

    pages = []

    for i, page in enumerate(
        website_pages,
        start=1
    ):

        title = page.get(
            "title",
            ""
        )

        headings = page.get(
            "headings",
            []
        )

        content = page.get(
            "content",
            ""
        )

        url = page.get(
            "url",
            ""
        )

        combined_text = (
            f"{title}\n\n"
            f"URL: {url}\n\n"
            f"{' | '.join(headings)}\n\n"
            f"{content}"
        )

        pages.append(
            {
                "page_num": i,
                "text": combined_text,
                "ocr_used": False,
            }
        )

    return pages


def ingest_website():

    print(
        "\nLoading website data..."
    )

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        website_pages = (
            json.load(f)
        )

    print(
        f"Loaded "
        f"{len(website_pages)} "
        f"website pages"
    )

    # Convert website → page format
    pages = build_pages(
        website_pages
    )

    # Create unique doc id
    doc_id = "agicent_website"
    

    print(
        "\nRegistering "
        "website..."
    )

    docstore.register(
        doc_id=doc_id,
        user_id="website_bot",
        name="Agicent Website",
        pdf_path="website://agicent",
        pages=len(pages),
    )

    print(
        "Chunking..."
    )

    chunks = chunk_pages(
        pages,
        doc_id
    )

    print(
        f"Created "
        f"{len(chunks)} "
        f"chunks"
    )

    print(
        "Saving pages..."
    )

    docstore.set_pages(
        doc_id,
        pages
    )

    print(
        "Saving chunks..."
    )

    docstore.set_chunks(
        doc_id,
        chunks
    )

    print(
        "Indexing into "
        "ChromaDB..."
    )

    index_chunks(
        doc_id,
        chunks
    )

    print(
        "Marking READY..."
    )

    docstore.set_status(
        doc_id,
        IndexStatus.READY
    )
    print(
        "Status after set:",
        docstore.get_info(
            doc_id
        ).status
    )

    print(
        "\nDone!"
    )

    print(
        f"\nDOC ID:"
        f" {doc_id}"
    )

    return doc_id


if __name__ == "__main__":
    ingest_website()