"""Small source connectors used by the Lens retrieval pipeline."""

import json
from datetime import date, timedelta
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree


def _abstract_from_inverted_index(index: dict | None) -> str:
    if not index:
        return ""
    words = []
    for word, positions in index.items():
        for position in positions:
            words.append((position, word))
    return " ".join(word for _, word in sorted(words))


def fetch_openalex(query: str, lookback_days: int = 30, max_results: int = 10, timeout: int = 15) -> list:
    """Fetch recent scholarly works from OpenAlex using its public API."""
    start_date = date.today() - timedelta(days=max(1, int(lookback_days)))
    params = (
        "https://api.openalex.org/works?search=" + quote_plus(query[:300])
        + f"&filter=from_publication_date:{start_date.isoformat()},to_publication_date:{date.today().isoformat()}"
        + "&sort=publication_date:desc&per-page=" + str(max(1, min(int(max_results), 50)))
    )
    request = Request(params, headers={"User-Agent": "agentic-lens/0.1"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    entries = []
    for work in payload.get("results", []):
        location = work.get("primary_location") or {}
        source = (location.get("source") or {}).get("display_name") or "OpenAlex"
        url = location.get("landing_page_url") or work.get("doi") or work.get("id", "")
        entries.append({
            "title": work.get("title", ""),
            "link": url,
            "summary": _abstract_from_inverted_index(work.get("abstract_inverted_index")),
            "published": work.get("publication_date", ""),
            "source": source,
            "source_type": "paper",
            "authors": [
                (author.get("author") or {}).get("display_name", "")
                for author in work.get("authorships", [])
            ],
            "doi": work.get("doi"),
        })
    return entries


def fetch_crossref(query: str, lookback_days: int = 30, max_results: int = 10, timeout: int = 15) -> list:
    """Fetch recent scholarly metadata from Crossref."""
    start_date = date.today() - timedelta(days=max(1, int(lookback_days)))
    params = urlencode({
        "query": query[:300],
        "filter": f"from-pub-date:{start_date.isoformat()},until-pub-date:{date.today().isoformat()}",
        "sort": "published",
        "order": "desc",
        "rows": max(1, min(int(max_results), 50)),
    })
    request = Request("https://api.crossref.org/works?" + params, headers={"User-Agent": "agentic-lens/0.1"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    entries = []
    for work in (payload.get("message") or {}).get("items", []):
        published = work.get("published-print") or work.get("published-online") or {}
        parts = published.get("date-parts") or [[]]
        date_parts = parts[0]
        published_text = "-".join(str(value).zfill(2) for value in date_parts)
        entries.append({
            "title": (work.get("title") or [""])[0],
            "link": work.get("URL") or ("https://doi.org/" + work["DOI"] if work.get("DOI") else ""),
            "summary": work.get("abstract", ""),
            "published": published_text,
            "source": (work.get("container-title") or ["Crossref"])[0],
            "source_type": "paper",
            "authors": [" ".join(filter(None, [author.get("given"), author.get("family")])) for author in work.get("author", [])],
            "doi": work.get("DOI"),
        })
    return entries


def fetch_pubmed(query: str, lookback_days: int = 30, max_results: int = 10, timeout: int = 15) -> list:
    """Fetch recent PubMed records and abstracts using NCBI E-utilities."""
    start_date = date.today() - timedelta(days=max(1, int(lookback_days)))
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urlencode({
        "db": "pubmed", "term": f"({query[:250]}) AND ({start_date.isoformat()}[PDAT] : {date.today().isoformat()}[PDAT])",
        "retmax": max(1, min(int(max_results), 50)), "retmode": "json",
    })
    request = Request(search_url, headers={"User-Agent": "agentic-lens/0.1"})
    with urlopen(request, timeout=timeout) as response:
        ids = json.loads(response.read().decode("utf-8")).get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urlencode({
        "db": "pubmed", "id": ",".join(ids), "retmode": "xml",
    })
    request = Request(fetch_url, headers={"User-Agent": "agentic-lens/0.1"})
    with urlopen(request, timeout=timeout) as response:
        root = ElementTree.fromstring(response.read())

    entries = []
    for article in root.findall(".//PubmedArticle"):
        medline = article.find(".//MedlineCitation")
        pmid = (medline.findtext("PMID") if medline is not None else "")
        title = "".join(article.findtext(".//ArticleTitle") or "").strip()
        abstract = " ".join("".join(node.itertext()).strip() for node in article.findall(".//AbstractText"))
        journal = article.findtext(".//Journal/Title") or "PubMed"
        year = article.findtext(".//PubDate/Year") or article.findtext(".//PubDate/MedlineDate") or ""
        doi = next((node.text for node in article.findall(".//ArticleId") if node.attrib.get("IdType") == "doi"), None)
        entries.append({
            "title": title, "link": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "summary": abstract,
            "published": year, "source": journal, "source_type": "paper",
            "authors": [" ".join(filter(None, [author.findtext(".//ForeName"), author.findtext(".//LastName")])) for author in article.findall(".//Author")],
            "doi": doi,
        })
    return entries
