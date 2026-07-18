import re


def chunk_ucp(text):
    """Split UCP 600 into chunks at the article/sub-clause level.

    Each sub-clause like (a), (b), (c) becomes its own chunk.
    Articles with no sub-clauses are kept as a single chunk.
    Returns a list of dicts: [{id, text, source, ref, corpus}, ...]
    """
    if not text.strip():
        return []

    chunks = []
    seen_ids = {}

    article_pattern = re.compile(r"^(Article\s+(\d+))", re.MULTILINE)
    article_matches = list(article_pattern.finditer(text))

    if not article_matches:
        return []

    def make_id(base):
        # append a counter if the same base id appears more than once
        if base in seen_ids:
            seen_ids[base] += 1
            return f"{base}-{seen_ids[base]}"
        seen_ids[base] = 1
        return base

    for i, match in enumerate(article_matches):
        art_num = match.group(2)
        start = match.start()
        end = article_matches[i + 1].start() if i + 1 < len(article_matches) else len(text)

        article_text = text[start:end].strip()
        title_line = article_text.split("\n", 1)[0].strip()

        # Match sub-clauses like (a), a., a)
        sub_pattern = re.compile(r"^\s*[\(]?([a-z])[\.\)]", re.MULTILINE)
        candidate_matches = list(sub_pattern.finditer(article_text))

        # Only accept clauses that follow the expected a, b, c... sequence.
        # This prevents Roman numerals like (i), (v), (x) from being mistaken
        # for lettered sub-clauses.
        sub_matches = []
        expected = ord("a")
        for m in candidate_matches:
            if ord(m.group(1)) == expected:
                sub_matches.append(m)
                expected += 1

        if sub_matches:
            # Emit any content before the first sub-clause as its own chunk
            # (e.g. Article 2 has definition text before sub-clauses start)
            preamble = article_text[:sub_matches[0].start()].strip()
            preamble_body = preamble[len(title_line):].strip()
            if preamble_body:
                chunks.append({
                    "id": make_id(f"ucp600-art{art_num}"),
                    "text": preamble,
                    "source": "UCP 600",
                    "ref": f"Article {art_num}",
                    "corpus": "ucp",
                })

            for j, sub_match in enumerate(sub_matches):
                letter = sub_match.group(1)
                sub_start = sub_match.start()
                sub_end = sub_matches[j + 1].start() if j + 1 < len(sub_matches) else len(article_text)

                sub_text = article_text[sub_start:sub_end].strip()
                # Include the article title in the chunk so its topic is clear in search
                chunk_text = f"{title_line}\n{sub_text}" if title_line else sub_text

                chunks.append({
                    "id": make_id(f"ucp600-art{art_num}{letter}"),
                    "text": chunk_text,
                    "source": "UCP 600",
                    "ref": f"Article {art_num}({letter})",
                    "corpus": "ucp",
                })
        else:
            chunks.append({
                "id": make_id(f"ucp600-art{art_num}"),
                "text": article_text,
                "source": "UCP 600",
                "ref": f"Article {art_num}",
                "corpus": "ucp",
            })

    return chunks


def chunk_isbp(text):
    """Split ISBP 821 into chunks at the paragraph level.

    Looks for markers like A1., A1), B3., C12. at the start of a line.
    Returns a list of dicts: [{id, text, source, ref, corpus}, ...]
    """
    if not text.strip():
        return []

    chunks = []
    seen_ids = {}

    para_pattern = re.compile(r"^([A-Z]\d+)[\.\)]", re.MULTILINE)
    para_matches = list(para_pattern.finditer(text))

    if not para_matches:
        return []

    for i, match in enumerate(para_matches):
        para_id = match.group(1)
        start = match.start()
        end = para_matches[i + 1].start() if i + 1 < len(para_matches) else len(text)

        para_text = text[start:end].strip()

        base_id = f"isbp821-{para_id}"
        if base_id in seen_ids:
            seen_ids[base_id] += 1
            chunk_id = f"{base_id}-{seen_ids[base_id]}"
        else:
            seen_ids[base_id] = 1
            chunk_id = base_id

        chunks.append({
            "id": chunk_id,
            "text": para_text,
            "source": "ISBP 821",
            "ref": f"Paragraph {para_id}",
            "corpus": "isbp",
        })

    return chunks