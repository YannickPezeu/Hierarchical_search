# Semantic Search API - EPFL LEX

A semantic search API built with **FastAPI** and **LlamaIndex** for indexing and searching documents with hierarchical support, ServiceNow integration, and hybrid search capabilities.

## 📋 Table of Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [API Endpoints](#api-endpoints)
- [Web Scraping](#web-scraping)
- [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture

The project consists of several modules:

| Module | Description |
|--------|-------------|
| **Indexing** | Converts documents (PDF, HTML, DOCX) to Markdown and creates vector indexes |
| **Search** | Semantic search with reranking and intelligent caching |
| **ServiceNow** | Synchronization and live search in ServiceNow knowledge bases |
| **Finance** | Hybrid search combining local sources and ServiceNow |
| **Libraries** | Library management with group-based access control |

---

## ✅ Prerequisites

- **Python** 3.10+
- **Node.js** 18+ (for the scraper)
- Access to an OpenAI-compatible embeddings API (EPFL RCP or OpenAI)
- (Optional) Access to EPFL ServiceNow API

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd semantic-search-api
```

### 2. Create a Python virtual environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
.\venv\Scripts\activate   # Windows
```

### 3. Install Python dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

If `requirements.txt` doesn't exist, install manually:

```bash
pip install \
    fastapi \
    uvicorn[standard] \
    python-dotenv \
    pydantic \
    passlib[bcrypt] \
    requests \
    httpx \
    beautifulsoup4 \
    markdownify \
    llama-index \
    llama-index-llms-openai \
    llama-index-embeddings-openai \
    llama-index-vector-stores-faiss \
    faiss-cpu \
    pymupdf \
    rapidfuzz
```

### 4. Install Node.js dependencies (for the scraper)

```bash
npm install puppeteer fs-extra dotenv
```

---

## ⚙️ Configuration

### Create the `.env` file

Create a `.env` file at the project root:

```env
# ===================================
# API & Embeddings (EPFL RCP or OpenAI)
# ===================================
RCP_API_ENDPOINT=https://inference.rcp.epfl.ch/v1
RCP_API_KEY=your_rcp_api_key_here
RCP_QWEN_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B

# Alternative: OpenAI
# OPENAI_API_ENDPOINT=https://api.openai.com/v1
# OPENAI_KEY=sk-your-openai-key

# ===================================
# API Security
# ===================================
INTERNAL_API_KEY=your_secure_internal_api_key_here

# ===================================
# Index Storage
# ===================================
INDEXES_BASE_DIR=./all_indexes

# ===================================
# ServiceNow (optional)
# ===================================
SERVICENOW_URL=https://epfl.service-now.com
SERVICENOW_USERNAME=WS_AI
SERVICENOW_KEY=your_servicenow_api_key_here
SERVICENOW_KB_IDS_FINANCE=["kb_id_1", "kb_id_2"]

# ===================================
# Reranking (optional)
# ===================================
RERANK_MODEL=BAAI/bge-reranker-v2-m3

# ===================================
# EPFL Scraper (optional)
# ===================================
EPFL_USERNAME_TEQUILA=your_tequila_username
EPFL_USERNAME_MICROSOFT=your_microsoft_username
EPFL_PASSWORD=your_password
```

### Required Variables

| Variable | Description |
|----------|-------------|
| `RCP_API_ENDPOINT` | Embeddings API URL |
| `RCP_API_KEY` | API key for embeddings |
| `RCP_QWEN_EMBEDDING_MODEL` | Embeddings model name |
| `INTERNAL_API_KEY` | Secret key to secure the API |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `INDEXES_BASE_DIR` | Index storage directory | `./all_indexes` |
| `SERVICENOW_*` | ServiceNow configuration | - |
| `RERANK_MODEL` | Reranking model | `BAAI/bge-reranker-v2-m3` |

---

## 📁 Project Structure

```
semantic-search-api/
├── src/
│   ├── main.py                 # FastAPI entry point
│   ├── settings.py             # LlamaIndex configuration
│   ├── components.py           # Custom components (reranker, filters)
│   │
│   ├── core/
│   │   ├── config.py           # Global configuration
│   │   ├── models.py           # Pydantic models
│   │   ├── utils.py            # Utilities
│   │   ├── cache.py            # Search cache (RAM + disk)
│   │   ├── indexing.py         # Indexing logic
│   │   ├── indexing_html.py    # HTML-specific processing
│   │   ├── servicenow_models.py
│   │   ├── servicenow_sync.py  # ServiceNow synchronization
│   │   └── servicenow_live_api.py
│   │
│   └── routes/
│       ├── index.py            # /index/* routes
│       ├── search.py           # /search/* routes
│       ├── files.py            # /files/* routes
│       ├── libraries.py        # /libraries/* routes
│       ├── servicenow.py       # /servicenow/* routes
│       └── finance.py          # /finance/* routes
│
├── all_indexes/                # Library storage (generated)
│   └── <library_id>/
│       ├── source_files/       # Original files
│       ├── source_files_archive/
│       ├── md_files/           # Converted Markdown files
│       ├── index/              # FAISS vector index
│       ├── .groups.json        # Access control
│       └── .indexing_status    # Indexing status
│
├── scripts/
│   └── epfl-hierarchical-scraper.js  # EPFL page scraper
│
├── .env                        # Environment variables
├── requirements.txt            # Python dependencies
└── README.md
```

---

## 🚀 Getting Started

### Development Mode

```bash
# Activate virtual environment
source venv/bin/activate

# Start the server
python -m src.main
```

The server starts at `http://localhost:8079`

### Production Mode (with Uvicorn)

```bash
uvicorn src.main:app --host 0.0.0.0 --port 8079 --workers 4
```

### API Documentation

Once the server is running, access:
- **Swagger UI**: http://localhost:8079/docs
- **ReDoc**: http://localhost:8079/redoc

---

## 🔌 API Endpoints

### Indexing

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/index/{index_id}` | Create/update an index |
| `GET` | `/index/{index_id}/status` | Get indexing status |

**Example - Create an index:**

```bash
curl -X POST "http://localhost:8079/index/my_library" \
  -H "X-API-Key: your_internal_api_key" \
  -F "files=@document1.pdf" \
  -F "files=@document2.docx" \
  -F "groups=[\"group1\", \"group2\"]"
```

### Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/search/{index_id}` | Search within an index |

**Example - Search:**

```bash
curl -X POST "http://localhost:8079/search/my_library" \
  -H "X-API-Key: your_internal_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How to configure VPN?",
    "user_groups": ["staff"],
    "top_k": 10,
    "rerank": true
  }'
```

### Files

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/files/{index_id}/{filename}` | Download a source file |

### Libraries

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/libraries/?user_groups=group1,group2` | List accessible libraries |

### ServiceNow

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/servicenow/ingest` | Ingest ServiceNow KBs |
| `POST` | `/servicenow/live-search` | Live ServiceNow search |

### Finance (Hybrid)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/finance/search` | Hybrid search (LEX + ServiceNow) |

---

## 🕷️ Web Scraping

The scraper crawls EPFL web pages and prepares them for indexing.

### Usage

```bash
node scripts/epfl-hierarchical-scraper.js <LIBRARY_NAME> [url1] [url2] ...
```

**Example:**

```bash
node scripts/epfl-hierarchical-scraper.js EPFL_CAMPUS \
  "https://www.epfl.ch/campus/" \
  "https://www.epfl.ch/about/"
```

Files will be saved to `all_indexes/EPFL_CAMPUS/source_files/`.

### Scraper Configuration

The scraper requires EPFL credentials in `.env`:

```env
EPFL_USERNAME_TEQUILA=username
EPFL_USERNAME_MICROSOFT=username@epfl.ch
EPFL_PASSWORD=password
```

---

## 🔧 Troubleshooting

### Error: "INTERNAL_API_KEY not set"

Make sure the `INTERNAL_API_KEY` variable is defined in `.env` and the file is being loaded.

### Embeddings Error

Verify that:
1. `RCP_API_ENDPOINT` is accessible
2. `RCP_API_KEY` is valid
3. The model `RCP_QWEN_EMBEDDING_MODEL` exists

### Index Not Found

Check that:
1. The folder `all_indexes/<index_id>` exists
2. The `index/` subfolder contains FAISS files

### Verbose Logging

```bash
# Enable DEBUG logs
export LOG_LEVEL=DEBUG
python -m src.main
```

---

## 📄 License

Internal EPFL project - All rights reserved.

---

## 👥 Contact

For any questions, contact the LEX team.
