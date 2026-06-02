import json

from services.website_extractor import (
    extract_page_content
)


INPUT_FILE = (
    "data/crawled_pages.json"
)

OUTPUT_FILE = (
    "data/cleaned_pages.json"
)


def process_pages():

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        pages = json.load(
            f
        )

    cleaned_pages = []

    for i, page in enumerate(
        pages,
        start=1
    ):

        print(
            f"[{i}/{len(pages)}] "
            f"Processing:"
            f" {page['url']}"
        )

        try:

            extracted = (
                extract_page_content(
                    page["html"]
                )
            )

            cleaned_pages.append(
                {
                    "url":
                        page["url"],

                    "title":
                        extracted[
                            "title"
                        ],

                    "headings":
                        extracted[
                            "headings"
                        ],

                    "content":
                        extracted[
                            "content"
                        ]
                }
            )

        except Exception as e:

            print(
                f"Failed:"
                f" {page['url']}"
            )

            print(e)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            cleaned_pages,
            f,
            indent=2,
            ensure_ascii=False
        )

    print(
        f"\nDone."
        f" Saved "
        f"{len(cleaned_pages)} "
        f" cleaned pages."
    )


if __name__ == "__main__":
    process_pages()