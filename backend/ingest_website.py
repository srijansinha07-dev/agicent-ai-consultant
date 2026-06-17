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
    

    temp_doc_id = f"{doc_id}_temp"
    
    print("\n🔄 [REBUILD] Starting atomic rebuild...")
    print(f"📦 [REBUILD] Creating temporary collection: {temp_doc_id}")

    from services.vectorstore import delete_collection, _get_client, _safe_col_name
    
    # Ensure temp is clean
    delete_collection(temp_doc_id)

    print(f"📄 [REBUILD] Registering temporary doc metadata for {temp_doc_id}...")

    docstore.register(
        doc_id=temp_doc_id,
        user_id="website_bot",
        name="Agicent Website (Building)",
        pdf_path="website://agicent",
        pages=len(pages),
    )

    print("⚙️ [REBUILD] Chunking pages...")

    chunks = chunk_pages(
        pages,
        doc_id  # Keep chunk's internal doc_id pointing to the real ID!
    )

    print(f"✅ [REBUILD] Created {len(chunks)} chunks")

    print("💾 [REBUILD] Indexing chunks into temporary ChromaDB collection...")
    # We pass temp_doc_id to vectorstore so it creates agicent-website-temp
    index_chunks(
        temp_doc_id,
        chunks
    )

    print("\n🔍 [REBUILD] Validating newly built collection...")
    client = _get_client()
    temp_col = client.get_collection(_safe_col_name(temp_doc_id))
    
    count = temp_col.count()
    print(f"📊 [VALIDATION] Chunk count: {count} (Expected: >= 4000)")
    
    res = temp_col.query(query_texts=["HASfit"], n_results=10)
    has_hasfit = False
    if res and res.get('documents') and res['documents'][0]:
        for doc in res['documents'][0]:
            if 'hasfit' in doc.lower():
                has_hasfit = True
                break
                
    print(f"🔎 [VALIDATION] HASfit case study exists: {has_hasfit}")

    if count >= 4000 and has_hasfit:
        print("\n✅ [VALIDATION PASSED] Performing atomic swap...")
        try:
            real_col_name = _safe_col_name(doc_id)
            temp_col_name = _safe_col_name(temp_doc_id)
            old_col_name = f"{real_col_name}-old"
            
            # Delete any lingering old backup
            delete_collection(f"{doc_id}_old")
            
            # Step 1: Rename current to old
            try:
                real_col = client.get_collection(real_col_name)
                real_col.modify(name=old_col_name)
                print(f"   -> Renamed active '{real_col_name}' to '{old_col_name}'")
            except Exception as e:
                print(f"   -> No existing '{real_col_name}' to rename ({e})")
                
            # Step 2: Rename temp to real (The atomic swap)
            temp_col.modify(name=real_col_name)
            print(f"   -> Renamed temp '{temp_col_name}' to active '{real_col_name}'")
            
            # Step 3: Cleanup old
            delete_collection(f"{doc_id}_old")
            print(f"   -> Cleaned up '{old_col_name}'")
            
            # Finally update docstore metadata pointers
            print("💾 [REBUILD] Updating docstore metadata to active...")
            docstore.set_pages(doc_id, pages)
            docstore.set_chunks(doc_id, chunks)
            docstore.set_status(doc_id, IndexStatus.READY)
            
            print(f"🎉 [REBUILD COMPLETE] Active collection '{real_col_name}' now has {count} chunks!")
            
        except Exception as e:
            print(f"❌ [SWAP FAILED] Exception during swap: {e}")
            print(f"⚠️ [REBUILD ABORTED] Original collection '{_safe_col_name(doc_id)}' remains untouched.")
    else:
        print(f"❌ [VALIDATION FAILED] Rebuild did not meet criteria. Count={count}, HASfit={has_hasfit}")
        print(f"⚠️ [REBUILD ABORTED] Original collection '{_safe_col_name(doc_id)}' remains untouched.")

    print(
        f"\nDOC ID:"
        f" {doc_id}"
    )

    return doc_id


if __name__ == "__main__":
    ingest_website()