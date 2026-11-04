# TDF Wikipedia

This repository builds structured Tour de France knowledge for Wikipedia-style articles by combining archival race coverage, stage statistics, and Wikidata-backed identity data.

## What this project does

- Pulls historical race information from public sources, especially Gallica newspaper archives and ProCyclingStats.
- Parses and cleans stage articles and summaries into a more usable format for downstream writing.
- Enriches rider, team, and stage records with IDs and metadata from Wikidata.
- Produces article-ready descriptions and structured race data that can be used to support Wikipedia content.

## How the different parts fit together

### `gallica_analysis/`
This is the historical text pipeline. It downloads, parses, cleans, and summarizes articles from the Gallica digital archive (French press coverage of the Tour). These files convert raw newspaper content into article text and stage descriptions that can be used as source material for narrative summaries.

Typical role:
- fetch race coverage from archives
- extract articles for each stage or year
- clean HTML and noisy OCR output
- generate detailed or sourced descriptions for later review

### `pcs_parsing/`
This is the structured results pipeline. It scrapes ProCyclingStats for stage-level metadata and race outcomes, including distances, profiles, key events, rider results, and stage-specific data.

Typical role:
- parse stage pages and rider data
- map riders and teams to identifiers
- build structured result tables for each stage
- provide the factual backbone used in summaries and uploads

### `wikidata_functions/`
This layer connects the project to Wikidata. It resolves rider, team, and stage IDs and uploads structured race properties and result data to Wikidata items.

Typical role:
- look up existing Wikidata entities for cyclists and stages
- attach stage or rider metadata to those entities
- maintain consistency with Wikipedia/Wikidata identifiers

### `utils/`
Shared helper code for fetching webpages, parsing HTML, and supporting common scraping operations used across the repo.

### `description_website/`
This contains supporting output or website-facing materials related to the generated descriptions and presentation.

### Notebooks
- `equipe_fetching.ipynb` — broader workflow for fetching and preparing source material for a given TDF year
- `wikidata_results_uploads.ipynb` — notebook-based workflow for pushing structured results into Wikidata

## Typical workflow

1. Use `gallica_analysis` to gather and clean historical article text for a specific Tour de France edition.
2. Use `pcs_parsing` to collect the official stage-level results and metadata.
3. Combine both sources to produce article-ready summaries and structured race context.
4. Use `wikidata_functions` to resolve IDs and upload normalized data to Wikidata.
5. Review the generated outputs and iterate on wording, sources, and data quality.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Notes

This project depends on public data sources and external APIs, so some scripts may require environment variables or credentials. The workflow is intentionally split by source and responsibility: Gallica provides historical narrative coverage, PCS provides factual race structure, and Wikidata provides entity-level enrichment and persistence.
