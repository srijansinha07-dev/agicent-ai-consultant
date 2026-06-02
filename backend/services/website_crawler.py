from playwright.sync_api import (
    sync_playwright
)

from bs4 import BeautifulSoup

from urllib.parse import (
    urljoin,
    urlparse
)

from collections import deque

import json
import os


BASE_URL = (
    "https://www.agicent.com"
)

SAVE_PATH = (
    "data/crawled_pages.json"
)

SKIP_EXTENSIONS = (
    ".pdf",
    ".doc",
    ".docx",
    ".zip",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".mp4",
    ".mp3",
)


def is_internal(
    url: str
) -> bool:

    return (
        urlparse(url).netloc
        ==
        urlparse(BASE_URL).netloc
    )


def clean_url(
    url: str
) -> str:

    return (
        url
        .split("#")[0]
        .split("?")[0]
        .rstrip("/")
    )


def should_skip(
    url: str
) -> bool:

    return (
        url.lower()
        .endswith(
            SKIP_EXTENSIONS
        )
    )


def save_progress(
    pages
):

    os.makedirs(
        "data",
        exist_ok=True
    )

    with open(
        SAVE_PATH,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            pages,
            f,
            indent=2,
            ensure_ascii=False
        )


def crawl_website(
    max_pages: int = 250
):

    visited = set()

    queue = deque(
        [BASE_URL]
    )

    pages = []

    with sync_playwright() as p:

        browser = (
            p.chromium.launch(
                headless=True
            )
        )

        context = (
            browser.new_context()
        )

        page = (
            context.new_page()
        )

        while (
            queue
            and
            len(visited)
            < max_pages
        ):

            url = clean_url(
                queue.popleft()
            )

            if (
                not url
                or url in visited
                or should_skip(url)
            ):
                continue

            print(
                f"[{len(visited)+1}] "
                f"Crawling: "
                f"{url}"
            )

            try:

                page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=60000,
                )

                # allow lazy content
                page.wait_for_timeout(
                    3000
                )

                html = (
                    page.content()
                )

                soup = (
                    BeautifulSoup(
                        html,
                        "lxml"
                    )
                )

                title = (
                    soup.title.text.strip()
                    if soup.title
                    else ""
                )

                visited.add(
                    url
                )

                pages.append(
                    {
                        "url": url,
                        "title": title,
                        "html": html,
                    }
                )

                # save after every page
                save_progress(
                    pages
                )

                for link in soup.find_all(
                    "a",
                    href=True
                ):

                    href = urljoin(
                        BASE_URL,
                        link["href"]
                    )

                    href = clean_url(
                        href
                    )

                    if (
                        href
                        and is_internal(
                            href
                        )
                        and href
                        not in visited
                        and not should_skip(
                            href
                        )
                    ):
                        queue.append(
                            href
                        )

            except Exception as e:

                print(
                    f"Failed:"
                    f" {url}"
                )

                print(e)

        browser.close()

    print(
        f"\nDone."
        f" Crawled "
        f"{len(pages)} "
        f"pages."
    )

    return pages