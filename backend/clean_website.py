import json

from services.website_cleaner import (
    clean_content
)


INPUT_FILE = (
    "data/cleaned_pages.json"
)

OUTPUT_FILE = (
    "data/cleaned_pages_v2.json"
)


def clean_pages():

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
            f"[{i}/{len(pages)}]"
            f" Cleaning "
            f"{page['url']}"
        )

        cleaned_text = (
            clean_content(
                page["content"]
            )
        )

        cleaned_pages.append(
            {
                "url":
                    page["url"],

                "title":
                    page["title"],

                "headings":
                    page[
                        "headings"
                    ],

                "content":
                    cleaned_text
            }
        )

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
        f"{len(cleaned_pages)}"
        f" cleaned pages."
    )


if __name__ == "__main__":
    clean_pages()