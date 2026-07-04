# Research Tools

Python modules for searching scientific literature and code repositories related to AI-based bone species and image classification. Results are normalized into shared dataclasses so the research agent, knowledge graph, and visualization layers can consume them consistently.

## Layout

```
tools/
├── literature/           # Paper search (OpenAlex, Semantic Scholar)
│   ├── paper.py
│   ├── openalex.py
│   ├── semantic_scholar.py
│   └── search_papers.py
├── code_repos/           # GitHub repository search
│   ├── code_repo.py
│   └── search_github.py
└── knowledge_graph/      # Graph queries (stub)
    └── query_graph.py
```

Run commands from the `openclaw/` directory so imports resolve correctly:

```bash
cd openclaw
python3 -c "from tools.literature import search_papers; print(search_papers('bone classification')[0].title)"
```

---

## Literature module

### `Paper`

Defined in `literature/paper.py`. Normalized representation of a paper regardless of which API returned it.

| Field | Type | Description |
|-------|------|-------------|
| `title` | `str` | Paper title |
| `authors` | `list[str]` | Author display names |
| `year` | `int \| None` | Publication year |
| `abstract` | `str \| None` | Abstract text |
| `doi` | `str \| None` | DOI without `https://doi.org/` prefix |
| `url` | `str \| None` | Canonical link to the record |
| `source_id` | `str \| None` | ID from the source API |
| `source` | `str` | `"openalex"`, `"semantic_scholar"`, or `"unknown"` |
| `venue` | `str \| None` | Journal or conference name |
| `citation_count` | `int \| None` | Citation count when available |
| `topics` | `list[str]` | Subject areas or fields of study |

**Methods**

- `to_dict()` — serialize to a plain `dict` for JSON export or agent tool output
- `from_openalex(work)` — build a `Paper` from an OpenAlex API work object
- `from_semantic_scholar(work)` — build a `Paper` from a Semantic Scholar API response

### Search functions

#### `search_openalex(query, *, per_page=25) -> list[Paper]`

Searches the [OpenAlex](https://openalex.org) works API. No API key is required. OpenAlex asks that clients include a `mailto` parameter for polite pool access.

**File:** `literature/openalex.py`

#### `search_semantic_scholar(query, *, limit=25) -> list[Paper]`

Searches the [Semantic Scholar](https://www.semanticscholar.org) paper search API. No API key is required for basic use.

**File:** `literature/semantic_scholar.py`

#### `search_papers(query) -> list[Paper]`

Runs both `search_openalex` and `search_semantic_scholar`, then deduplicates results. Deduplication uses DOI first, then `source_id`, then a case-folded title.

**File:** `literature/search_papers.py`

Also exports an agent tool definition:

```python
tool = {
    "name": "search_papers",
    "description": "Search scientific literature",
    "parameters": {"query": "string"},
}
```

### Literature examples

```python
from tools.literature import Paper, search_openalex, search_semantic_scholar, search_papers

# Combined search (recommended)
papers = search_papers("bone species image classification CNN")

# Single-source search
openalex_papers = search_openalex("osteology deep learning", per_page=10)
s2_papers = search_semantic_scholar("zooarchaeology bone identification", limit=10)

# Inspect or serialize results
for paper in papers:
    print(paper.title, paper.year, paper.citation_count)
    print(paper.to_dict())
```

---

## Code repositories module

### `CodeRepository`

Defined in `code_repos/code_repo.py`. Normalized representation of a GitHub repository.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Short repository name |
| `full_name` | `str \| None` | `owner/repo` slug |
| `url` | `str \| None` | GitHub HTML URL |
| `description` | `str \| None` | Repository description |
| `language` | `str \| None` | Primary language reported by GitHub |
| `stars` | `int \| None` | Star count |
| `forks` | `int \| None` | Fork count |
| `license` | `str \| None` | SPDX ID or license name |
| `topics` | `list[str]` | GitHub topic tags |
| `source` | `str` | Always `"github"` |
| `source_id` | `str \| None` | GitHub numeric repository ID |

**Methods**

- `to_dict()` — serialize to a plain `dict`
- `from_github(repo)` — build a `CodeRepository` from a GitHub API repository object

### `PaperRepositoryLink`

Defined in `code_repos/code_repo.py`. Represents a link between a paper and a code repository (for future knowledge-graph use).

| Field | Type | Description |
|-------|------|-------------|
| `paper_id` | `str \| None` | Paper identifier (e.g. DOI or `source_id`) |
| `repo_id` | `str \| None` | Repository `source_id` |
| `relation_type` | `str` | Relationship label, default `"implements"` |
| `confidence` | `float \| None` | Match confidence score |
| `evidence` | `str \| None` | Text explaining why the link was made |

### `search_github(query, *, per_page=30, sort="stars", order="desc") -> list[CodeRepository]`

Searches GitHub repositories via the [repository search API](https://docs.github.com/en/rest/search/search#search-repositories).

**File:** `code_repos/search_github.py`

**Authentication (optional but recommended)**

Set one of these environment variables to raise rate limits from 10 to 60 requests per minute:

```bash
export GITHUB_TOKEN=ghp_...
# or
export GH_TOKEN=ghp_...
```

### Code repository examples

```python
from tools.code_repos import CodeRepository, search_github

repos = search_github("bone fracture classification pytorch")

for repo in repos:
    print(repo.full_name, repo.stars, repo.language)
    print(repo.to_dict())
```

GitHub search supports [qualifiers](https://docs.github.com/en/search-github/searching-on-github/searching-for-repositories) in the query string:

```python
repos = search_github("bone classification language:python stars:>5")
```

---

## Agent configuration

The bone research agent in `config/research_agent.yaml` references these tools:

```yaml
tools:
  - search_papers
  - search_repos
  - extract_entities
  - query_graph
```

`search_papers` is implemented in `literature/search_papers.py`. `search_repos` is intended to map to `code_repos/search_github.py` once wired into the agent runtime.

---

## Dependencies

The search modules use only the Python standard library (`urllib`, `json`, `os`, `dataclasses`). No extra packages are required beyond what is already in `requirements.txt` for the LLM client.

---

## Rate limits and errors

| API | Unauthenticated limit | Notes |
|-----|----------------------|-------|
| OpenAlex | ~10 requests/second | Include a real `mailto` in `openalex.py` for production |
| Semantic Scholar | 100 requests / 5 min | May return HTTP 429 under heavy use |
| GitHub | 10 requests / minute | Set `GITHUB_TOKEN` or `GH_TOKEN` for higher limits |

All search functions use a 30-second HTTP timeout. Network or rate-limit failures propagate as `urllib.error.HTTPError` or `urllib.error.URLError`.

---

## Suggested query terms

For bone species and image classification research:

- `"bone species classification" machine learning`
- `"osteology" "deep learning" image`
- `"zooarchaeology" CNN identification`
- `"bone fracture" classification pytorch`
- `"skeletal remains" species recognition`

---

## Next steps

Planned extensions that build on these modules:

1. Wire `search_github` into the agent as `search_repos`
2. Implement `extract_entities` to pull species names, methods, and datasets from `Paper` abstracts
3. Store `Paper` and `CodeRepository` nodes in Neo4j via `knowledge_graph/query_graph.py`
4. Add modular network and data visualizations over the stored graph
