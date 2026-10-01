import os
import tqdm
from typesafe_sdk import TypeSafeClient, Noul

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api"

article_paths = 'gallica_analysis/full_articles/{year}/'
clean_article_paths = 'gallica_analysis/clean_articles/{year}/'

def clean_article(article_text: str, year: int) -> str:
    client = TypeSafeClient(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL
    )

    article_splits = article_text.split("---")
    cleaned_article = ""


    for split in article_splits:    
        response = client.system_one(
            state={'document': split},
            questions={
                "cleaned_article": Noul(instructions=f"This is a part of the L'Équipe Journal from {str(year)}, is this article or snippet related to reporting on the Tour de France Cycling race ?")
            }
        )

        if response.answers['cleaned_article'].noul >= 0.5:
            cleaned_article += split + "---"
    
    return cleaned_article

def clean_tdf_articles(year: int, overwrite: bool):
    article_dir = article_paths.format(year=year)
    clean_article_dir = clean_article_paths.format(year=year)

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