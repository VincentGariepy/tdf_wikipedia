import os
from typing import Literal
import tqdm
from typesafe_sdk import TypeSafeClient, Noul
from google import genai

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api"

API_KEY = os.getenv("GOOGLE_AI_WIKI_KEY")
GEMINI_SUMMARY_MODEL = "gemini-3.8-flash"

gemini_article_paths = 'gallica_analysis/full_articles_gemini/{year}/'
gemini_clean_article_paths = 'gallica_analysis/clean_articles_gemini/{year}/'
gemini_detailed_description_paths = 'gallica_analysis/detailed_descriptions_gemini/{year}/'
cohere_article_paths = 'gallica_analysis/full_articles_cohere/{year}/'
cohere_clean_article_paths = 'gallica_analysis/clean_articles_cohere/{year}/'
cohere_detailed_description_paths = 'gallica_analysis/detailed_descriptions_cohere/{year}/'

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


def clean_article(article_text: str, year: int) -> str:
    client = TypeSafeClient(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL
    )

    article_splits = article_text.split("-----")
    cleaned_article = ""


    for i, split in enumerate(article_splits):    
        response = client.system_one(
            state={'document': split},
            questions={
                "cleaned_article": Noul(instructions=f"This is a part of the L'Équipe Journal from {str(year)}, is this article or snippet related to reporting on the Tour de France Cycling race ?")
            }
        )

        if response.answers['cleaned_article'].noul >= 0.5:
            cleaned_article += f"\n\nSection {i + 1} : " + split + "-----"
    
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
            article_path = os.path.join(article_dir, filename)
            clean_article_path = os.path.join(clean_article_dir, filename)

            if not overwrite and os.path.exists(clean_article_path):
                continue

            with open(article_path, 'r', encoding='utf-8') as f:
                article_text = f.read()

            cleaned_text = clean_article(article_text, year)

            with open(clean_article_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_text)

def create_stage_summary(year: int, stage_num: int, article_text: str):
    client = genai.Client(api_key=API_KEY)

    interaction = client.interactions.create(
        model=GEMINI_SUMMARY_MODEL,
        input=[
            {"type": "text", 
                "text": f"""The following text is multiple articles from the L'Équipe Journal, regarding the Tour de France cycling,
                            specifically the {year} edition, stage {stage_num}. Your task as a journalist expert is to write a detailed description of the race.
                            
                            Here is an example of a previously written summary of stage 1 of the 1952 Tour de France, to give you an idea of the level of detail and style expected:
                            
                            {description_example}

                            Here are the articles for the {year} edition, stage {stage_num} : 

                            {article_text}

                            Please write the detailed description in french and make sure to use "[n]" to link to the section used to write different paragraphs or sentences of the paragraph.
                            Make sure to follow the same writing style and as the example provided and format your text in html.
                            """}
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
