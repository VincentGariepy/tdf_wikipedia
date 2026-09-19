import json
import os
import re
from datetime import datetime
from typing import Tuple

import pandas as pd
from tqdm import tqdm
from wikibaseintegrator import WikibaseIntegrator
from wikibaseintegrator.datatypes import Item, Quantity, String, Time
from wikibaseintegrator.wbi_config import config
from wikibaseintegrator.wbi_login import Login
from wikibaseintegrator.wbi_enums import ActionIfExists
from wikibaseintegrator.models import Qualifiers

from pcs_parsing.pcs_stage_parsing import fetch_full_stage_data, create_stage_fetch_urls

QUANTITY_PROPERTIES = {'P1132', 'P1352', 'P1358', 'P2781', 'P2911', 'P3157', 'P7297'}
DATE_PROPERTIES = {'P585'}
JERSEY_IDS = {'Property': 'P2912', 'Jerseys': {'Yellow': 'Q24257871'}}
ITEM_ID_RE = re.compile(r'^Q\d+$')

with open('wikidata_functions/wikidata_properties.json', 'r') as f:
    WIKIDATA_PROPERTIES = json.load(f)

WDUSER = os.getenv('WIKIDATA_BOT_USER')
WDPASS = os.getenv('WIKIDATA_BOT_PASSWORD')

config['USER_AGENT'] = os.getenv('WIKIDATA_USER_AGENT', 'TDF_Wikipedia_Script/1.0')
config['MEDIAWIKI_API_URL'] = 'https://www.wikidata.org/w/api.php'
config['MAX_LAG'] = 30

login_instance = Login(user=WDUSER, password=WDPASS)
wbi = WikibaseIntegrator(login=login_instance)

def time_to_seconds(time_str: str) -> int:
    cleaned_time = re.sub(r"[^0-9:]", "", time_str)
    parts = list(map(int, cleaned_time.split(':')))
    if len(parts) == 3:       # HH:MM:SS
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:     # MM:SS
        return parts[0] * 60 + parts[1]
    return 0

def _to_wikidata_time(value) -> str | None:
    if value is None or value == '':
        return None

    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()

    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%dT%H:%M:%SZ')

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        if re.match(r'^[+-]?\d{4}-\d{2}-\d{2}T', text):
            return text if text.endswith('Z') else text + 'Z'
        if re.match(r'^[+-]?\d{4}-\d{2}-\d{2}$', text):
            return f'{text}T00:00:00Z'
        if re.match(r'^[+-]?\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}', text):
            return text.replace(' ', 'T') + ('Z' if 'Z' not in text and 'T' in text and not text.endswith('Z') else '')

        for fmt in (
            '%d %B %Y', '%d %b %Y', '%d %B %Y %H:%M', '%d %b %Y %H:%M',
            '%d %B %Y %H:%M:%S', '%d %b %Y %H:%M:%S', '%B %d %Y', '%b %d %Y',
            '%Y %B %d', '%Y %b %d'
        ):
            try:
                return datetime.strptime(text, fmt).strftime('%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                continue

    return None


def _parse_numeric_value(value):
    if value is None or value == '':
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None

        match = re.search(r'[-+]?\d+(?:[.,]\d+)?', text)
        if match:
            return float(match.group(0).replace(',', '.'))

    return None


def _make_wb_value(property_id: str, value, is_item: bool = False):
    if value is None or value == '':
        return None

    value_str = str(value).strip()
    if not value_str:
        return None

    if is_item or (isinstance(value, str) and ITEM_ID_RE.fullmatch(value_str)):
        return Item(prop_nr=property_id, value=value_str)

    if property_id in DATE_PROPERTIES:
        wb_time = _to_wikidata_time(value)
        if wb_time is not None:
            return Time(prop_nr=property_id, time=wb_time, precision=11)

    if property_id in QUANTITY_PROPERTIES:
        amount = _parse_numeric_value(value)
        if amount is not None:
            unit = '1'
            if property_id == 'P3157':
                unit = 'http://www.wikidata.org/entity/Q828224'
            elif property_id in {'P2781', 'P2911'}:
                unit = 'http://www.wikidata.org/entity/Q11574'
            elif property_id == 'P7297':
                unit = 'http://www.wikidata.org/entity/Q11573'
            return Quantity(prop_nr=property_id, amount=amount, unit=unit)

    return String(prop_nr=property_id, value=value_str)

def upload_add_property(entity, 
                        property_id: str, 
                        upload_item_str: str = None, 
                        upload_item_property: str = None,
                        qualifier_str: list[Tuple[str, str]] = None,
                        qualifier_property: list[Tuple[str, str]] = None):
    
    if not property_id:
        return entity

    qualifiers = Qualifiers()

    if qualifier_str:
        for q_prop, q_val in qualifier_str:
            if q_prop and q_val is not None and q_val != '':
                qualifiers.add(_make_wb_value(q_prop, q_val))

    if qualifier_property:
        for q_prop, q_val in qualifier_property:
            if q_prop and q_val is not None and q_val != '':
                qualifiers.add(Item(prop_nr=q_prop, value=str(q_val)))

    if upload_item_str is not None:
        claim = _make_wb_value(property_id, upload_item_str)
        if claim is not None:
            claim.qualifiers = qualifiers
            entity.claims.add(claim, action_if_exists=ActionIfExists.FORCE_APPEND)
    elif upload_item_property is not None:
        claim = Item(prop_nr=property_id, value=str(upload_item_property), qualifiers=qualifiers)
        entity.claims.add(claim, action_if_exists=ActionIfExists.FORCE_APPEND)

    return entity

def clear_entity_property(entity, property_id: str):
    if not property_id:
        return entity

    existing_claims = entity.claims.get(property_id)
    for claim in existing_claims:
        claim.remove()  # claim.remove() takes no arguments in WBI v0.12+

    return entity

def upload_single_overwrite_property(entity, 
                                     property_id: str, 
                                     upload_item_str: str = None, 
                                     upload_item_property: str = None,
                                     qualifier_str: list[Tuple[str, str]] = None,
                                     qualifier_property: list[Tuple[str, str]] = None):
    entity = clear_entity_property(entity, property_id)

    return upload_add_property(entity, 
                               property_id, 
                               upload_item_str, 
                               upload_item_property, 
                               qualifier_str, 
                               qualifier_property)

def upload_result_table(entity, 
                        rankings_df: pd.DataFrame, 
                        mapping: dict, 
                        df_type: str, 
                        yellow_jersey_holder_wikidata_id: str):
    """
    Parses ranking DataFrames and converts rows into Wikidata statements + qualifiers.
    """
    main_prop = mapping[list(mapping)[0]]
    if not main_prop or not isinstance(main_prop, str):
        return entity

    entity = clear_entity_property(entity, main_prop)

    if "Time" in rankings_df.columns:
        rankings_df['Time_Display'] = rankings_df['Time']

    if "Time_Display" in rankings_df.columns:
        val = rankings_df.at[1, 'Time_Display']
        if pd.isna(val) or str(val).strip() in (',,', ''):
            rankings_df.at[1, 'Time_Display'] = '0'

        rankings_df['Time_Display'] = rankings_df['Time_Display'].replace(r'^\s*,,?\s*$', None, regex=True).ffill()
    
    for i, row in rankings_df.iterrows():
        qualifier_str = []
        qualifier_prop = []
        
        # Handle stage winner time vs gap times
        if "Time_Display" in row and pd.notna(row["Time_Display"]):
            if i == 0:
                qualifier_str.append((mapping['Time_Display'], str(time_to_seconds(row['Time_Display']))))
            else:
                qualifier_str.append((mapping['Time_Gap'], str(time_to_seconds(row['Time_Display']))))

        # Add rank qualifier
        if "Rnk" in row and 'Rnk' in mapping:
            qualifier_str.append((mapping['Rnk'], str(row['Rnk'])))

        if "Pnt" in row and 'Pnt' in mapping:
            qualifier_str.append((mapping['Pnt'], str(row['Pnt'])))

        if "Rider_Wikidata_ID" in row:
            item_property = row['Rider_Wikidata_ID']
            qualifier_str.append((mapping['Team Wiki ID'], row['Team Wiki ID']))
        else:
            item_property = row['Team Wiki ID']

        if i == 0 and df_type == 'gc_results':
            qualifier_str.append((JERSEY_IDS['Property'], JERSEY_IDS['Jerseys']['Yellow']))
        elif ('Rider_Wikidata_ID' in row and 
            row['Rider_Wikidata_ID'] == yellow_jersey_holder_wikidata_id and
            df_type != 'gc_results'):
            qualifier_str.append((JERSEY_IDS['Property'], JERSEY_IDS['Jerseys']['Yellow']))

        try:
            entity = upload_add_property(
                entity,
                property_id=main_prop,
                upload_item_property=item_property,
                qualifier_str=qualifier_str,
                qualifier_property=qualifier_prop
            )
        except ValueError as e:
            print(f"Error uploading property {list(mapping)[0]} for item entry {row}: {e}")
            continue
    return entity

def update_stage_properties(stage_id: str, stage_results: dict):
    entity = wbi.item.get(entity_id=stage_id, maxlag=30)

    stage_results_gen = stage_results['stage_general_info']
    stage_rankings_start = stage_results['stage_results']
    stage_rankings_end = stage_rankings_start[(stage_rankings_start['Rnk'] != "DNS") & 
                                              (stage_rankings_start['Rnk'] != "DNF") & 
                                              (stage_rankings_start['Rnk'] != "DSQ")]
    gc_rankings = stage_results.get('gc_results', None)
    points_rankings = stage_results.get('points_results', None)
    kom_rankings = stage_results.get('kom_results', None)
    teams_rankings = stage_results.get('teams_results', None)

    number_participants = { 
        'num_part_start': len(stage_rankings_start[stage_rankings_start['Rnk'] != "DNS"]),
        'num_part_end': len(stage_rankings_end)
        }
    winners = {
        "Rider": {
            "First": {
                "Leader": stage_rankings_end.iloc[0]['Rider_Wikidata_ID'],
                "Team": stage_rankings_end.iloc[0]['Team Wiki ID']
            },
            "Second": {
                "Leader": stage_rankings_end.iloc[1]['Rider_Wikidata_ID'],
                "Team": stage_rankings_end.iloc[1]['Team Wiki ID']
            },
            "Third": {
                "Leader": stage_rankings_end.iloc[2]['Rider_Wikidata_ID'],
                "Team": stage_rankings_end.iloc[2]['Team Wiki ID']
            }
        }
    }
    if gc_rankings is not None:
        winners["GC"] = {
            "Leader": {
                "Leader": gc_rankings.iloc[0]['Rider_Wikidata_ID'],
                "Team": gc_rankings.iloc[0]['Team Wiki ID']
            }
        }
    if points_rankings is not None:
        winners["Points"] = {
            "Leader": {
                "Leader": points_rankings.iloc[0]['Rider_Wikidata_ID'],
                "Team": points_rankings.iloc[0]['Team Wiki ID']
            }
        }
    if kom_rankings is not None:
        winners["KOM"] = {
            "Leader": {
                "Leader": kom_rankings.iloc[0]['Rider_Wikidata_ID'],
                "Team": kom_rankings.iloc[0]['Team Wiki ID']
            }
        }
    if teams_rankings is not None:
        winners["Team"] = {
            "Leader": {
                "Leader": teams_rankings.iloc[0]['Team Wiki ID']
            }
        }


    for key, value in WIKIDATA_PROPERTIES.items():
        if type(value) == str and value != "":
            if value == "P793" and key in stage_results_gen:
                events = stage_results_gen[key] if type(stage_results_gen[key]) == list else [stage_results_gen[key]]
                for event in events:
                    entity = upload_add_property(entity, value, upload_item_str=event)
            elif key in stage_results_gen:
                entity = upload_single_overwrite_property(entity, value, upload_item_str=stage_results_gen[key])
        elif key == "profile" and key in stage_results_gen:
            entity = upload_single_overwrite_property(entity, value['property'], upload_item_property=value[stage_results_gen[key]])
        elif key == "number_participants":
            entity = clear_entity_property(entity, value['property'])
            for qual in value['location']:
                entity = upload_add_property(entity, 
                                            value['property'], 
                                            upload_item_str=number_participants[qual['name']], 
                                            qualifier_property = [(qual['property'], qual['id'])])
        elif key == "Winner":
            entity = clear_entity_property(entity, value['property'])
            for win in value['Results']:
                win_name = list(win)[0]
                if win_name in winners:
                    result_info = win[win_name]
                    win_key = result_info['property']
                    for pos_dict in result_info['Position']:
                        pos_key = list(pos_dict)[0]
                        pos_val = pos_dict[pos_key]
                        if "Team" in winners[win_name][pos_key]:
                            entity = upload_add_property(
                                entity,
                                property_id=value['property'],
                                upload_item_property=winners[win_name][pos_key]['Leader'],
                                qualifier_property=[
                                    (win_key, pos_val),
                                    (value['Team'], winners[win_name][pos_key]['Team'])]
                            )
                        else:
                            entity = upload_add_property(
                                entity,
                                property_id=value['property'],
                                upload_item_property=winners[win_name][pos_key]['Leader'],
                                qualifier_property=[(win_key, pos_val)]
                            )
        elif key == "stage_results" and stage_rankings_end is not None:
            entity = upload_result_table(entity, stage_rankings_end, value, key, stage_results_gen.get('yellow_jersey_holder_wikidata_id'))
        elif key == "gc_results" and gc_rankings is not None:
            entity = upload_result_table(entity, gc_rankings, value, key, stage_results_gen.get('yellow_jersey_holder_wikidata_id'))
        elif key == "points_results" and points_rankings is not None:
            entity = upload_result_table(entity, points_rankings, value, key, stage_results_gen.get('yellow_jersey_holder_wikidata_id'))
        elif key == "kom_results" and kom_rankings is not None:
            entity = upload_result_table(entity, kom_rankings, value, key, stage_results_gen.get('yellow_jersey_holder_wikidata_id'))
        elif key == "teams_results" and teams_rankings is not None:
            entity = upload_result_table(entity, teams_rankings, value, key, stage_results_gen.get('yellow_jersey_holder_wikidata_id'))
    return entity

def upload_entity(entity, stage_id: str):
    summary = f"Updated {stage_id} claim via script"
    entity.write(login=login_instance, summary=summary, maxlag=30)

def upload_stage(tdf_year: int, stage_number: int):
    stage_links = create_stage_fetch_urls(tdf_year)

    results = fetch_full_stage_data(stage_links[stage_number - 1], stage_number, tdf_year)
    stage_wikidata_id = results['stage_general_info']['stage_wikidata_id']
    
    entity = update_stage_properties(stage_wikidata_id, results)
    upload_entity(entity, stage_wikidata_id)

def upload_full_tdf(tdf_year: int):
    stage_links = create_stage_fetch_urls(tdf_year)

    for index, stage_link in enumerate(tqdm(stage_links)):
        results = fetch_full_stage_data(stage_link, index+1, tdf_year)
        stage_wikidata_id = results['stage_general_info']['stage_wikidata_id']

        entity = update_stage_properties(stage_wikidata_id, results)
        upload_entity(entity, stage_wikidata_id)




