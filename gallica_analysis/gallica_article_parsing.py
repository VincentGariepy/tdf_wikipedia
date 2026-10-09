import base64
import os
from typing import Literal
import cohere
import requests
import json
import time as time_sleep
from datetime import datetime, time, timedelta
from pathlib import Path
from google import genai
from curl_cffi import requests as cffi_requests

import tqdm
from pcs_parsing.pcs_stage_parsing import create_stage_fetch_urls, parse_html_for_metadata
from utils.web_parsing_utils import get_bs_html

ARTICLE_LINKS = "https://gallica.bnf.fr/api/document/Issues"
ARTICLE_DETAILS_LINK = "https://gallica.bnf.fr/services/getSyntheseContent/ark:/12148/{ark_id}"
API_ARTICLE_URL = "https://gallica.bnf.fr/iiif/ark:/12148/{ark_id}/manifest.json"
EQUIPE_ARK = "cb32768368g"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://gallica.bnf.fr/"
}
API_KEY = os.getenv("GOOGLE_AI_WIKI_KEY")
GEMINI_EXTRACTION_MODEL = "gemini-3.8-flash"

article_date_cache = 'gallica_analysis/cache/tdf_article_dates.json'
equipe_ark_cache = 'gallica_analysis/cache/equipe_ark_ids.json'
article_paths = 'gallica_analysis/full_articles_{tool}/{year}/{date}_stage_{stage_num}.txt'

co = cohere.ClientV2(api_key=os.getenv('COHERE_API_KEY'))

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

def get_article_ark_id(date: str) -> str:
    with open(equipe_ark_cache, 'r', encoding='utf-8') as f:
        ark_id_cache = json.load(f)

    if date in ark_id_cache:
        return ark_id_cache[date]

    parsed_date = parse_str_index_datetime(date)

    params = {
        "ark": f"{EQUIPE_ARK}/date",
        "year": parsed_date.year,
        "month": parsed_date.month
    }
    response = cffi_requests.get(ARTICLE_LINKS, params=params, headers=HEADERS, impersonate='chrome').json()

    ark_id_dict = {}
    for i in response['years'][0]['months'][0]['issues']:
        for j in i['ark']:
            ark_date = convert_datetime_to_str_index(parse_gallica_date(j[1].split(' ')[0]))
            ark_id_dict[ark_date] = j[0]

    with open(equipe_ark_cache, 'w', encoding='utf-8') as f:
        json.dump(ark_id_cache | ark_id_dict, f, indent=2)

    return ark_id_dict[date]

def get_num_pages_article(article_ark_id: str) -> int:
    response = cffi_requests.get(ARTICLE_DETAILS_LINK.format(ark_id=article_ark_id), headers=HEADERS, impersonate='chrome').json()
    return int(response['fragment']['parameters']['tailleDocumentEtNbPage'].split(' ')[0])

def parse_article_page_cohere(ark_id: str, page_num: int) -> str:
    iiif_url = f"https://gallica.bnf.fr/iiif/ark:/12148/{ark_id}/f{page_num}/full/pct:80/0/native.jpg"

    for r in range(3):  # Retry up to 3 times
        try:
            response = co.parse(
                model="parse-v5.0",
                document={
                    "type": "image_url",
                    "image_url": iiif_url,
                },
                output_format="markdown",
            )
            return response.pages[0].markdown.content
        except cohere.BadRequestError as e:
            if r < 2:
                datetime.sleep(120)
            else:
                raise e

def parse_article_page_gemini(ark_id: str, page_num: int) -> str:
    client = genai.Client(api_key=API_KEY)
    
    iiif_url = f"https://gallica.bnf.fr/iiif/ark:/12148/{ark_id}/f{page_num}/full/pct:80/0/native.jpg"

    for r in range(3):  # Retry up to 3 times
        try:
            response = cffi_requests.get(iiif_url, headers=HEADERS, impersonate='chrome')

            b64_data = base64.b64encode(response.content).decode("utf-8")

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
                     "text": """Extract the text from this image. 
                                It is an article page from the L'Équipe Journal, please extract the text and return it as a string.
                                Do not include any additional commentary or information, only return the extracted text.
                                
                                Try and seperate the different sections of the article with "-----"."""}
                ]
            )
            return interaction.output_text
        except Exception as e:
            if r < 2:
                time_sleep.sleep(120)
            else:
                raise e

def parse_full_article(ark_id: str, date: str, stage_num: int, parsing_tool: Literal['Cohere', 'Gemini'], overwrite: bool = False):
    year = parse_str_index_datetime(date).year

    if Path(article_paths.format(year=year, date=date, stage_num=stage_num, tool=parsing_tool.lower())).exists() and not overwrite:
        return

    for i in range(3):  # Retry up to 3 times
        num_pages = get_num_pages_article(ark_id)
        if num_pages > 0:
            break
    article_text = ""

    for page_num in tqdm.tqdm(range(1, num_pages + 1), desc=f"Parsing article for {date} stage {stage_num}"):
        if parsing_tool == 'Cohere':
            page_text = parse_article_page_cohere(ark_id, page_num)
        elif parsing_tool == 'Gemini':
            page_text = parse_article_page_gemini(ark_id, page_num)
        article_text += f"\n\n--- Page {page_num} ---\n\n{page_text}"

    with open(article_paths.format(year=year, date=date, stage_num=stage_num, tool=parsing_tool.lower()), 'w', encoding='utf-8') as f:
        f.write(article_text)

def parse_articles_for_tdf_year(tdf_year: int, parsing_tool: Literal['Cohere', 'Gemini'], overwrite: bool = False):
    tdf_dates = get_tdf_stage_article_dates(tdf_year)

    for stage_num, date in enumerate(tdf_dates, start=1):
        ark_id = get_article_ark_id(date)
        parse_full_article(ark_id, date, stage_num, parsing_tool=parsing_tool, overwrite=overwrite)