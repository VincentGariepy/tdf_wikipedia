import base64
import os
import json
import time as time_sleep
from datetime import datetime, time, timedelta
from pathlib import Path
from google import genai
from google.genai import types
from curl_cffi import requests as cffi_requests

import tqdm
from pcs_parsing.pcs_stage_parsing import create_stage_fetch_urls, parse_html_for_metadata
from utils.web_parsing_utils import get_bs_html

SOURCES = ['equipe', 'figaro', 'franc_tireur', 'humanite', 'liberation']

ARTICLE_LINKS = "https://gallica.bnf.fr/api/document/Issues"
ARTICLE_DETAILS_LINK = "https://gallica.bnf.fr/services/getSyntheseContent/ark:/12148/{ark_id}"
API_ARTICLE_URL = "https://gallica.bnf.fr/iiif/ark:/12148/{ark_id}/manifest.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://gallica.bnf.fr/"
}
API_KEY = os.getenv("GOOGLE_AI_WIKI_KEY")
GEMINI_EXTRACTION_MODEL = "gemini-4-hydrogen"

article_date_cache = 'gallica_analysis/cache/tdf_article_dates.json'
ark_cache = 'gallica_analysis/cache/ark_ids/{journal}_ark_ids.json'
article_paths = 'gallica_analysis/analysis_outputs/full_articles/{journal}/{year}/{date}_stage_{stage_num}.txt'

extract_prompt = """Extract the text from this image. 
                    It is an article page from the {journal_name}, please extract the text and return it as a string.
                    Do not include any additional commentary or information, only return the extracted text.
                    
                    Try and seperate the different sections of the article with "-----"."""

with open('gallica_analysis/journal_metadata.json', 'r', encoding='utf-8') as f:
    journal_metadata = json.load(f)

def parse_pcs_date(date: str) -> datetime:
    return datetime.strptime(date, '%d %B %Y') 

def parse_gallica_date(date: str) -> datetime:
    return datetime.strptime(date, '%Y/%m/%d')

def parse_str_index_datetime(date: str) -> datetime:
    return datetime.strptime(date, '%d-%m-%Y')

def convert_datetime_to_str_index(date: datetime) -> str:
    return datetime.strftime(date, '%d-%m-%Y')

def get_tdf_stage_article_dates(tdf_year: int) -> list[str]:
    with open(article_date_cache, 'r', encoding='utf-8') as f:
        article_date_cache_dict = json.load(f)

    tdf_year_str = str(tdf_year)
    if tdf_year_str in article_date_cache_dict:
        return article_date_cache_dict[tdf_year_str]
    
    urls = create_stage_fetch_urls(tdf_year)

    tdf_dates = [convert_datetime_to_str_index(
                    parse_pcs_date(parse_html_for_metadata(get_bs_html(url))[0]['Date'])
                    + timedelta(days=1)
                ) for url in urls]

    article_date_cache_dict[tdf_year] = tdf_dates
    with open(article_date_cache, 'w', encoding='utf-8') as f:
        json.dump(article_date_cache_dict, f, indent=2)

    return tdf_dates

def get_article_ark_id(date: str, source: str) -> str:
    assert source in SOURCES

    with open(ark_cache.format(journal=source), 'r', encoding='utf-8') as f:
        ark_id_cache = json.load(f)

    if date in ark_id_cache:
        return ark_id_cache[date]

    parsed_date = parse_str_index_datetime(date)

    params = {
        "ark": f"{journal_metadata["journal"][source]['ark_global']}/date",
        "year": parsed_date.year,
        "month": parsed_date.month
    }
    response = cffi_requests.get(ARTICLE_LINKS, params=params, headers=HEADERS, impersonate='chrome', timeout=120).json()
    
    ark_id_dict = {}
    for i in response['years'][0]['months'][0]['issues']:
        for j in i['ark']:
            try:
                ark_date = convert_datetime_to_str_index(parse_gallica_date(j[1][:10]))
                ark_id_dict[ark_date] = j[0]
            except (ValueError, KeyError):
                continue

    if date not in ark_id_dict:
        ark_id_dict[date] = None

    with open(ark_cache.format(journal=source), 'w', encoding='utf-8') as f:
        json.dump(ark_id_cache | ark_id_dict, f, indent=2)

    if date in ark_id_dict:
        return ark_id_dict[date]

    return None

def get_num_pages_article(article_ark_id: str) -> int:
    for i in range(3):
        try:
            response = cffi_requests.get(ARTICLE_DETAILS_LINK.format(ark_id=article_ark_id), headers=HEADERS, impersonate='chrome', timeout=120).json()
            return int(response['fragment']['parameters']['tailleDocumentEtNbPage'].split(' ')[0])
        except Exception as e:
            if i == 2:
                raise e
            time_sleep.sleep(120)
            continue

def get_article_data(ark_id: str, page_num: int) -> bytes:
    iiif_url = f"https://gallica.bnf.fr/iiif/ark:/12148/{ark_id}/f{page_num}/full/pct:70/0/native.jpg"

    for i in range(3):
        try:
            response = cffi_requests.get(iiif_url, headers=HEADERS, impersonate='chrome', timeout=120)
            return response.content

        except Exception as e:
            if i == 2:
                raise e
            time_sleep.sleep(120)
            continue
    
def parse_article_page_gemini(ark_id: str, page_num: int, source: str) -> str:
    client = genai.Client(api_key=API_KEY)

    for r in range(3):  # Retry up to 3 times
        try:
            bytes_data = get_article_data(ark_id, page_num)
            b64_data = base64.b64encode(bytes_data).decode("utf-8")

            # Send inline image interaction
            interaction = client.interactions.create(
                model=GEMINI_EXTRACTION_MODEL,
                input=[
                    {
                        "type": "image",
                        "data": b64_data,
                        "mime_type": "image/jpeg"
                    },
                    {"type": "text", 
                     "text": extract_prompt.format(journal_name=journal_metadata["journal"][source]["full_name"])}
                ]
            )
            return interaction.output_text
        except Exception as e:
            if r < 2:
                time_sleep.sleep(120)
            else:
                raise e

def parse_full_article(ark_id: str, date: str, stage_num: int, source: str, overwrite: bool = False):
    assert source in SOURCES

    year = parse_str_index_datetime(date).year

    if Path(article_paths.format(journal=source, year=year, date=date, stage_num=stage_num)).exists() and not overwrite:
        return

    num_pages = get_num_pages_article(ark_id)

    article_text = ""

    for page_num in tqdm.tqdm(range(1, num_pages + 1), desc=f"Parsing article for {date} stage {stage_num}"):
        page_text = parse_article_page_gemini(ark_id, page_num, source)
        article_text += f"\n\n--- Page {page_num} ---\n\n{page_text}"

    with open(article_paths.format(journal=source, year=year, date=date, stage_num=stage_num), 'w', encoding='utf-8') as f:
        f.write(article_text)

def parse_articles_for_tdf_year(tdf_year: int, source: str, overwrite: bool = False):
    assert source in SOURCES

    tdf_dates = get_tdf_stage_article_dates(tdf_year)

    for stage_num, date in enumerate(tdf_dates, start=1):
        ark_id = get_article_ark_id(date, source)
        if ark_id is not None:
            parse_full_article(ark_id, date, stage_num, source=source, overwrite=overwrite)

def parse_articles_for_tdf_year(tdf_year: int, sources: list[str], overwrite: bool = False):
    assert set(sources).issubset(SOURCES)

    for source in sources:
        parse_articles_for_tdf_year(tdf_year, source, overwrite)


### Batch functions ###

def add_full_article_batch(ark_id: str, date: str, stage_num: int, source: str, requests: list, overwrite: bool = False):
    assert source in SOURCES

    year = parse_str_index_datetime(date).year
    
    if Path(article_paths.format(journal=source, year=year, date=date, stage_num=stage_num)).exists() and not overwrite:
        return

    num_pages = get_num_pages_article(ark_id)

    for page_num in range(1, num_pages + 1):
        image_bytes = get_article_data(ark_id, page_num)

        requests.append(
            types.InlinedRequest(
                contents=[
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type="image/jpeg",
                    ),
                    extract_prompt.format(journal_name=journal_metadata["journal"][source]["full_name"]),
                ],
                metadata={"ark_id": ark_id, "page_num": str(page_num)}
            )
        )

def request_batch_extraction(requests: list[types.InlinedRequest]) -> list[types.InlinedResponse]:
    client = genai.Client(api_key=API_KEY)

    batch_job = client.batches.create(
        model=GEMINI_EXTRACTION_MODEL,
        src=requests,
        config={"display_name": "journal-transcripton-batch"}
    )

    print(f"Batch job created: {batch_job.name} (State: {batch_job.state})")

    # 4. Poll until completed
    while batch_job.state not in (
        types.JobState.JOB_STATE_SUCCEEDED,
        types.JobState.JOB_STATE_FAILED,
        types.JobState.JOB_STATE_CANCELLED,
    ):
        print(f"Current state: {batch_job.state}... waiting 60s")
        time_sleep.sleep(60)
        batch_job = client.batches.get(name=batch_job.name)

    if batch_job.state == types.JobState.JOB_STATE_SUCCEEDED:
        return batch_job.dest.inlined_responses

    else:
        raise(f"Job failed with error: {batch_job.error}")

def process_batch_requests(responses: list[types.InlinedResponse], ark_id: str, year: int, date: str, stage_num: int, source: str):
    assert source in SOURCES

    article_pages = []
    for item in responses:
        if ark_id == item.metadata.get("ark_id"):
            try:
                article_page = item.response.text
                article_page_number = int(item.metadata.get("page_num"))
            except Exception:
                print(f"Could not parse {ark_id}, {stage_num}, {date}")
                print(item)

            article_pages.append((article_page_number, article_page))

    article_text = ""
    for article in sorted(article_pages):
        article_text += f"\n\n--- Page {article[0]} ---\n\n{article[1]}"

    with open(article_paths.format(journal=source, year=year, date=date, stage_num=stage_num), 'w', encoding='utf-8') as f:
        f.write(article_text)

def parse_articles_for_tdf_year_batch(tdf_year: int, sources: list[str], overwrite: bool = False):
    assert set(sources).issubset(SOURCES)

    tdf_dates = get_tdf_stage_article_dates(tdf_year)

    batch_requests = []
    for source in sources:
        print(f"Processing source : {source}")
        for stage_num, date in tqdm.tqdm(enumerate(tdf_dates, start=1), "Creating batch"):
            ark_id = get_article_ark_id(date, source)
            if ark_id is not None:
                add_full_article_batch(ark_id, date, stage_num, source=source, requests=batch_requests, overwrite=overwrite)

        if not batch_requests:
            continue
        batch_response = request_batch_extraction(batch_requests)

        for stage_num, date in tqdm.tqdm(enumerate(tdf_dates, start=1), "Processing batch"):
            ark_id = get_article_ark_id(date, source)
            if ark_id is not None:
                process_batch_requests(batch_response, ark_id, tdf_year, date, stage_num, source)