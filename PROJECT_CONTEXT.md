# CRM Intelligence Engine — Complete Project Context

> This document is the single source of truth for any AI or developer continuing work on this project. It covers architecture, every module, all API contracts, data flow, LLM integration, storage, frontend, configuration, design decisions, and pending work.

---

## 1. What This Product Does

The CRM Intelligence Engine is a standalone product that:
1. Accepts raw CRM platform exports (CSV/XLSX from CleverTap, MoEngage planned)
2. Computes deterministic analytics (40+ metrics — CTR, CTOR, delivery rates, day patterns, channel splits, rankings)
3. Calls Claude Opus 4.6 via Amazon Bedrock for AI classification (L1) and narration (L2)
4. Generates professional executive CRM Intelligence Reports as DOCX files
5. Supports period-over-period comparison with AI analysis
6. Full-stack UI: Next.js 14 frontend + FastAPI backend

**Core Principle:** The LLM NEVER computes numbers. Every statistic is deterministically computed in Python. The LLM only classifies messages and narrates pre-computed facts.

---

## 2. Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, FastAPI, Pydantic v2 |
| LLM | Claude Opus 4.6 via Amazon Bedrock (boto3 converse API) |
| Analytics | pandas, pure Python computation |
| Report | python-docx for DOCX generation |
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, class-variance-authority |
| Storage | Flat JSON files (migration to PostgreSQL planned) |
| Auth | None yet (planned) |
| Deployment | Not yet deployed (planned) |

**Dependencies (pyproject.toml):**
```
pandas>=2.0, openpyxl>=3.1, pydantic>=2.0, python-dotenv>=1.0,
python-docx>=1.0, boto3>=1.34, fastapi>=0.111, uvicorn[standard]>=0.29,
python-multipart>=0.0.9
```

**Frontend (package.json key deps):**
```
next@14, react@18, tailwindcss, class-variance-authority, lucide-react, clsx, tailwind-merge
```

---

## 3. Project Structure

```
Analytics_Engine/
├── .env                          # AWS credentials (NEVER commit)
├── pyproject.toml                # Python project config
├── crm_intelligence/             # Core engine (importable package)
│   ├── __init__.py               # Version: 0.1.0
│   ├── __main__.py               # CLI entry: python -m crm_intelligence
│   ├── main.py                   # Orchestrator — runs the 8-step pipeline
│   ├── config.py                 # All env vars and paths
│   ├── sections.py               # Section Registry (control plane)
│   ├── scanner.py                # Data scanner (detects capabilities from CSV)
│   ├── logging_config.py         # Structured logging setup
│   ├── adapters/
│   │   ├── __init__.py           # adapt_file() dispatcher
│   │   ├── clevertap.py          # CleverTap CSV/XLSX → CanonicalCampaign
│   │   └── registry.py           # Platform detection
│   ├── analytics/
│   │   ├── __init__.py           # Exports compute_facts()
│   │   └── engine.py             # Deterministic metric computation
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py             # Bedrock wrapper (ONLY file talking to AWS)
│   │   ├── classifier.py         # L1: message classification (temp=0)
│   │   ├── narrator.py           # L2: narrative generation (temp=0.3)
│   │   └── merge.py              # Merge L1 classifications back into Facts
│   ├── models/
│   │   ├── __init__.py
│   │   ├── campaign.py           # CanonicalCampaign (Pydantic model)
│   │   ├── facts.py              # Facts, OverallMetrics, ChannelMetrics, etc.
│   │   ├── profile.py            # BusinessProfile, VerticalProfile
│   │   └── run.py                # Run metadata model
│   ├── renderer/
│   │   ├── __init__.py           # Exports render_report()
│   │   └── docx_report.py        # DOCX builder (python-docx)
│   └── storage/
│       ├── __init__.py           # Exports all CRUD functions
│       └── store.py              # JSON file-based storage
├── api/                          # FastAPI web layer
│   ├── __init__.py
│   ├── main.py                   # FastAPI app, CORS, router mounts
│   └── routes/
│       ├── __init__.py
│       ├── profiles.py           # Brand CRUD + verticals
│       ├── reports.py            # List/get/delete/download reports
│       ├── generate.py           # Upload + SSE pipeline streaming
│       ├── sections.py           # Section registry endpoint
│       ├── settings.py           # App settings
│       └── compare.py            # Report comparison + DOCX export
├── frontend/                     # Next.js 14 app
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── src/
│       ├── app/
│       │   ├── layout.tsx        # Root layout with sidebar
│       │   ├── page.tsx          # Dashboard (brand cards + recent reports)
│       │   ├── generate/page.tsx # 4-step generation flow
│       │   ├── brands/
│       │   │   ├── page.tsx      # Brand list
│       │   │   ├── new/page.tsx  # Create brand
│       │   │   └── [name]/page.tsx # Edit brand + verticals
│       │   ├── reports/
│       │   │   ├── page.tsx      # Reports list (with compare selection)
│       │   │   └── [runId]/page.tsx # Report detail (in-browser view)
│       │   ├── compare/page.tsx  # Comparison result view
│       │   ├── comparisons/page.tsx # Past comparisons list
│       │   └── settings/page.tsx # Settings page
│       ├── components/
│       │   ├── sidebar.tsx       # Navigation sidebar
│       │   ├── logo.tsx          # Attributics logo (SVG)
│       │   └── ui/              # Reusable components (button, badge, card, input)
│       ├── hooks/
│       │   └── use-generation.ts # SSE streaming hook for pipeline progress
│       └── lib/
│           ├── api.ts            # Full API client (typed, all endpoints)
│           └── utils.ts          # cn() utility for classnames
├── storage/                      # Flat-file data store
│   ├── profiles/                 # {company-slug}.json
│   ├── runs/                     # {run_id}.json
│   ├── facts/                    # {run_id}_facts.json
│   ├── insights/                 # {run_id}_insights.json
│   ├── comparisons/              # {comparison_id}.json + .docx
│   └── uploads/                  # Temp uploaded files (cleaned after pipeline)
├── output/                       # Generated DOCX reports
└── data/                         # Input data directory
```

---

## 4. The Pipeline (8 Steps)

The orchestrator (`crm_intelligence/main.py`) runs these steps sequentially:

```
Step 1: Load/create business profile
Step 2: Adapt file (CleverTap adapter → CanonicalCampaign objects)
Step 3: Compute deterministic analytics (→ Facts object)
Step 4: L1 Classification (LLM call #1, temp=0) — classify messages
Step 5: Merge classifications back into Facts
Step 6: L2 Narration (LLM call #2, temp=0.3) — generate insights
Step 7: Render DOCX report
Step 8: Persist everything (run metadata, facts, insights)
```

**Key constraints:**
- Exactly 2 LLM calls maximum per report generation
- L1 is skipped if no selected sections need classification
- L2 is skipped if no selected sections need narration
- progress_callback fires after each step (for SSE streaming)
- Pipeline is run in a ThreadPoolExecutor when invoked via API (FastAPI is async)

---

## 5. Data Models

### 5.1 CanonicalCampaign (the Data Contract)

Every adapter MUST produce this. The analytics layer ONLY consumes this.

```python
class CanonicalCampaign(BaseModel):
    campaign_name: str        # Full campaign name
    channel: str              # "WhatsApp" | "Push Notification" | "RCS" | "Email" | "SMS"
    segment: str              # Target segment
    start_date: date          # Send date
    start_time: time          # Send time (24h)
    estimated_reach: int      # Target audience size
    sent: int                 # Total sent
    delivered: int            # Total delivered
    viewed: int               # Total viewed/opened
    clicked: int              # Total clicked
    click_conversions: int    # Direct conversions
    influenced_conversions: int # Attributed conversions
    message: str              # Full message body (required for creative intelligence)
    # Optional:
    title: Optional[str]      # Push notification title
    labels: Optional[str]     # Pipe-separated tags: "eoss|jeans|sale"
    errors: Optional[int]     # Delivery failures
    revenue: Optional[float]  # Revenue attributed
```

### 5.2 BusinessProfile

Stores brand context that feeds into LLM prompts:

```python
class BusinessProfile(BaseModel):
    company_name: str
    industry: str
    business_model: Optional[str]
    description: Optional[str]
    brand_positioning: Optional[str]
    products_services: Optional[str/list]
    target_audience: Optional[str/list]
    website: Optional[str]
    crm_platforms: list[str]
    marketing_strategy: Optional[str]
    communication_goals: Optional[str]
    retention_strategy: Optional[str]
    brand_voice: Optional[str]
    business_constraints: Optional[str]
    kpis: Optional[str/list]
    selected_sections: list[str]       # Default sections for this brand
    ranking_metric: str                 # "composite" (default)
    performers_count: int               # Top/bottom N (default 5)
    offer_extraction_pattern: Optional[str]  # e.g. "PROGRAM_CHANNEL_OFFER_DATE"
    label_separator: str                # Default "|"
    verticals: list[VerticalProfile]
    observations: list[str]             # Business-specific notes
```

### 5.3 VerticalProfile

```python
class VerticalProfile(BaseModel):
    name: str                           # e.g. "HFRP", "E-commerce"
    code: str                           # e.g. "HFRP", "ECOM"
    business_objective: Optional[str]
    primary_kpi: Optional[str]
    typical_cta: Optional[str]
    target_audience: Optional[str]
    success_metrics: Optional[str/list]
    notes: Optional[str]
```

### 5.4 Facts (Analytics Output)

```python
class Facts(BaseModel):
    meta: AnalysisMeta         # Company, vertical, date range, campaign count, channels
    overall: OverallMetrics    # Total sent/delivered/viewed/clicked/conversions + rates
    by_channel: list[ChannelMetrics]
    by_offer: list[OfferMetrics]
    by_segment: list[SegmentMetrics]
    by_day: list[TimingMetrics]         # Monday through Sunday
    by_hour: list[TimingMetrics]        # 7 time buckets (00-06, 06-09, ..., 21-24)
    by_label: list[LabelMetrics]        # Tag-based grouping
    # L1-classified (populated after merge):
    by_opening_style: list[ClassifiedMetrics]
    by_tone: list[ClassifiedMetrics]
    by_headline_quality: list[ClassifiedMetrics]
    by_cta_strength: list[ClassifiedMetrics]
    by_emoji_bucket: list[ClassifiedMetrics]
    by_keyword: list[KeywordMetrics]
    by_message_structure: list[ClassifiedMetrics]
    by_message_length: list[ClassifiedMetrics]
    # Rankings:
    top_performers: list[CampaignHighlight]
    bottom_performers: list[CampaignHighlight]
    comparison: Optional[TrendComparison]  # vs prior run
```

### 5.5 Run (Pipeline Execution Metadata)

```python
class Run(BaseModel):
    run_id: str                # 8-char UUID prefix
    company: str
    vertical_code: str
    source_platform: str       # "clevertap"
    source_filename: str
    campaign_count: int
    channels: list[str]
    date_range_start: Optional[str]
    date_range_end: Optional[str]
    status: RunStatus          # "running" | "complete" | "failed"
    error_message: Optional[str]
    facts_path: Optional[str]
    report_path: Optional[str]
    insights_path: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
```

---

## 6. LLM Integration (Bedrock)

### 6.1 Client (`crm_intelligence/llm/client.py`)

- **ONLY file that talks to AWS.** Everything else uses `call_claude()` or `call_claude_json()`.
- Auth: `AWS_BEARER_TOKEN_BEDROCK` env var (Bedrock API key). Loaded via python-dotenv into os.environ, boto3 picks it up.
- Model: `us.anthropic.claude-opus-4-6-v1` (configurable via `BEDROCK_MODEL_ID`)
- Uses `bedrock-runtime` client with `converse` API (NOT the messages API)
- Retry: exponential backoff, max 3 attempts. Throttling and transient errors retry; validation errors don't.
- JSON extraction: handles code fences, finds first `{` to last `}`, graceful fallback.
- Token tracking: module-level `usage` object accumulates across the run.

### 6.2 L1 Classifier (`crm_intelligence/llm/classifier.py`)

- **Temperature: 0.0** (deterministic classification)
- Classifies each campaign message along 8 dimensions:
  1. `opening_style`: personalized_greeting, question, urgency, benefit_lead, emotional, announcement, direct
  2. `tone`: emotional, transactional, aspirational, urgency, informational, playful
  3. `headline_quality`: strong, moderate, weak
  4. `cta_strength`: strong, moderate, weak, absent
  5. `emoji_bucket`: heavy, moderate, minimal, none
  6. `keywords`: 2-3 theme keywords extracted from message
  7. `message_structure`: header_body_cta, body_cta, greeting_body_cta, single_block, multi_section
  8. `message_length`: short, medium, long
- **Dynamic prompt building**: only requests dimensions needed by selected sections (saves tokens)
- Batching: campaigns are sent in batches of `MAX_CAMPAIGNS_PER_LLM_BATCH` (default 50)
- Graceful fallback: if LLM fails for a batch, returns safe defaults (direct/transactional/moderate)
- Strict taxonomy validation: any off-taxonomy label gets corrected to default

### 6.3 L2 Narrator (`crm_intelligence/llm/narrator.py`)

- **Temperature: 0.3** (slightly creative but grounded)
- Receives: computed Facts + BusinessProfile + VerticalProfile
- Produces: NarratedInsights object with structured sections
- **Dynamic prompt**: only requests narrative for selected sections
- Output fields:
  - `executive_summary`: 2-3 paragraphs
  - `channel_insights`: per-channel narrative with verdict
  - `offer_insights`: per-offer narrative with verdict
  - `creative_insights`: opening_style, tone, cta, headline quality narratives
  - `timing_insights`: best days, best hours, recommendation
  - `keyword_insights`, `emoji_insights`, `message_structure_insights`
  - `label_insights`: per-label narrative
  - `top_performer_analysis`, `bottom_performer_analysis`
  - `recommendations`: prioritized list with action, expected_impact, rationale
  - `trend_commentary`: comparison vs prior period (if available)

### 6.4 Merge (`crm_intelligence/llm/merge.py`)

After L1 classifies campaigns, this module:
1. Maps each classification back to its campaign
2. Aggregates by classification dimension (e.g., all "urgency" tone campaigns → CTR, CTOR, conversions)
3. Populates the empty `by_opening_style`, `by_tone`, etc. fields in Facts
4. Aggregates keywords across all campaigns

---

## 7. Section Registry (`crm_intelligence/sections.py`)

The Section Registry is the **control plane** of the report. It declares:
- What data each section needs (capabilities from the file scan)
- Whether it needs L1 classification
- Which L1 dimensions it requires
- Whether it needs L2 narration

```
Registered sections:
- performers          (always available, no L1)
- timing              (always available, no L1)
- recommendations     (always available, no L1)
- channel_performance (requires: multiple_channels)
- offer_analysis      (requires: offer_extraction)
- label_analysis      (requires: labels)
- creative_intelligence (requires: messages, L1 dims: opening_style, tone, headline_quality, cta_strength)
- keywords            (requires: messages, L1 dims: keywords)
- emoji               (requires: messages, L1 dims: emoji_bucket)
- message_structure   (requires: messages, L1 dims: message_structure, message_length)
```

The pipeline uses this to:
1. Show available sections to the user based on file scan
2. Skip L1/L2 when no selected sections need them
3. Build minimal LLM prompts (fewer dimensions = fewer tokens)

---

## 8. CleverTap Adapter

The adapter (`crm_intelligence/adapters/clevertap.py`) handles:
- **Column aliasing**: Maps 20+ variant column names to canonical form (handles narrow 29-col format, wide 121-col format, compact 19-col format)
- **Date parsing**: Handles M/D/YYYY, DD/MM/YYYY, ISO, Excel serial numbers, datetime objects
- **Time parsing**: Handles HH:MM, HH:MM:SS, 12h format, Excel day-fractions
- **Channel standardization**: Maps "WA" → "WhatsApp", "PN" → "Push Notification", etc.
- **Platform rule**: For Push Notification, CleverTap reports Delivered=0 always; uses Viewed as proxy
- **Multi-sheet XLSX**: Auto-picks the best sheet (priority: "raw_data" → "performance" → "data" → first)
- **Labels**: Parses pipe-separated label values, filters out "nan"/"n/a"/"none"
- **Graceful error handling**: Skips bad rows, logs errors, continues processing

**Detection**: `is_clevertap_export(columns)` checks for signature columns: "Campaign Name" + "Total Sent(users)" + "Total Clicked(users)"

---

## 9. Analytics Engine

The engine (`crm_intelligence/analytics/engine.py`) computes:

1. **Overall metrics**: total sent/delivered/viewed/clicked/conversions + rates (CTR, CTOR, delivery, CVR)
2. **By channel**: same metrics grouped by channel
3. **By offer**: grouped by extracted offer type (from campaign name pattern)
4. **By label**: grouped by campaign tags/categories
5. **By segment**: grouped by target segment
6. **By day of week**: Monday through Sunday (sorted chronologically, not alphabetically)
7. **By hour bucket**: 7 buckets (00-06, 06-09, 09-12, 12-15, 15-18, 18-21, 21-24)
8. **Top/bottom performers**: composite score = 40% CTR + 30% CTOR + 30% CVR(influenced)
9. **Trend comparison**: delta vs prior run (CTR change, conversion change)

**Key**: `_rate(numerator, denominator)` returns 0.0 on division by zero. Never produces NaN.

**Conditional computation**: sections the user didn't select are skipped (e.g., if "channel_performance" not selected, `by_channel` stays empty).

---

## 10. DOCX Renderer

`crm_intelligence/renderer/docx_report.py` builds a professional Word document using python-docx:

- Title page with company/vertical/date range
- Executive Summary
- Overall Metrics table
- Channel Performance (if multi-channel)
- Timing Analysis (day-of-week + hour tables)
- Offer/Label Analysis
- Creative Intelligence (opening style, tone, CTA, headline quality)
- Keywords, Emoji, Message Structure
- Top/Bottom Performers (with message text and metrics)
- Recommendations (numbered, with expected impact)
- Footer

**Conditional rendering**: only renders sections the user selected.

---

## 11. API Layer (FastAPI)

### 11.1 Application Setup (`api/main.py`)

```python
app = FastAPI(title="CRM Intelligence Engine", version="0.1.0")
# CORS for Next.js: localhost:3000
# Routers: profiles, reports, generate, sections, settings, compare
```

### 11.2 Endpoints

**Profiles (CRUD)**
```
GET    /api/profiles                         → {profiles: ProfileSummary[]}
GET    /api/profiles/{company_name}          → ProfileFull
POST   /api/profiles                         → {status, company_name}
PUT    /api/profiles/{company_name}          → {status}
DELETE /api/profiles/{company_name}          → {status}
POST   /api/profiles/{company}/verticals     → {status}
PUT    /api/profiles/{company}/verticals/{code} → {status}
DELETE /api/profiles/{company}/verticals/{code} → {status}
```

**Reports**
```
GET    /api/reports                           → {reports: ReportSummary[], total}
       ?company=X&vertical=Y&limit=N
GET    /api/reports/{run_id}                  → {run, facts_summary, insights_summary}
DELETE /api/reports/{run_id}                  → {status, run_id}
GET    /api/reports/{run_id}/download         → FileResponse (DOCX)
```

**Generate (SSE streaming)**
```
POST   /api/generate/upload                   → {upload_id, filename, platform, data_profile, available_sections, default_sections}
       (multipart file upload)
POST   /api/generate/run                      → StreamingResponse (SSE)
       (form: upload_id, company, vertical_code, sections)
       Events: "step" (progress), "complete" (success), "error" (failure)
```

**Sections**
```
GET    /api/sections                          → {sections: SectionDef[]}
```

**Compare**
```
POST   /api/compare                           → ComparisonResult (creates or returns cached)
       Body: {run_id_a, run_id_b}
GET    /api/compare                           → {comparisons: ComparisonSummary[], total}
       ?limit=N
GET    /api/compare/{comparison_id}           → ComparisonResult
DELETE /api/compare/{comparison_id}           → {status}
GET    /api/compare/{comparison_id}/download  → FileResponse (DOCX)
```

**Settings & Health**
```
GET    /api/settings                          → {settings object}
PUT    /api/settings                          → {status}
GET    /api/health                            → {status: "healthy", ...}
```

### 11.3 SSE Progress Streaming

The generation endpoint uses a critical pattern for real-time progress:
1. Pipeline runs in a `ThreadPoolExecutor` (blocking Python code)
2. `progress_callback` bridges to an `asyncio.Queue` via `loop.call_soon_threadsafe()`
3. The async generator awaits the queue and yields SSE events immediately
4. Initial 2KB comment flushes browser read buffers (Chrome/Edge hold first 2-4KB)
5. Events: `event: step\ndata: {"step": N, "total": 8, "message": "...", "status": "running"}\n\n`
6. Final: `event: complete\ndata: {"run_id": "...", "report_path": "..."}\n\n`

---

## 12. Comparison System (`api/routes/compare.py`)

### Flow:
1. POST `/api/compare` with two run_ids
2. Validates same brand (rejects cross-brand)
3. Orders by `date_range_start` (NOT `created_at` — user may generate older reports later)
4. Checks cache: deterministic ID = md5(sorted_pair)[:12]
5. If not cached: loads facts + insights for both, calls LLM (temp=0.3)
6. Caches result as JSON
7. DOCX download generates on first request, then cached

### Comparison LLM Output:
```json
{
  "summary": "Executive summary of what changed",
  "metrics_delta": {ctr_change, ctor_change, conversion_change, sent_change, delivery_rate_change},
  "improvements": ["what got better"],
  "declines": ["what got worse"],
  "strategy_shifts": ["notable changes in approach"],
  "recommendation": "One actionable recommendation",
  "context_note": "Comparability note (if periods differ significantly)"
}
```

---

## 13. Frontend Architecture

### 13.1 Routing (Next.js 14 App Router)

```
/                    → Dashboard (brand cards + recent reports)
/generate            → 4-step flow: upload → configure → progress → results
/brands              → Brand list
/brands/new          → Create brand
/brands/[name]       → Edit brand + manage verticals
/reports             → Reports list (with multi-select comparison)
/reports/[runId]     → Report detail (in-browser rendered view)
/compare?a=X&b=Y    → Comparison result view
/comparisons         → Past comparisons list
/settings            → App settings
```

### 13.2 API Client (`frontend/src/lib/api.ts`)

All requests go through `request<T>(path, options)` which prepends `/api`, sets JSON headers, and throws on non-200 with parsed error detail.

Next.js `rewrites` in `next.config.js` proxy `/api/*` to FastAPI at `localhost:8000`.

### 13.3 SSE Hook (`frontend/src/hooks/use-generation.ts`)

Custom hook for report generation:
- Uses `fetch()` + `ReadableStream` (not EventSource — POST body required)
- Parses SSE protocol manually (handles multi-line data, event types)
- Returns: `{steps, currentStep, status, error, runId, startGeneration}`
- States: idle → running → complete | error

### 13.4 UI Components

- **Sidebar**: Fixed left nav with Dashboard, Reports, Comparisons, Brands, Settings
- **Button/Badge/Card/Input**: CVA-based reusable components (no component library — all custom)
- **Logo**: Inline SVG Attributics logo

### 13.5 Key Frontend Patterns

- All pages are client components (`"use client"`) — state-heavy
- Loading states use skeleton pulse animations
- Error states show AlertTriangle icon + message + back button
- Delete confirmations use `window.confirm()`
- Color coding: emerald for positive, red for negative, muted for neutral
- Typography: 2xs (10px) for labels, xs (12px) for body, sm (14px) for emphasis

---

## 14. Storage Architecture (Current: Flat JSON)

```
storage/
├── profiles/{company-slug}.json     # BusinessProfile (Pydantic serialized)
├── runs/{run_id}.json               # Run metadata
├── facts/{run_id}_facts.json        # Computed analytics
├── insights/{run_id}_insights.json  # LLM narrative output
├── comparisons/{id}.json            # Comparison results
├── comparisons/{id}.docx            # Cached comparison DOCX
└── uploads/{upload_id}.xlsx         # Temp (cleaned after pipeline)
```

**Atomic writes**: All saves write to a temp file then rename (prevents corruption on crash).

**Planned migration**: PostgreSQL with SQLAlchemy 2.0 + Alembic. Models: User, Brand, Vertical, Run, Facts (JSONB), Insights (JSONB), Comparison. Generated DOCX files stay on disk.

---

## 15. Configuration (`.env`)

```env
AWS_BEARER_TOKEN_BEDROCK=<base64 Bedrock API key>
AWS_REGION=us-east-1
BEDROCK_MODEL_ID=us.anthropic.claude-opus-4-6-v1
```

**CRITICAL**: `AWS_BEARER_TOKEN_BEDROCK` must NEVER be committed to git or exposed via frontend. The `.env` is gitignored.

Additional config in `config.py`:
```python
MIN_CAMPAIGNS_FOR_ANALYSIS = 5   # Minimum campaigns to run pipeline
MAX_CAMPAIGNS_PER_LLM_BATCH = 50 # Batch size for L1 classification
RANKING_TOP_N = 5                 # Top/bottom performer count
LLM_CLASSIFY_TEMPERATURE = 0.0   # L1 temp (deterministic)
LLM_NARRATE_TEMPERATURE = 0.3    # L2 temp (slightly creative)
LLM_MAX_RETRIES = 2              # Retry attempts on API failure
```

---

## 16. Running the Project

### Backend (FastAPI):
```bash
cd Analytics_Engine
pip install -e .
uvicorn api.main:app --reload --port 8000
```

### Frontend (Next.js):
```bash
cd Analytics_Engine/frontend
npm install
npm run dev    # Port 3000, proxies /api to :8000
```

### CLI (standalone, no web):
```bash
cd Analytics_Engine
python -m crm_intelligence.main data/export.xlsx --company "Levi's" --vertical ECOM --sections performers,timing,recommendations
```

---

## 17. Design Decisions & Rationale

1. **2 LLM calls max**: Classification (temp=0) is deterministic and factual. Narration (temp=0.3) is slightly creative but grounded. Separating them ensures numbers are never hallucinated.

2. **Flat JSON over DB (current)**: Simpler for single-user development. Every artifact is human-readable. Migration to PostgreSQL is planned for multi-user/deployment.

3. **Section Registry as control plane**: Adding a new section means registering it once — the entire pipeline (scanner, classifier, narrator, renderer) adapts automatically.

4. **Adapter pattern**: Only CleverTap exists today. MoEngage adapter would implement the same interface (produce `CanonicalCampaign` list). No code changes needed upstream.

5. **Composite ranking score (40% CTR + 30% CTOR + 30% CVR)**: Prevents campaigns with high CTR but zero conversions from dominating rankings.

6. **Period ordering by date_range_start, not created_at**: Users may generate reports out of chronological order (e.g., March first, then January for comparison).

7. **Comparison cache with deterministic IDs**: `md5(sorted_pair)[:12]` ensures the same two reports always map to the same comparison, regardless of which was passed as A vs B.

8. **SSE over WebSocket**: Simpler for unidirectional progress. No connection management. Works with standard HTTP infrastructure.

9. **No LangChain/LangGraph**: Direct boto3 converse API calls. Fewer dependencies, full control over retry/parsing, no abstraction overhead.

10. **DOCX over PDF**: Clients expect editable reports. DOCX is the standard deliverable format in the marketing industry.

---

## 18. Existing Data (Real Test Cases)

### Brands configured:
1. **Club Mahindra** — Travel & Hospitality, vacation ownership. 5 verticals: HFRP (referrals), OCCUPANCY, FHP (first holiday), ASF (annual fee), EMI (installments). Full creative intelligence enabled.
2. **Levi's** — Apparel retail, D2C. 4 verticals: ECOM, LOYALTY, RETAIL, SEASONAL. Performers + timing + label analysis enabled.

### Completed runs:
- `1173a7d0`: Levi's ECOM, 114 Push campaigns, Jan-Dec 2026, CTR 0.29%, 17,268 conversions
- `5aa8265c`: Club Mahindra HFRP, 25 campaigns (5 channels), March 2026, CTR 2.24%
- `9ce41fd6`: Club Mahindra HFRP, 36 campaigns (3 channels), May 2026, CTR 1.07%

### Completed comparisons:
- `04db136b4ba6`: Club Mahindra HFRP March vs May — detected severe performance collapse (CTR -52%, conversions -84%) driven by Email channel removal

---

## 19. Pending Work & Known Issues

### Immediate next steps (in priority order):
1. **PostgreSQL integration** — Replace flat JSON files with proper DB (SQLAlchemy + Alembic)
2. **Authentication** — User model, JWT/session auth, protected routes
3. **Deployment** — Containerize (Docker), deploy backend + frontend

### Feature backlog:
- MoEngage adapter (second CRM platform support)
- Comparison from report detail page header (third entry point)
- Trend tracking across 3+ reports (line charts over time)
- Auto-invalidate comparison cache when a source report is deleted
- Comparison section embedded in main DOCX report
- Dashboard aggregate metrics and trend indicators
- Observations/learnings auto-extraction (brand gets smarter over time)

### Task #20 (pending since early build):
- End-to-end validation with both Club Mahindra and Levis data (confirming pipeline produces valid output with real exports)

---

## 20. Security Notes

- `AWS_BEARER_TOKEN_BEDROCK` is the only secret. It's in `.env` (gitignored).
- No user authentication exists yet. The entire API is open.
- File uploads are stored temporarily and cleaned after pipeline completion.
- No input sanitization beyond Pydantic validation (add before deployment).
- CORS is configured for `localhost:3000` only (update for production domain).
- The Bedrock API key format is `ABSK...` base64 — it's a Bedrock-specific API key, not IAM credentials.

---

## 21. Important Patterns for Continuation

### Adding a new report section:
1. Register in `sections.py` with requirements
2. Add analytics computation in `engine.py` (if new aggregation needed)
3. Add L1 dimension in `classifier.py` (if needs classification)
4. Add narrative block in `narrator.py` system prompt
5. Add DOCX rendering in `docx_report.py`
6. Done — scanner, pipeline, and UI auto-adapt

### Adding a new CRM platform adapter:
1. Create `crm_intelligence/adapters/{platform}.py`
2. Implement `adapt(filepath: Path) -> AdapterResult`
3. Add detection function: `is_{platform}_export(columns) -> bool`
4. Register in `crm_intelligence/adapters/registry.py`
5. Done — the rest of the pipeline is platform-agnostic

### API response format convention:
- Lists return: `{items: [...], total: N}`
- Single item returns the object directly
- Errors return: `{"detail": "Human-readable error message"}`
- DELETE returns: `{"status": "deleted", "id": "..."}`

### Frontend API pattern:
- All API calls go through typed functions in `src/lib/api.ts`
- Errors are caught and displayed via `alert()` or inline error state
- Loading states use skeleton pulse, never spinners (except generation)

---

## 22. How to Start the Backend & Frontend Together

```bash
# Terminal 1: Backend
cd Z:\Attributics\Analytics_Engine
.venv\Scripts\activate
uvicorn api.main:app --reload --port 8000

# Terminal 2: Frontend
cd Z:\Attributics\Analytics_Engine\frontend
npm run dev
```

Open `http://localhost:3000` — the frontend proxies all `/api/*` calls to `:8000`.

---

*Last updated: 2026-08-17*
*Version: 0.1.0*
*Status: Feature-complete for v1 scope. Pending: DB, Auth, Deploy.*
