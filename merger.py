from collections import Counter


def _build_boilerplate(all_lines: list[list[str]], threshold: float = 0.6) -> set[str]:
    total = len(all_lines)
    counter = Counter()
    for lines in all_lines:
        for line in set(lines):
            if line.strip():
                counter[line] += 1
    return {line for line, count in counter.items() if count / total >= threshold}


def _split(lines: list[str], boilerplate: set[str]) -> tuple[list[str], list[str], list[str]]:
    """Split lines into (header, body, footer)."""

    # Header: before the first H1 heading
    h1_idx = next((i for i, l in enumerate(lines) if l.startswith("# ")), 0)

    # Footer: try known footer marker first, then boilerplate scan from bottom
    footer_idx = next(
        (i for i in range(h1_idx, len(lines)) if lines[i] == "YesNo"),
        None,
    )
    if footer_idx is None:
        i = len(lines) - 1
        while i > h1_idx:
            if not lines[i].strip():
                i -= 1
            elif lines[i] in boilerplate:
                footer_idx = i
                i -= 1
            else:
                break
        if footer_idx is None:
            footer_idx = len(lines)

    return lines[:h1_idx], lines[h1_idx:footer_idx], lines[footer_idx:]


def merge(pages: list[tuple[str, str]], threshold: float = 0.6) -> str:
    """
    Combine multiple scraped pages into one document.
    - One shared header (from the first file)
    - Each page's body with a source comment
    - One shared footer (from the first file)

    Args:
        pages: list of (url, markdown_text)
        threshold: fraction of files a line must appear in to be considered boilerplate
    """
    if not pages:
        return ""
    if len(pages) == 1:
        return pages[0][1]

    all_lines = [text.splitlines() for _, text in pages]
    boilerplate = _build_boilerplate(all_lines, threshold)

    # Use the first non-trivial file for header/footer extraction
    ref_lines = next(
        (lines for lines in all_lines if len(lines) > 10),
        all_lines[0],
    )
    header_lines, _, footer_lines = _split(ref_lines, boilerplate)

    header = "\n".join(header_lines).strip()
    footer = "\n".join(footer_lines).strip()

    # Collect bodies
    bodies: list[tuple[str, str]] = []
    for (url, _), lines in zip(pages, all_lines):
        _, body_lines, _ = _split(lines, boilerplate)
        body = "\n".join(body_lines).strip()
        if body:
            bodies.append((url, body))

    # Assemble
    parts: list[str] = []
    if header:
        parts.append(header)
    for url, body in bodies:
        parts.append(f"<!-- source: {url} -->\n\n{body}")
    if footer:
        parts.append(footer)

    return "\n\n---\n\n".join(parts) + "\n"
