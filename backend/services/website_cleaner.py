import re


JUNK_PATTERNS = [
    r"Book a Call",
    r"Contact our Experts",
    r"Enter Captcha",
    r"Submit",
    r"Talk to our experts",
    r"Get in touch!",
    r"Schedule a Discovery Session",
    r"Download Sample App Development Agreement",
    r"Your Name \*",
    r"Email \*",
    r"Phone Number \*",
    r"Describe your project \*",
    r"Upload Resume.*",
    r"Position Applied For.*",
]


MIN_PARAGRAPH_LENGTH = 50


def normalize_text(
    text: str
) -> str:

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def is_junk(
    paragraph: str
) -> bool:

    if len(
        paragraph.strip()
    ) < MIN_PARAGRAPH_LENGTH:
        return True

    for pattern in JUNK_PATTERNS:

        if re.search(
            pattern,
            paragraph,
            re.IGNORECASE
        ):
            return True

    return False


def clean_content(
    text: str
) -> str:

    paragraphs = re.split(
        r"\.\s+|\n+",
        text
    )

    seen = set()

    cleaned = []

    for para in paragraphs:

        para = normalize_text(
            para
        )

        if not para:
            continue

        if is_junk(
            para
        ):
            continue

        normalized = (
            para.lower()
        )

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        cleaned.append(
            para
        )

    return "\n\n".join(
        cleaned
    )