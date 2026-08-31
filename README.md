# CRM Analytics Engine

Analyze CRM campaign exports, compute campaign metrics, and generate executive reports with FastAPI, Next.js, and Amazon Bedrock.

## Local setup

Requires Python 3.10+, Node.js, and AWS Bedrock access.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cd frontend
npm ci
cd ..
```

Configure AWS access locally through environment variables or an untracked `.env` file. See `crm_intelligence/config.py` for supported settings. Never commit credentials or customer datasets.

Start both services with `./start.ps1`, or run each service separately:

```powershell
uvicorn api.main:app --reload --port 8000
```

```powershell
cd frontend
npm run dev
```

The UI runs at http://localhost:3000 and API documentation at http://localhost:8000/docs.

See `CRM_Intelligence_Engine_Architecture.md` and `PROJECT_CONTEXT.md` for implementation details. Local datasets, generated reports, and deployment storage are excluded from Git.

## Repository history

This repository was imported from an existing source snapshot in November 2026. Its initial commits group that snapshot by feature and use reconstructed July–August 2026 dates; those dates are not a record of the original development timeline.
