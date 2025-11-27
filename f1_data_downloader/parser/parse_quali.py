# -*- coding: utf-8 -*-
import pymupdf as fitz
import pandas as pd
import re
import logging

from f1_data_downloader.parser.utils import get_image_header

logger = logging.getLogger(__name__)

def parse_quali_final_classification(file: str) -> pd.DataFrame:
    """Parse "Qualifying Session Final Classification" PDF"""
    # Find the page with "Qualifying Session Final Classification"
    doc = fitz.open(file)
    found = []
    page = None
    for i in range(len(doc)):
        page = doc[i]
        if '.pdf' in page.get_text():  # This is the front page. Skip
            continue
        found = page.search_for('Final Classification')
        if found:
            break
        found = page.search_for('Provisional Classification')
        if found:
            logger.warning('Found and using provisional classification, not the final one')
            break
        else:
            found = get_image_header(page)
            if found:
                found = [found]
                break

    if found is None or len(found) == 0:
        raise ValueError(f'not able to find quali. result in `{file}`')

    if page is None:
        raise ValueError(f'not able to find quali. result in `{file}`')

    # Width and height of the page
    w = page.bound()[2]

    # y-position of "Qualifying Final Classification" or "Qualifying Session Provisional Classification"
    y = found[0].y1

    # y-position of "NOT CLASSIFIED - " or "POLE POSITION LAP"
    not_classified = page.search_for('NOT CLASSIFIED - ')
    b = None
    if len(not_classified) > 0:
        b = not_classified[0].y0
    elif len(page.search_for('POLE POSITION LAP')) > 0:
        b = page.search_for('POLE POSITION LAP')[0].y0
    elif len(page.search_for('FASTEST LAP')) > 0:
        b = page.search_for('FASTEST LAP')[0].y0
    elif len(page.search_for('Formula One World Championship')[0]) > 0:
        b = page.search_for('Formula One World Championship')[0].y0
    else:
        raise ValueError(f'not able to find the bottom of quali. result in `{file}`')
    if b is None:
        raise ValueError(f'not able to find the bottom of quali. result in `{file}`')

    # Table bounding box
    bbox = fitz.Rect(0, y, w, b)

    # Dist. between "NAT" and "ENTRANT"
    nat = page.search_for('NAT')[0]
    entrant = page.search_for('ENTRANT')[0]
    snap_x_tolerance = (entrant.x0 - nat.x1) * 1.2  # 20% buffer

    # Parse
    df = page.find_tables(clip=bbox, snap_x_tolerance=snap_x_tolerance)[0].to_pandas()
    first_row = [format_col(c) for c in df.columns]
    # Insert the new column names
    if len(df.columns) == 14:
        df.columns = ['_', 'no', 'driver', 'nat', 'entrant', 'q1', 'q1_laps', 'q1_time', 'q2',
                          'q2_laps', 'q2_time', 'q3', 'q3_laps', 'q3_time']
    elif len(df.columns) == 15:
        df.columns = ['_', 'no', 'driver', 'nat', 'entrant', 'q1', 'q1_laps', 'q1_laps_%', 'q1_time', 'q2',
                          'q2_laps', 'q2_time', 'q3', 'q3_laps', 'q3_time']
    df = pd.concat([pd.DataFrame([first_row], columns=df.columns), df], ignore_index=True)
    df.apply(format_long_name_row, axis=1)
    df = df[df['_'] != '']
    df.drop(columns=['_', 'nat'], inplace=True)
    df = df[df['no'] != '']
    return df

# Format the first line elements
def format_col(c: str) -> str:
    if len(c.split("-")) > 1:
        return c.split("-")[1]
    return c

def format_long_name_row(row):
    if row["driver"] is not None:
        return row
    elif row["_"]:
        # In this case the driver name is too long so every info is stacked up in the first cell
        tokens = row["_"].split(" ")

        # Step 1: Extract driver number
        driver_no = int(tokens[1])

        # Step 2: Find index of first ALL CAPS word (surname)
        surname_idx = next(i for i, token in enumerate(tokens[2:], start=2) if token.isupper())
        driver_forename = " ".join(tokens[2:surname_idx])
        driver_surname = str(tokens[surname_idx])

        # Step 3: Find first time-like token (1:16.xxx) to separate entrant and Q1 time
        time_regex = re.compile(r"^\d:\d{2}\.\d{3}$")
        time_idx = next(i for i, token in enumerate(tokens) if time_regex.match(token))

        entrant = " ".join(tokens[surname_idx + 1:time_idx])

        # Step 4: From time_idx forward, parse Q1, Q2, Q3 sets
        remaining = tokens[time_idx:]
        phases = []
        i = 0
        while i + 2 < len(remaining):
            if time_regex.match(remaining[i]):
                time_val = remaining[i]
                laps_val = remaining[i + 1]
                timestamp_val = remaining[i + 2]


                if len(row) == 15:
                    phases.append((time_val, laps_val, timestamp_val, remaining[i + 3]))
                    i += 1
                else:
                    phases.append((time_val, laps_val, timestamp_val))
                i += 3
            else:
                break

        # Pad missing Q2/Q3 with empty strings
        while len(phases) < 3:
            phases.append(("", "", ""))

        row["no"] = driver_no
        row["driver"] = " ".join([driver_forename, driver_surname])
        row["entrant"] = entrant
        row["q1"] = phases[0][0]
        row["q1_laps"] = phases[0][1]

        if len(row) == 15:
            row["q1_laps_%"] = phases[0][2]
            row["q1_time"] = phases[0][3]
        else:
            row["q1_time"] = phases[0][2]

        row["q2"] = phases[1][0]
        row["q2_laps"] = phases[1][1]
        row["q2_time"] = phases[1][2]
        row["q3"] = phases[2][0]
        row["q3_laps"] = phases[2][1]
        row["q3_time"] = phases[2][2]

        return row
