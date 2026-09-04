import pandas as pd
import re
import json

from utils.web_parsing_utils import get_bs_html
from wikidata_functions.wikidata_get_info import get_rider_wikidata_id, get_stage_wikidata_id, get_team_wikidata_id

BASE_PCS_URL = "https://www.procyclingstats.com/"

PROFILES = {
    "icon profile p1 mg_rp4": "Flat",
    "icon profile p2 mg_rp4": "Hills, flat finish",
    "icon profile p3 mg_rp4": "Hills, uphill finish",
    "icon profile p4 mg_rp4": "Mountains, flat finish",
    "icon profile p5 mg_rp4": "Mountains, uphill finish",
}

pcs_id_cache = "pcs_parsing/pcs_id_rider_cache.json"

def fetch_stage_links(year):
    url = f"{BASE_PCS_URL}race/tour-de-france/{year}/route/stages"
    html_content = get_bs_html(url)

    raw_stage_links = html_content.find_all("option")
    parsed_stage_links = [tag['value'] for tag in raw_stage_links if str(year) in tag['value'] and "stage-" in tag['value']]
    return parsed_stage_links

def create_stage_fetch_urls(year):
    stages_links = fetch_stage_links(year)
    stage_urls = [f"{BASE_PCS_URL}{link}" for link in stages_links]

    return stage_urls

def parse_html_for_metadata(html_content):
    # Parse metadata
    info_dict = {}
    profile_class = None
    info_list = html_content.find("ul", class_="keyvalueList")
    if info_list:
        for li in info_list.find_all("li"):
            title_div = li.find("div", class_="title")
            value_div = li.find("div", class_="value")
            if title_div and value_div:
                key = title_div.get_text(strip=True).rstrip(":")

                # Special handling for "Parcours type" to extract the profile class
                if key == "Parcours type":
                    span_tag = value_div.find("span")
                    if span_tag and span_tag.has_attr("class"):
                        # Returns a string like "icon profile p1 mg_rp4"
                        profile_class = " ".join(span_tag["class"])
                else:
                    info_dict[key] = value_div.get_text(strip=True)

    info_dict['stage_pcs_id'] = html_content.find("input", {"name": "race_id"})['value']
    return info_dict, profile_class

def parse_detailed_key_events(key_events):
    detailed_key_events = []
    for link in key_events:
        full_url = f"{BASE_PCS_URL}{link}"
        html_content = get_bs_html(full_url)
        event_div = html_content.find("div", class_=lambda c: c and "keyeventcont" in c.lower())

        if event_div:
            # get_text strips nested HTML tags and normalizes spaces/non-breaking spaces
            key_event_text = event_div.get_text(separator=" ", strip=True)
            detailed_key_events.append(key_event_text)
    return detailed_key_events

def parse_html_for_key_events(html_content):
    key_events = []
    key_events_links = []

    key_events_section = html_content.find("h4", string=lambda t: t and "Key events" in t)

    if key_events_section:
        events_ul = key_events_section.find_next_sibling("ul")
        if events_ul:
            for li in events_ul.find_all("li"):
                a_tag = li.find("a")
                if a_tag:
                    key_events.append(a_tag.get_text(strip=True))
                    key_events_links.append(a_tag.get("href", ""))

    return key_events, parse_detailed_key_events(key_events_links)

def fetch_stage_metadata(html_content, stage_number, tdf_year):
    stage_metadata = {}

    info_dict, profile_class = parse_html_for_metadata(html_content)
    key_events, detailed_key_events = parse_html_for_key_events(html_content)

    stage_metadata["stage_number"] = stage_number
    stage_metadata["stage_pcs_id"] = info_dict['stage_pcs_id']
    stage_metadata["stage_wikidata_id"] = get_stage_wikidata_id(stage_number, tdf_year)
    stage_metadata["date"] = info_dict.get("Date", "")
    stage_metadata["distance"] = info_dict.get("Distance", "")
    stage_metadata["profile"] = PROFILES[profile_class] if profile_class in PROFILES else ""
    stage_metadata["vert_meters"] = info_dict.get("Vertical meters", "")
    stage_metadata["start_location"] = info_dict.get("Departure", "")
    stage_metadata["finish_location"] = info_dict.get("Arrival", "")
    stage_metadata['description'] = html_content.find("meta", attrs={"name": "description"}).get('content')
    stage_metadata["avg_speed"] = info_dict.get("Avg. speed winner", "")
    
    stage_metadata["won_how"] = info_dict.get("Won how", "")
    stage_metadata["key_events"] = key_events
    stage_metadata["detailed_key_events"] = detailed_key_events
    
    return stage_metadata

def fetch_rider_pcs_id(rider_url):
    with open(pcs_id_cache, 'r', encoding='utf-8') as f:
        pcs_ids = json.load(f)

    if rider_url in pcs_ids:
        return pcs_ids[rider_url]

    full_url = f"{BASE_PCS_URL}{rider_url}/statistics/overview"
    html_content = get_bs_html(full_url)
    
    rider_id_tag = html_content.find("div", class_="mt40 ar")
    if rider_id_tag:
        pcs_ids[rider_url] = rider_id_tag.get_text(strip=True).split('ID: ')[-1]
    else:
        pcs_ids[rider_url] = None

    with open(pcs_id_cache, 'w', encoding='utf-8') as f:
        json.dump(pcs_ids, f, indent=2)

    return pcs_ids[rider_url]

def fetch_stage_results(html_content, tdf_year: int):
    wanted_results = ['stage', 'gc', 'points', 'temp', 'teams']
    results_counter = -1
    parsed_results = {}
    yellow_jersey_holder_wikidata_id = None

    # Target rows inside the results table
    rows = html_content.select("table.results tbody tr")
    for row in rows:
        if row.find('td').get_text(strip=True) == str(1):
            results_counter += 1
            if results_counter >= len(wanted_results):
                break
            parsed_results[wanted_results[results_counter]] = []

        if results_counter == 3:
            continue
        if results_counter == 4:
            # Rank & Delta
            rnk = row.find("td", class_=None).get_text(strip=True) if row.find("td", class_=None) else None
            delta_td = row.find("span", class_=re.compile(r"delta-")).get_text(strip=True) if row.find("span", class_=re.compile(r"delta-")) else None

            # Team & Class
            team = row.find("a").get_text(strip=True) if row.find("a") else None
            team_class = row.find_all("td", class_=None)[2].get_text(strip=True) if len(row.find_all("td", class_=None)) > 1 else None
            team_url = row.find("a")["href"] if row.find("a") else None
            team_wiki_id = get_team_wikidata_id(team, tdf_year)

            # Time
            time = row.find("span", class_="hide").get_text(strip=True) if row.find("span", class_="hide") else None

            full_results = {
                "Rnk": rnk,
                "Delta": delta_td,
                "Team": team,
                "Class": team_class,
                "Time": time,
                "Team_URL": team_url,
                "Team Wiki ID": team_wiki_id,
            }
                        
            parsed_results[wanted_results[results_counter]].append(full_results)
        else:                
            # 1. Rank & GC info
            rnk = row.find("td", class_=None).get_text(strip=True) if row.find("td", class_=None) else None
            gc_td = row.find("td", class_="fs11 clr666")
            gc_rank = gc_td.get_text(strip=True) if gc_td else None

            # 2. Bib & Age
            bib = row.find("td", class_="bibs").get_text(strip=True) if row.find("td", class_="bibs") else None
            age = row.find("td", class_="age").get_text(strip=True) if row.find("td", class_="age") else None

            # 3. Specialty
            specialty_span = row.select_one("td.specialty span")
            specialty = specialty_span.get_text(strip=True) if specialty_span else None

            # 4. Rider Name & Country
            rider_a = row.select_one("td.ridername a")
            last_name = rider_a.find("span", class_="uppercase").get_text(strip=True)
            first_name = rider_a.get_text(strip=True).replace(last_name, "").strip()
            # Reconstruct as "Firstname Lastname" with proper space
            rider_name = f"{first_name} {last_name}"
            rider_url = rider_a["href"] if rider_a else None
            rider_pcs_id = fetch_rider_pcs_id(rider_url) if rider_url else None
            rider_wikidata_id = get_rider_wikidata_id(rider_pcs_id)
            if row.find("span", class_=['svg_shirt', 'mx4'], attrs={'data-color': 'yellow'}) is not None:
                yellow_jersey_holder_wikidata_id = rider_wikidata_id

            flag_span = row.select_one("td.ridername span.flag")
            # Country code from flag class (e.g., 'flag fr' -> 'fr')
            country = flag_span["class"][-1].upper() if flag_span and len(flag_span["class"]) > 1 else None

            # 5. Team
            team_a = row.select_one("td.cu600 a")
            team_name = team_a.get_text(strip=True) if team_a else None
            team_wiki_id = get_team_wikidata_id(team_name, tdf_year)

            # 6. Bonus
            bonis = row.find("td", class_="ar cu600").get_text(strip=True) if row.find("td", class_="ar cu600") else None

            # 7. Time Handling
            time_td = row.find("td", class_="time ar")
            time_display = time_td.find("font").get_text(strip=True) if time_td and time_td.find("font") else None

            # Extra handling
            pnt = row.find_all("td", attrs={"class": None})[1].get_text(strip=True) if results_counter == 2 else None
            if row.find("span", class_=re.compile(r"delta-")) is not None:
                delta_pos = row.find("span", class_=re.compile(r"delta-")).get_text(strip=True) if results_counter in [1,2] else None
            else:
                delta_pos = "-"

            full_results = {
                "Rnk": rnk,
                "Rnk_Delta": delta_pos,
                "GC": gc_rank,
                "BIB": bib,
                "Specialty": specialty,
                "Age": age,
                "Rider": rider_name,
                "Country": country,
                "Team": team_name,
                "Team Wiki ID": team_wiki_id,
                "Bonus": bonis,
                "Pnt": pnt,
                "Time_Display": time_display,
                "Rider_URL": rider_url,
                "Rider_PCS_ID": rider_pcs_id,
                "Rider_Wikidata_ID": rider_wikidata_id
            }

            if results_counter == 0:
                full_results.pop("Pnt")
                full_results.pop("Rnk_Delta")
            if results_counter == 1:
                full_results.pop("GC")
                full_results.pop("Pnt")
            if results_counter == 2:
                full_results.pop("GC")
                full_results.pop("Bonus")
                full_results.pop("Time_Display")

            parsed_results[wanted_results[results_counter]].append(full_results)

    # Convert to DataFrame
    df_results = {}
    for result in parsed_results.keys():
        df_results[result] = pd.DataFrame(parsed_results[result])

    return df_results, yellow_jersey_holder_wikidata_id


def fetch_full_stage_data(stage_url, stage_number, tdf_year):
    html_content = get_bs_html(stage_url)
    stage_leaderboards, yellow_jersey_holder_wikidata_id = fetch_stage_results(html_content, tdf_year)

    stage_metadata = fetch_stage_metadata(html_content, stage_number, tdf_year)
    stage_metadata['yellow_jersey_holder_wikidata_id'] = yellow_jersey_holder_wikidata_id
    
    stage_data = {
            'stage_general_info': stage_metadata,
            'stage_results': stage_leaderboards['stage'],
            'gc_results': stage_leaderboards['gc'],
            'points_results': stage_leaderboards['points'],
            'teams_results': stage_leaderboards['teams'],
            }

    return stage_data