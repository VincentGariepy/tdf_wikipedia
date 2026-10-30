import os
import re
from typing import Literal
import tqdm
import json
import locale
from typesafe_sdk import TypeSafeClient, Noul
from google import genai
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from functools import partial

from gallica_analysis.gallica_article_parsing import parse_str_index_datetime

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api"

GALLICA_SOURCE_FORMAT_WITH_AUTHOR = """<ref name=":{ref_num}">{{{{Article|langue=fr|auteur1={author}|titre={title}|périodique=L'Équipe : Le stade, l'air, la route|pages={page_num}|date={str_date}|lire en ligne={{{{Gallica|id={ark_id}/f{page_num}}}}}|accès url=libre}}}}.</ref>"""
GALLICA_SOURCE_FORMAT_WITHOUT_AUTHOR = """<ref name=":{ref_num}">{{{{Article|langue=fr|titre={title}|périodique=L'Équipe : Le stade, l'air, la route|pages={page_num}|date={str_date}|lire en ligne={{{{Gallica|id={ark_id}/f{page_num}}}}}|accès url=libre}}}}.</ref>"""

API_KEY = os.getenv("GOOGLE_AI_WIKI_KEY")
GEMINI_SUMMARY_MODEL = "gemini-3.8-flash"

equipe_ark_cache = 'gallica_analysis/cache/equipe_ark_ids.json'

gemini_article_paths = 'gallica_analysis/full_articles_gemini/{year}/'
gemini_clean_article_paths = 'gallica_analysis/clean_articles_gemini/{year}/'
gemini_detailed_description_paths = 'gallica_analysis/detailed_descriptions_gemini/{year}/'
gemini_detailed_sourced_description_paths = 'gallica_analysis/sourced_descriptions_gemini/{year}/'
cohere_article_paths = 'gallica_analysis/full_articles_cohere/{year}/'
cohere_clean_article_paths = 'gallica_analysis/clean_articles_cohere/{year}/'
cohere_detailed_description_paths = 'gallica_analysis/detailed_descriptions_cohere/{year}/'
cohere_detailed_sourced_description_paths = 'gallica_analysis/sourced_descriptions_cohere/{year}/'

description_example = """
## Résumé de l'étape
### Départ de Brest et premières tentatives d'échappées
Au matin du 25 juin, les dernières festivités ont lieu à Brest et les cyclistes ont un programme précis à suivre avant le départ de la course :

8 h : signatures et ravitaillement place des Fusillés ;
8 h 45 : présentation des équipes. Jean Pierre-Bloch président de la Société nationale des entreprises de presse (SNEP) propriétaire du Tour de France ouvre la « route de France » au peloton en coupant le ruban tricolore sous les yeux des coureurs[39],[40] ;
9 h 35 : départ du défilé par le cours d'Ajot, rue Salaun-Penquer, avenue Clemenceau, rue Jean Jaurès, place de Strasbourg à Rennes ;
10 h 0 : départ de l'étape à l'entrée de la route de Paris.
La météo prévue est ensoleillée et chaude, le vent est nul à tendance favorable.

Dès le début de l'étape plusieurs concurrents tentent de s'échapper. Au km 9, Sowa (Nord-Est / Centre) est le premier coureur à attaquer avec dans sa roue l'Italien Baroni (Italie) qui le rejoint sans véritablement collaborer. Malgré les efforts du Français, les deux hommes ne parviennent pas à prendre plus d'une centaine de mètres d'avance[41],[42].

À proximité de Landerneau (km 18), Canavèse (Sud-Est) attaque à son tour suivi par Martini (Italie) un autre Italien. Leurs efforts permettent de construire un écart de 40 s qui néanmoins ne résiste pas longtemps. Ils réintègrent le peloton au km 30[42],[43]. Au km 36, Nolten (Hollande[b]) et Deledda (Nord-Est / Centre) sortent également du peloton, mais ne réussissent pas non plus à s’éloigner[41].

À la sortie du village de Saint-Thégonnec (km 44), l'équipe de France prend part à son tour aux offensives. Géminiani attaque avec son coéquipier Rolland (France) dans sa roue, suivi de près encore une fois par un Italien, Milano (Italie)[40]. S'ils prennent rapidement le large, une contre-attaque de Gil (Espagne) et Lapébie (Ouest / Sud-Ouest) ramène le peloton avant l'entrée dans Morlaix[39],[42],[41]. Rolland lance une nouvelle attaque dans la foulée, suivi de Decaux (Paris) et Baroni (Italie)[40].

### Les Français insistent dans les côtes bretonnes
Arrivé à Morlaix (km 57), le peloton est très étendu. Le trio Rolland dispose de cent mètres d'avance. Ils sont repris à la sortie de la ville par Caput (Paris) qui s'empare de la prime, avant qu'un nouveau regroupement s'observe[40]. Au même instant, l'Italien Magni (Italie), l'un des trois leaders de l'équipe d'Italie, est contraint de s’arrêter à la suite d'un problème technique (panne de dérailleur). Deux coéquipiers, Franchi et Martini posent pied à terre aussitôt pour l'attendre, suivi plus tard du renfort de Corrieri pourtant équipier de Bartali. Corrieri finit seul le sauvetage de Magni au cours d'une remontée de 20 km puisque les deux autres finirent attardés, incapables de suivre le rythme[46],[42],[47]. Cette situation motive plusieurs Français à attaquer dans la côte à la sortie de la ville : Gaudot et Renaud (Paris) ainsi que Quentin (France), suivis de près par Lauredi, Robic (France), Rotta (Sud-Est) et Voorting (Hollande). Ils sont chassés par les coureurs italiens. Gauthier (France) parvient néanmoins à rejoindre ses coéquipiers en semant le peloton, le groupe compte désormais huit coureurs[41],[39],[48]. Pourtant, à Ponthou (km 72), le groupe de tête est rejoint[41],[43].

Après Saint-Laurent-Plouegat (km 75), Robic, Gauthier, Quentin, Rolland, Géminiani, Rémy, Bonnaventure, et Dotto, soit huit coureurs de l'équipe de France, relancent une attaque, accompagnés d'autres coureurs, dont Coppi (Italie). Ils forment alors un petit peloton de tête d'une vingtaine de coureurs et prennent rapidement 20 s d'avance[41],[48],[39]. Au km 80, ils comptent 30 s sur un petit groupe et 50 s sur le peloton[41].

Au km 91, une vingtaine de coureurs passent au contrôle de ravitaillement en tête, rejoints par Bartali[39]. À partir de là, l'échappée peine à s'organiser et l'équipe de France lâche progressivement l'effort. Coppi déclara à la fin de l'étape ne pas comprendre pourquoi les Français ont condamné leur échappée en ne maintenant pas le rythme. Marcel Bidot, leur directeur technique, déclara que l'absence de Lazaridès dans le groupe en était l'explication[49].

Au km 93, un groupe de poursuivants rejoint celui de tête. Ces quarante-neuf coureurs ont 2 min 30 s d'avance sur le gros peloton[41]. Le ralentissement de l'échappée aboutit à un nouveau regroupement général au km 138[41],[47].

### L'échappée décisive parvient à se former à Saint-Brieuc
Dans une côte avant Saint-Brieuc (km 143), Pardoën (Nord-Est / Centre) parvient à semer le peloton, emmenant avec lui Blomme (Belgique), Vivier (Ouest / Sud-Ouest) et Papazian (Paris)[46],[48]. Seul Van Steenbergen (Belgique) revient sur ce quatuor. Rapidement, ces hommes réalisent un écart de 2 min sur le peloton et de 50 s sur un groupe de neuf poursuivants composé de Vanderstockt et Close (Belgique), Lauredi et Gauthier (France), Cieleska (Nord-Est / Centre), Carle, Telotte et Decaux (Paris), et enfin Dekkers (Hollande)[41],[46]. Les cinq hommes de tête possèdent 1 min 45 s d'avance au km 160 sur les neuf poursuivants qui eux-mêmes devancent de quelques dizaines de secondes Carrea (Italie), Wagtmans (Hollande) et Renaud (Paris). Ces trois coureurs ne tardent pas à rejoindre le groupe des neuf poursuivants au km 170[41],[48].

Au km 190, subissant le rythme des deux Belges, Vivier et Papazian perdent contact avec le groupe de tête. Seul Vivier parvient à rester dans le groupe des poursuivants[42]. À Broons, le trio a construit une avance de 2 min 15 s sur les poursuivants et 4 min 50 s sur le peloton[41].

### Les 50 derniers kilomètres ne changent pas la hiérarchie de l'étape
Le trio de tête continue d'accentuer son avance. Derrière, Vanderstockt et Wagtmans ont pris de l'avance sur un autre groupe de dix poursuivants. Le peloton pointe à 6 min 55 s au km 204[41].

Le sprint final disputé sur la piste du Stade vélodrome de Rennes est remporté par Van Steenbergen qui devance aisément ses compagnons d’échappée et enfile le maillot jaune[41]. Vanderstockt (qui s'est échappé du groupe Lauredi) termine à 2 min 54 s, les neuf poursuivants à 3 min 8 s, le peloton à 6 min 21 s[50]."""

class ArticleMetadata(BaseModel):
    author: Optional[str] = Field(description="Author of the article")
    title: str = Field(description="Title of the article")

class ArticleSources(BaseModel):
    sources: dict[int, ArticleMetadata] = Field(description="Dict containig the section number as key and author and title as value")

    def print(self):
        for source in self.sources.keys():
            print(f"Section : {str(source)}, Author : {self.sources[source].author}, Title : {self.sources[source].title}")

def build_full_source(article_metadata: ArticleMetadata, page_num: str, ref_num: str, ark_id: str, date: str) -> str:
    try:
            locale.setlocale(locale.LC_TIME, "fr_FR.UTF-8")
    except locale.Error:
        # Fallback syntax for Windows systems
        locale.setlocale(locale.LC_TIME, "french")

    formatted_date = datetime.strftime(parse_str_index_datetime(date), '%d %B %Y')
    
    if article_metadata.author is not None and article_metadata.author != "":
        return GALLICA_SOURCE_FORMAT_WITH_AUTHOR.format(
            author=article_metadata.author,
            title=article_metadata.title,
            page_num=page_num,
            ref_num=ref_num,
            ark_id=ark_id,
            str_date=formatted_date
        )
    else:
        return GALLICA_SOURCE_FORMAT_WITHOUT_AUTHOR.format(
            title=article_metadata.title,
            page_num=page_num,
            ref_num=ref_num,
            ark_id=ark_id,
            str_date=formatted_date
        ) 


def get_sources_article(article_entry_text: str, date: str) -> ArticleSources:
    client = genai.Client(api_key=API_KEY)

    interaction = client.interactions.create(
        model=GEMINI_SUMMARY_MODEL,
        input=[
            {"type": "text", 
                "text": f"""The following text is a collection of short entries from the L'Équipe journal from {date}, your task
                            is to extract the title and author of each entry, there may not be an author so you can leave that
                            blank but you should always find a title or give one that makes sense. You should also include the section number
                            for each source. For the titles and authors, make sure they follow the standard french capitalization, meaning only capitalize
                            the first letter of a sentence. Ignore the Source:, that is below the Section.
                            
                            Here is the entry : {article_entry_text}"""}
        ],
        response_format={
            "type": "text",
            "mime_type": "application/json",
            "schema": ArticleSources.model_json_schema()
        },
    )

    article_sources = ArticleSources.model_validate_json(interaction.output_text)

    return article_sources

def clean_article(article_text: str, year: int, date: str) -> str:
    client = TypeSafeClient(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL
    )

    with open(equipe_ark_cache, 'r', encoding='utf-8') as f:
        ark_id_cache = json.load(f)
        article_ark_id = ark_id_cache[date]

    cleaned_article = ""
    page_counter = 0
    source_counter = 0
    for i, split in enumerate(article_text.split("-----")):
        if "--- Page " in split:
            page_counter += 1

        response = client.system_one(
            state={'document': split},
            questions={
                "cleaned_article": Noul(instructions=f"This is a part of the L'Équipe Journal from {str(year)}, is this article or snippet related to reporting on the Tour de France Cycling race ?")
            }
        )

        if response.answers['cleaned_article'].noul >= 0.5:
            source_counter += 1
            cleaned_article +=\
            f"\n\nSection {i + 1} : " +\
            f"\n\nSource : {f'wiki_source_{page_counter}_{i+1}_{source_counter}'}" +\
            split +\
            "-----"
    
    sources = get_sources_article(cleaned_article, date)

    regex_pattern = r"wiki_source_(\d+)_(\d+)_(\d+)"
    str_matches = re.findall(regex_pattern, cleaned_article)

    for page_num, section_num, ref_num in str_matches:
        cleaned_article = cleaned_article.replace(
            f"wiki_source_{page_num}_{section_num}_{ref_num}", 
            build_full_source(sources.sources[int(section_num)], int(page_num), int(ref_num), article_ark_id, date))

    return cleaned_article

def clean_tdf_articles(year: int, parsing_tool: Literal['Cohere', 'Gemini'], overwrite: bool):
    if parsing_tool == 'Cohere':
        article_dir = cohere_article_paths.format(year=year)
        clean_article_dir = cohere_clean_article_paths.format(year=year)
    else:
        article_dir = gemini_article_paths.format(year=year)
        clean_article_dir = gemini_clean_article_paths.format(year=year)

    for filename in tqdm.tqdm(os.listdir(article_dir), desc=f"Processing articles for {year}"):
        if filename.endswith(".txt"):
            date = filename.split('_')[0]
            stage_num = filename.split('_')[-1].split('.')[0]

            article_path = os.path.join(article_dir, filename)
            clean_article_path = os.path.join(clean_article_dir, f"stage_{stage_num}.txt")

            if not overwrite and os.path.exists(clean_article_path):
                continue

            with open(article_path, 'r', encoding='utf-8') as f:
                article_text = f.read()

            cleaned_text = clean_article(article_text, year, date, )

            with open(clean_article_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_text)

def create_stage_summary(year: int, stage_num: int, article_text: str):
    client = genai.Client(api_key=API_KEY)
    
    available_sections = sorted(
        {int(section) for section in re.findall(r"(?m)^Section\s+(\d+)\s*:", article_text)}
    )
    available_sections_text = ", ".join(map(str, available_sections))


    cleaned_article_text = re.sub(r"^Source\s*:.*(?:\r?\n)?", "", article_text, flags=re.MULTILINE)

    interaction = client.interactions.create(
        model=GEMINI_SUMMARY_MODEL,
        input=[{
                "type": "text",
                "text": f"""The following text contains multiple articles from the L'Équipe newspaper regarding the Tour de France (edition {year}, stage {stage_num}). Your task as a Wikipedia/encyclopedic editor is to write a detailed, strictly neutral, and factual narrative account of the race stage in html format.

                Here is an example of a previously written summary of stage 1 of the 1952 Tour de France for structural guidance:

                {description_example}

                Here are the source articles for the {year} edition, stage {stage_num}:

                Make sure to only cite from available sections.
                Here are the available section numbers for citations: {available_sections_text}

                {cleaned_article_text}

                ---
                ### WRITING INSTRUCTIONS & STYLISTIC GUIDELINES

                1. **Format**: Output valid HTML. Use "[n]" footnotes to cite specific source sections corresponding to the statements or paragraphs. Only cite section numbers from the available section numbers listed above; never infer or invent a section number.
                2. **Tone**: Strictly encyclopedic, neutral, and sober (Wikipedia style). Avoid journalistic sensationalism, sports metaphors, or literary prose.
                3. **Prohibited Vocabulary & Idioms**:
                - DO NOT use journalistic idioms (e.g., replace "reprend ses droits" with "reprend après X années d'interruption").
                - DO NOT use metaphorical or dramatic sports jargon (e.g., avoid "hostilités", "bataille", "attaque tranchante", "lourd revers", "le peloton explode"). Instead, use sober terms: "la course s'accélère", "le peloton se disloque", "une attaque", etc.
                - DO NOT use figurative terms like "tandem" for two riders unless referring to an actual tandem bicycle. Use "le duo" or "les deux coureurs".
                - Avoid redundant embellishments or pleonasms (e.g., use "sous un soleil chaud" or state the temperature instead of "sous un soleil accablant").
                4. **Avoid Evaluative & Subjective Language**:
                - Replace subjective adjectives or dramatic framing with plain factual data (e.g., instead of "retard rédhibitoire" or "lourd revers", state the exact time lost: "concède plus de dix minutes").
                - Replace vague descriptions like "longue phase de temporisation" with simple terms like "allure modérée".
                - Do NOT extrapolate physical or emotional states (e.g., "deux coureurs exténués") unless directly and explicitly cited in the sources.
                5. **Adverb Restraint**:
                - Minimize subjective adverbs (e.g., "vivement", "progressivement", "définitivement"). Only include them if strictly necessary and supported directly by the source material.

                Please write the detailed summary in French following these strict neutral encyclopedic constraints and make sure to format it for html.
                """,
            }
        ]
    )
    return interaction.output_text

def create_stage_summaries_for_year(year: int, parsing_tool: Literal['Cohere', 'Gemini'], overwrite: bool):
    if parsing_tool == 'Cohere':
        article_dir = cohere_clean_article_paths.format(year=year)
        detailed_description_dir = cohere_detailed_description_paths.format(year=year)
    else:
        article_dir = gemini_clean_article_paths.format(year=year)
        detailed_description_dir = gemini_detailed_description_paths.format(year=year)

    for filename in tqdm.tqdm(os.listdir(article_dir), desc=f"Creating stage summaries for {year}"):
        if filename.endswith(".txt"):
            stage_num = int(filename.split("_")[-1].split(".")[0])
            article_path = os.path.join(article_dir, filename)

            detailed_description_path = os.path.join(detailed_description_dir, f"stage_{stage_num}.html")

            if not overwrite and os.path.exists(detailed_description_path):
                continue

            with open(article_path, 'r', encoding='utf-8') as f:
                article_text = f.read()

            detailed_description = create_stage_summary(year, stage_num, article_text)

            with open(detailed_description_path, 'w', encoding='utf-8') as f:
                f.write(detailed_description)

def build_source_dictionnary(article_text: str) -> dict[str, str]:
    pattern = r"Section\s+(\d+)[\s\S]*?(<ref[^>]*>[\s\S]*?</ref>)"

    return {
        match.group(1).strip(): match.group(2).strip()
        for match in re.finditer(pattern, article_text)
    }

def reformat_sources(article_sources: dict[str, str], already_source: dict[str, str], match):
    raw_numbers = match.group(1)
    sections = [n.strip() for n in raw_numbers.split(",")]

    formatted_sources = []
    for section in sections:
        if section in already_source:
            formatted_sources.append(already_source[section])
            continue

        full_source = article_sources[section]
        formatted_sources.append(full_source)
        already_source[section] = full_source.split('{')[0]

    return ", ".join(formatted_sources)

def source_description(description: str, article_sources: dict[str, str]) -> str:
    already_source = {}

    pattern = r" \[(\d+(?:\s*,\s*\d+)*)\]"
    
    callback = partial(reformat_sources, article_sources, already_source)
    return re.sub(pattern, callback, description)

def add_sources_description(year: int, parsing_tool: Literal['Cohere', 'Gemini'], overwrite: bool):
    if parsing_tool == 'Cohere':
        article_dir = cohere_clean_article_paths.format(year=year)
        description_dir = cohere_detailed_description_paths.format(year=year)
        sourced_description_dir = cohere_detailed_sourced_description_paths.format(year=year)
    else:
        article_dir = gemini_clean_article_paths.format(year=year)
        description_dir = gemini_detailed_description_paths.format(year=year)
        sourced_description_dir = gemini_detailed_sourced_description_paths.format(year=year)

    for filename in tqdm.tqdm(os.listdir(description_dir), desc=f"Creating stage summaries for {year}"):
        if filename.endswith(".html"):
            stage_num = int(filename.split("_")[-1].split(".")[0])
            description_path = os.path.join(description_dir, filename)
            article_path = os.path.join(article_dir, filename.replace('.html', '.txt'))

            sourced_description_path = os.path.join(sourced_description_dir, f"stage_{stage_num}.html")

            if not overwrite and os.path.exists(sourced_description_path):
                continue

            with open(article_path, 'r', encoding='utf-8') as f:
                article_text = f.read()

            source_dic = build_source_dictionnary(article_text)

            with open(description_path, 'r', encoding='utf-8') as f:
                description_text = f.read()

            sourced_description = source_description(description_text, source_dic)

            with open(sourced_description_path, 'w', encoding='utf-8') as f:
                f.write(sourced_description)