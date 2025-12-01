from re import sub
from urllib.request import urlopen
from bs4 import BeautifulSoup
from bs4.element import Tag
import requests
import pandas as pd

from pathlib import Path
import logging
import json
import sys
import traceback

from f1_data_downloader.parser.parse_quali import parse_quali_final_classification
from f1_data_downloader.parser.parse_driver_championship import parse_driver_championship
from f1_data_downloader.parser.parse_constructor_championship import parse_constructor_championship
from f1_data_downloader.parser.parse_race_classification import parse_race_final_classification
from f1_data_downloader.parser.parse_race_history_chart import parse_race_history_chart
from f1_data_downloader.parser.parse_race_lap_chart import parse_race_lap_chart
from f1_data_downloader.parser.parse_race_pit_stops import parse_race_pit_stop
from f1_data_downloader.parser.parse_starting_grid import parse_starting_grid

from f1_data_downloader.parser.parse_sprint_history_chart import parse_sprint_history_chart
from f1_data_downloader.parser.parse_sprint_classification import parse_sprint_final_classification
from f1_data_downloader.parser.parse_sprint_lap_chart import parse_sprint_lap_chart

base = "https://www.fia.com"
events_endpoint = "/events/fia-formula-one-world-championship"
decision_documents_endpoint = "/system/files/decision-document"

decision_documents_files = [
    {
        "pdf_filename": "race_classification",
        "fia_filename": "final_race_classification"
    },
    {
        "pdf_filename": "quali_classification",
        "fia_filename": "final_qualifying_classification"
    },
    {
        "pdf_filename": "starting_grid",
        "fia_filename": "final_starting_grid",
    }
]

events_titles = {
    "RACE": {
        "race_lap_chart": [
            "Race Lap Chart",
            "Lap Chart"
        ],
        "drivers_championship": [
            "Drivers Championship",
            "Drivers' Championship"
        ],
        "constructors_championship": [
            "Constructors Championship",
            "Drivers' Championship  Constructors Championship"
        ],
        "race_pit_stops": [
            "Race Pit Stop Summary",
            "Pit Stop Summary"
        ],
        "race_history_chart": [
            "History Chart"
        ]
    },
    "SPRINT RACE": {
        "sprint_classification": ["Provisional Classification", "Sprint Provisional Classification", "Classification"],
        "sprint_lap_chart": ["Sprint Lap Chart", "Lap Chart"],
        "sprint_history_chart": [
            "History Chart",
            "Sprint History Chart"
        ]
    }
}

entrant_id_mapping = {
    "Oracle Red Bull Racing": 9,
    "McLaren Formula 1 Team": 1,
    "Mercedes-AMG PETRONAS F1 Team": 131,
    "Aston Martin Aramco F1 Team": 117,
    "Scuderia Ferrari HP": 6,
    "Atlassian Williams Racing": 3,
    "BWT Alpine F1 Team": 214,
    "MoneyGram Haas F1 Team": 210,
    "Visa Cash App Racing Bulls F1 Team": 215,
    "Stake F1 Team Kick Sauber": 15,
    "Kick Sauber F1 Team": 15,
}

driver_mapping = {
    "L. NORRIS": 846,
    "M. VERSTAPPEN": 830,
    "G. RUSSELL": 847,
    "I. HADJAR": 863,
    "A. ALBON": 848,
    "L. STROLL": 840,
    "N. HULKENBERG": 807,
    "C. LECLERC": 844,
    "O. PIASTRI": 857,
    "L. HAMILTON": 1,
    "P. GASLY": 842,
    "Y. TSUNODA": 852,
    "E. OCON": 839,
    "O. BEARMAN": 860,
    "L. LAWSON": 859,
    "K. ANTONELLI": 864,
    "F. ALONSO": 4,
    "C. SAINZ": 832,
    "J. DOOHAN": 862,
    "G. BORTOLETO": 865,
    "F. COLAPINTO": 861,
}

driver_no_mapping = {
    4: 846,
    1: 830,
    63: 847,
    6: 863,
    23: 848,
    18: 840,
    27: 807,
    16: 844,
    81: 857,
    44: 1,
    10: 842,
    22: 852,
    31: 839,
    87: 860,
    30: 859,
    12: 864,
    14: 4,
    55: 832,
    7: 862,
    5: 865,
    43: 861,
}

logger = logging.getLogger(__name__)

def download_files(year: int, kebab_race_name: str, snake_race_name: str, is_sprint: bool):
    # Format the key to the following format:
    # year_round_country
    # Note: the round is a 2 digit number
    complete_url = base + events_endpoint + f"/season-{year}/{kebab_race_name}/eventtiming-information"
    logger.info("Event timing url: %s", complete_url)
    page = urlopen(complete_url)
    html = page.read().decode("utf-8")
    soup = BeautifulSoup(html, "html.parser")

    # Select the div.content > div.middle
    content = soup.find("div", class_="content")

    if not isinstance(content, Tag):
        logger.error("content not found")
        exit(1)

    middle = content.find("div", class_="middle")

    if not isinstance(middle, Tag):
        logger.error("middle not found")
        exit(1)

    files_url = {
        "RACE": [],
        "SPRINT RACE": [],
    }
    current_header = ""

    for div in middle.findChildren():
        if not isinstance(div, Tag):
            continue

        b_tag = div.find("b")
        strong_tag = div.find("strong")

        if div.name == "p":
            if b_tag is not None:
                current_header = ""

                for header in files_url:
                    if header == b_tag.getText(strip=True):
                        current_header = header
                        break
            elif strong_tag is not None:
                current_header = ""

                for header in files_url:
                    if header == strong_tag.getText(strip=True):
                        current_header = header
                        break

        classes = div.get("class")

        if current_header == "":
            continue

        if classes is None or classes[0] != 'for-documents':
            continue

        a = div.find("a")

        if not isinstance(a, Tag):
            logger.error("a tag not found")
            exit(1)

        title_div = div.find("div", class_="title")

        if not isinstance(title_div, Tag):
            logger.error("title_div not found")
            exit(1)

        url = a.get("href")
        title = title_div.text

        logger.info(f"Found: {current_header} - {title}")
        files_url[current_header].append((title, url))

    logger.info("----- Files found -----")

    decision_document_complete_url = base + decision_documents_endpoint + f"/{year}_{snake_race_name}_-_"
    for file in decision_documents_files:
        dl_url = decision_document_complete_url + file.get("fia_filename", "") + ".pdf"
        filename = file.get("pdf_filename", "")

        logger.info(f"Downloading: {dl_url} to {filename}.pdf")

        resp = requests.get(dl_url)

        if resp.status_code != 200:
            logger.error(f"could not download: {dl_url} - {resp.status_code}")
            exit(1)

        filepath = Path(f"data/{filename}.pdf")
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(resp.content)        

    for header in files_url:
        for files in files_url[header]:
            fn = None

            for f in events_titles[header]:
                if files[0] in events_titles[header][f]:
                    fn = f
                    break

            if fn is None:
                logger.info(f"Skipping: {files[0]}")
                continue

            dl_url = files[1]

            logger.info(f"Downloading: {dl_url} to {fn}.pdf")

            resp = requests.get(dl_url)

            if resp.status_code != 200:
                logger.error(f"could not download: {dl_url} - {resp.status_code}")
                exit(1)

            filepath = Path(f"data/{fn}.pdf")
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_bytes(resp.content)

def create_constructor_results():
    data = parse_race_final_classification("data/race_classification.pdf")
    data['constructor_id'] = data['entrant'].map(lambda x: entrant_id_mapping.get(x)).astype(int)
    data = data[['constructor_id', 'points']]
    data['points'] = data['points'].astype('Int64')
    result = data.groupby("constructor_id", as_index=False)["points"].sum()
    result.to_csv("csv/constructor_results.csv", index=False)

    logger.info("----- CSV file created for constructor results -----")

def create_constructor_standings():
    data = parse_constructor_championship("data/constructors_championship.pdf")
    data['position'] = data['pos']
    data['position_text'] = data['pos']
    data['points'] = data['total']
    data['constructor_id'] = data['entrant'].map(lambda x: entrant_id_mapping.get(x)).astype(int)

    data = data[['constructor_id', 'points', 'position', 'position_text', 'wins']]

    data.to_csv("csv/constructor_standings.csv", index=False)

    logger.info("----- CSV file created for constructor standings -----")

def to_ms_safe(t: str):
    if pd.isna(t) or t == "" or t is None:
        return None
    t_str = str(t).strip()
    # If it has 0 colon, assume SS.sss    → prepend 0:0:
    # If it has 1 colon, assume MM:SS.sss → prepend 0:
    if t_str.count(":") == 0:
        t_str = "0:0:" + t_str
    elif t_str.count(":") == 1:
        t_str = "0:" + t_str
        
    td = pd.to_timedelta(t_str, errors="coerce")
    return None if pd.isna(td) else int(td.total_seconds()) * 1000

def create_results():
    data = parse_race_final_classification("data/race_classification.pdf")
    grid_data = parse_starting_grid("data/starting_grid.pdf")

    data = data.reset_index(drop=True)
    data['driver_id'] = data['driver_no'].map(lambda x: driver_no_mapping.get(int(x)))
    data['driver_number'] = data['driver_no'].astype(int)
    data['constructor_id'] = data['entrant'].map(lambda x: entrant_id_mapping.get(x)).astype(int)
    data['position'] = data.index + 1

    data['position_text'] = data['position'].astype(str)
    is_dnf = data["gap"].astype(str).str.strip().eq("DNF")
    data.loc[is_dnf, "position_text"] = "R"

    data['position_order'] = data['position']
    data["milliseconds"] = data['time'].apply(to_ms_safe).astype('Int64')
    data.loc[1:, "time"] = data.loc[1:, "gap"]

    data['fastest_lap'] = data['on']
    data['fastest_lap_time'] = data['fastest']
    data['fastest_lap_speed'] = data['km/h']
    data['fastest_ms'] = data['fastest'].apply(to_ms_safe)
    data['rank'] = data["fastest_ms"].rank(method="min", ascending=True).astype('Int64')

    data = data[[
        'driver_id',
        'constructor_id',
        'driver_number',
        'position',
        'position_text',
        'position_order',
        'points',
        'laps',
        'time',
        'milliseconds',
        'fastest_lap',
        'fastest_lap_time',
        'rank',
        'fastest_lap_speed',
    ]]

    grid_data = grid_data.reset_index().rename(columns={"index": "grid"})
    grid_data['grid'] = grid_data['grid'] + 1

    data = data.merge(grid_data[['car', 'grid']], left_on='driver_number', right_on='car', how='left').drop(columns=['car'])

    data.to_csv("csv/results.csv", index=False)

    logger.info("----- CSV file created for results -----")

def create_driver_standings():
    data = parse_driver_championship("data/drivers_championship.pdf")

    data = data.reset_index(drop=True)
    data['points'] = data['total']
    data['driver_id'] = data['driver'].map(lambda x: driver_mapping.get(x))
    data['position'] = data.index + 1
    data['position_text'] = data['position']
   
    data = data[[
        'driver_id',
        'points',
        'position',
        'position_text',
        'wins'
    ]]

    data.to_csv("csv/driver_standings.csv", index=False)
    logger.info("----- CSV file created for driver standings -----")


def create_lap_times(is_sprint: bool):
    data = parse_race_history_chart("data/race_history_chart.pdf")
    data = data.reset_index(drop=True)

    data['driver_id'] = data['driver_no'].map(lambda x: driver_no_mapping.get(int(x)))
    data['milliseconds'] = data['time'].apply(to_ms_safe).astype('Int64')

    data = data[[
        'driver_id',
        'lap',
        'position',
        'time',
        'milliseconds'
    ]]

    data.to_csv("csv/lap_times.csv", index=False)
    logger.info("----- CSV file created for lap times -----")

def create_pit_stops():
    data = parse_race_pit_stop("data/race_pit_stops.pdf")
    data = data.reset_index(drop=True)

    data['driver_id'] = data['driver_no'].map(lambda x: driver_no_mapping.get(int(x)))
    data['stop'] = data['no']
    data['time'] = data['local_time']
    data['milliseconds'] = data['duration'].apply(to_ms_safe).astype('Int64')

    data = data[[
        'driver_id',
        'stop',
        'lap',
        'time',
        'duration',
        'milliseconds'
    ]]

    data.to_csv("csv/pit_stops.csv", index=False)
    logger.info("----- CSV file created for pit stops -----")

def create_qualifying():
    data = parse_quali_final_classification("data/quali_classification.pdf")
    data = data.reset_index(drop=True)

    data['driver_id'] = data['no'].map(lambda x: driver_no_mapping.get(int(x)))
    data['constructor_id'] = data['entrant'].map(lambda x: entrant_id_mapping.get(x)).astype('Int64')
    data['number'] = data['no']
    data['position'] = data.index + 1

    data = data[[
        'driver_id',
        'constructor_id',
        'number',
        'position',
        'q1',
        'q2',
        'q3'
    ]]

    data.to_csv("csv/qualifying.csv", index=False)
    logger.info("----- CSV file created for qualifying -----")

def create_sprint_results():
    data = parse_sprint_final_classification("data/sprint_classification.pdf")
    
    data = data.reset_index(drop=True)
    data['driver_id'] = data['driver_no'].map(lambda x: driver_no_mapping.get(int(x)))
    data['constructor_id'] = data['entrant'].map(lambda x: entrant_id_mapping.get(x))
    data['position'] = data.index + 1

    data['position_text'] = data['position']
    is_dnf = data["gap"].astype(str).str.strip().eq("DNF")
    data.loc[is_dnf, "position_text"] = "R"

    data['position_order'] = data['position']
    data["milliseconds"] = data['time'].apply(to_ms_safe).astype('Int64')
    data.loc[1:, "time"] = data.loc[1:, "gap"]

    data['fastest_lap'] = data['on']
    data['fastest_lap_time'] = data['fastest']

    data = data[[
        'driver_id',
        'constructor_id',
        'driver_no',
        'position',
        'position_text',
        'position_order',
        'points',
        'laps',
        'time',
        'milliseconds',
        'fastest_lap',
        'fastest_lap_time',
    ]]

    data.to_csv("csv/sprint_results.csv", index=False)

    logger.info("----- CSV file created for sprint results -----")


def create_sprint_classification():
    data = parse_sprint_final_classification("data/sprint_classification.pdf")
    data.to_csv("csv/sprint_classification.csv", index=False)

    logger.info("----- CSV file created for sprint classification -----")
    return

def snake_case(s: str) -> str:
    return '_'.join(
        sub('([A-Z][a-z]+)', r' \1',
        sub('([A-Z]+)', r' \1',
        s.replace('-', ' '))).split()).lower()

def kebab_case(s: str) -> str:
  return '-'.join(
    sub(r"(\s|_|-)+"," ",
    sub(r"[A-Z]{2,}(?=[A-Z][a-z]+[0-9]*|\b)|[A-Z]?[a-z]+[0-9]*|[A-Z]|[0-9]+",
    lambda mo: ' ' + mo.group(0).lower(), s)).split())


if __name__ == "__main__":
    # Configure logger
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
    # Get season, race_name and is_sprint from stdin
    season = sys.argv[1]
    race_name = sys.argv[2]

    # Load grand prix file and change race name to FIA race name
    with open('grand_prix.json', 'r') as gp_file:
        gp = json.load(gp_file)
        if race_name in gp:
            race_name = gp[race_name]
        else:
            logger.warning("unable to find key %s in grand prix list", sys.argv[2])
            logger.warning("trying to perform action still...")

    # Transform race name to kebab case and snake case
    snake_race_name = snake_case(race_name)
    kebab_race_name = kebab_case(race_name)

    is_sprint = sys.argv[3] == "true"

    try :
        download_files(int(season), kebab_race_name, snake_race_name, is_sprint)

        logger.info("----- Parsing file -----")

        # Ensures csv folder exists
        filepath = Path(f"csv")
        filepath.mkdir(parents=True, exist_ok=True)

        create_constructor_results()
        create_constructor_standings()
        create_results()
        create_driver_standings()
        create_lap_times(is_sprint)
        create_pit_stops()
        create_qualifying()

        if is_sprint:
            logger.info("----- Handling sprint weekend -----")
            
    except Exception as e:
        logger.error(e)
        logger.error(traceback.format_exc()) 
        exit(1)
