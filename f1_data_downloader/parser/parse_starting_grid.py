import fitz
import pandas as pd
import re


def parse_starting_grid(pdf_path: str) -> pd.DataFrame:
    """
    Parse an FIA starting grid PDF into a pandas DataFrame.

    Returned DataFrame columns:
        - position (int or None for pit lane)
        - car (int)
        - driver (str)
        - pit_lane (bool)

    Parameters
    ----------
    pdf_path : str
        Path to the FIA PDF document.

    Returns
    -------
    pd.DataFrame
    """

    blocks = load_blocks(pdf_path)
    lines = clean_blocks(blocks)

    grid = parse_grid(lines)
    pit = parse_pit_lane(lines)

    df = pd.DataFrame(grid + pit)

    # Sort by grid position (pit lane at bottom)
    df = df.sort_values(
        by=["pit_lane", "position"],
        ascending=[True, True],
        na_position="last"
    ).reset_index(drop=True)

    return df

# -------------------------------------------------------
# Helpers
# -------------------------------------------------------

def load_blocks(path):
    doc = fitz.open(path)
    blocks = []
    for page in doc:
        for b in page.get_text("blocks"):
            blocks.append(b[4])  # block text
    return blocks

def clean_blocks(blocks):
    cleaned = []
    for b in blocks:
        line = " ".join(b.split())
        if line.strip():
            cleaned.append(line)
    return cleaned

def parse_grid(lines):
    grid_regex = re.compile(
        r"\b(\d{1,2})\b\s+(\d{1,3})\s+([A-Z][A-Za-zÀ-ÿ']+(?:\s+[A-Z][A-Za-zÀ-ÿ']+)*)"
    )
    entries = []
    for line in lines:
        m = grid_regex.search(line)
        if m:
            pos, car, driver = m.groups()
            entries.append({
                "position": int(pos),
                "car": int(car),
                "driver": driver.title(),
                "pit_lane": False
            })
    return entries

def parse_pit_lane(lines):
    pit_regex = re.compile(
        r"\b(\d{1,3})\b\s+([A-Z][A-Za-zÀ-ÿ']+(?:\s+[A-Z][A-Za-zÀ-ÿ']+)*)"
    )

    pit_section = False
    entries = []

    for line in lines:
        if "START FROM THE PIT LANE" in line.upper():
            pit_section = True
            continue

        if pit_section:
            # stop on typical end-of-section keywords
            if any(kw in line.upper() for kw in ["PENALT", "DOCUMENT", "COPYRIGHT"]):
                break

            m = pit_regex.search(line)
            if m:
                car, driver = m.groups()
                entries.append({
                    "position": None,
                    "car": int(car),
                    "driver": driver.title(),
                    "pit_lane": True
                })

    return entries

