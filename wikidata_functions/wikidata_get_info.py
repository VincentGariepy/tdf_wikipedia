import requests
import time
import json
from wikibaseintegrator.wbi_helpers import get_user_agent, search_entities



WIKIDATA_SQL_URL = 'https://query.wikidata.org/sparql'
WIKIDATA_USER_AGENT = {'User-Agent': 'VGariepy/0.0 (vincent.gariepy@gmail.com)'}
WIKIDATA_ID_QUERY = '''
SELECT DISTINCT ?item ?itemLabel WHERE {
  SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],mul,en". }
  {
    SELECT DISTINCT ?item WHERE {
      ?item p:P1663 ?statement0.
      ?statement0 (ps:P1663) "{pcs_id}".
    }
    LIMIT 1
  }
}
'''

rider_wikidata_id_cache = 'wikidata_functions/wiki_id_rider_cache.json'

with open("wikidata_functions/team_wiki_id.json", "r", encoding="utf-8") as file:
    team_wiki_data_id = json.load(file)

def get_rider_wikidata_id(rider_pcs_id: str):
    with open(rider_wikidata_id_cache, 'r', encoding='utf-8') as f:
            wikidata_ids = json.load(f)

    if rider_pcs_id in wikidata_ids:
        return wikidata_ids[rider_pcs_id]
    
    max_retries = 3
    backoff_seconds = 1

    for attempt in range(max_retries):
        try:
            r = requests.get(
                WIKIDATA_SQL_URL,
                params={'format': 'json', 'query': WIKIDATA_ID_QUERY.replace("{pcs_id}", rider_pcs_id)},
                headers=WIKIDATA_USER_AGENT,
                timeout=10
            )
            wikidata_id = r.json()['results']['bindings'][0]['item']['value'].split('/')[-1]
            wikidata_ids[rider_pcs_id] = wikidata_id

            with open(rider_wikidata_id_cache, 'w', encoding='utf-8') as f:
                json.dump(wikidata_ids, f, indent=2)

            return wikidata_id
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(backoff_seconds * (2 ** attempt))
                continue
            print(rider_pcs_id)
            return None           

def get_team_wikidata_id(team_name: str, tdf_year: int):
    year_index = f'tdf-{str(tdf_year)}'
    if year_index in team_wiki_data_id and team_name in team_wiki_data_id[year_index]:
        return team_wiki_data_id[year_index][team_name]['wikidata_id']
    else:
        return None

def get_stage_wikidata_id(stage_number: int, tdf_year: int):
    search_string = f'{str(tdf_year)} Tour de France, stage {stage_number}'
    results = search_entities(search_string=search_string, 
                    dict_result=True, max_results=1, 
                    user_agent=get_user_agent(WIKIDATA_USER_AGENT['User-Agent']),
                    maxlag=30)

    for result in results:
        if result['label'] == search_string:
            return result['id']
    return None
    
