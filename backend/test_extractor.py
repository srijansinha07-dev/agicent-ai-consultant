import json

from services.website_extractor import (
    extract_page_content
)

with open(
    "data/crawled_pages.json",
    "r",
    encoding="utf-8"
) as f:

    pages = json.load(f)

sample = pages[0]

result = extract_page_content(
    sample["html"]
)

print("\nURL:")
print(sample["url"])

print("\nTITLE:")
print(result["title"])

print("\nHEADINGS:")
print(
    result["headings"][:10]
)

print(
    "\nCONTENT SAMPLE:\n"
)

print(
    result["content"][:3000]
)