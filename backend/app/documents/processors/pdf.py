import io
import fitz  # PyMuPDF


def extract_text(file_bytes: bytes) -> str:
    """
    Extract text from a PDF, page by page, using PyMuPDF.
    Pages are separated by double newlines so the chunker can respect
    paragraph boundaries.
    """
    parts = []
    with fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf") as doc:
        for page in doc:
            text = page.get_text("text")
            if text and text.strip():
                parts.append(text.strip())
    return "\n\n".join(parts)


def extract_pages(file_bytes: bytes) -> list[tuple[int, str]]:
    """
    Extract text page by page, returning a list of (page_number, text) tuples.
    page_number is 1-based.
    Used by the document indexer to record page_number in chunk metadata.
    """
    pages = []
    with fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf") as doc:
        for page_index, page in enumerate(doc):
            text = page.get_text("text")
            if text and text.strip():
                pages.append((page_index + 1, text.strip()))
    return pages


def extract_structured(file_bytes: bytes) -> list[dict]:
    """
    Extract text and tables from a PDF as a typed segment list.

    Returns a list of dicts:
        {"text": str, "source": "text" | "table", "page_number": int}

    For each page:
      - Detect native tables via page.find_tables()
      - Convert each table to Markdown via pandas + tabulate
      - Extract remaining non-table text using block-level bbox filtering
      - Skip empty segments
    """
    import pandas as pd

    results = []
    with fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf") as doc:
        for page_index, page in enumerate(doc):
            page_number = page_index + 1
            table_rects = []

            # --- Tables ---
            tables = page.find_tables()
            for table in tables.tables:
                table_rect = fitz.Rect(table.bbox)
                table_rects.append(table_rect)

                cells = table.extract()
                if not cells:
                    continue

                # Replace None with empty string (merged cells)
                cells = [[c if c is not None else "" for c in row] for row in cells]

                try:
                    df = pd.DataFrame(cells[1:], columns=cells[0])
                except Exception:
                    df = pd.DataFrame(cells)

                md = df.to_markdown(index=False, tablefmt="pipe")
                if md and md.strip():
                    results.append({
                        "text": md.strip(),
                        "source": "table",
                        "page_number": page_number,
                    })

            # --- Non-table text ---
            blocks = page.get_text("blocks")  # (x0,y0,x1,y1,text,block_no,block_type)
            text_parts = []
            for block in blocks:
                if block[6] != 0:  # skip image blocks
                    continue
                block_rect = fitz.Rect(block[:4])
                if any(block_rect.intersects(tr) for tr in table_rects):
                    continue  # skip text inside table bboxes
                if block[4].strip():
                    text_parts.append(block[4].strip())

            if text_parts:
                results.append({
                    "text": "\n".join(text_parts),
                    "source": "text",
                    "page_number": page_number,
                })

    return results
