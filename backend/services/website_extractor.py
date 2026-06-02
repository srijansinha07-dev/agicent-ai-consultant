from bs4 import BeautifulSoup
import re


REMOVE_TAGS = [
    "script",
    "style",
    "noscript",
    "iframe",
    "svg",
    "canvas",
]


REMOVE_SELECTORS = [
    "nav",
    "footer",
    "header",
    ".menu",
    ".navbar",
    ".footer",
    ".header",
    ".cookie",
    ".popup",
]


def clean_text(
    text: str
) -> str:

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def extract_page_content(
    html: str
):

    soup = BeautifulSoup(
        html,
        "lxml"
    )

    # remove junk tags
    for tag_name in REMOVE_TAGS:

        for tag in soup.find_all(
            tag_name
        ):
            tag.decompose()

    # remove junk UI
    for selector in REMOVE_SELECTORS:

        for tag in soup.select(
            selector
        ):
            tag.decompose()

    title = (
        soup.title.text.strip()
        if soup.title
        else ""
    )

    headings = []

    for h in soup.find_all(
        ["h1", "h2", "h3"]
    ):

        txt = h.get_text(
            " ",
            strip=True
        )

        if len(txt) > 2:
            headings.append(
                txt
            )

    # prioritize meaningful content
    content_areas = soup.find_all(
        [
            "main",
            "article",
            "section",
        ]
    )

    text_parts = []

    for area in content_areas:

        txt = area.get_text(
            " ",
            strip=True
        )

        txt = clean_text(
            txt
        )

        if len(txt) > 100:
            text_parts.append(
                txt
            )

    # fallback
    if not text_parts:

        body = soup.body

        if body:

            txt = body.get_text(
                " ",
                strip=True
            )

            text_parts.append(
                clean_text(txt)
            )

    content = "\n\n".join(
        text_parts
    )

    return {
        "title": title,
        "headings": headings,
        "content": content,
    }