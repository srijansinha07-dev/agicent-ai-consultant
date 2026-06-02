from services.website_crawler import (
    crawl_website
)

pages = crawl_website(
    max_pages=250
)

print(
    f"\nPages found:"
    f" {len(pages)}"
)

print(
    "\nSample URLs:\n"
)

for page in pages[:20]:
    print(
        page["url"]
    )