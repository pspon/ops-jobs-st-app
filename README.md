# OPS Jobs Explorer

A Streamlit app for browsing and filtering [Ontario Public Service (OPS)](https://www.ontario.ca/page/ontario-public-service) job postings sourced from [gojobs.gov.on.ca](https://www.gojobs.gov.on.ca).

Live app: **https://opsjobs.streamlit.app/**

---

## Features

| Feature | Description |
|---|---|
| **Salary filter** | Slide to narrow by annualised salary range. Hourly/weekly/monthly rates are automatically converted to annual equivalents. |
| **Date range picker** | Show only postings closing within a chosen window (default: next 4 weeks). |
| **Organization filter** | Narrow to a specific ministry or agency. |
| **Location search** | Case-insensitive substring match on the Location field. |
| **Job title keyword search** | Up to 5 keywords combinable with AND / OR / NOT boolean logic. |
| **Extended data** | Unlock Division, Address, and Job Code columns (and their filters) via the *Show Extended Data* toggle. |
| **TDA / Restricted toggle** | Switch between open postings and postings restricted to existing OPS employees. |
| **Internal URLs** | Swap public `gojobs.gov.on.ca` links for internal intranet URLs (useful on-network). |
| **Inflation-adjusted salaries** | Re-express historical salaries in present-day purchasing power using Canadian CPI data (2008–2025). |
| **Job ID picker** | Pin specific postings after all other filters are applied. |
| **Metrics row** | At-a-glance counts — jobs found, average salary min/max, postings closing within 7 days. |
| **Download CSV** | Export the current filtered results as a CSV file. |
| **Interactive charts** | Jobs by closing date, salary distribution, and top 10 organizations — all rendered with Plotly. |

---

## Data Sources

Job data is stored in a **private** GitHub repository as CSV and Parquet files across three temporal tiers:

| Tier | Description |
|---|---|
| Current | Most recently scraped postings |
| Recent | Postings from the past few weeks |
| Historical | Older archived postings |

Each tier has a *core* file (basic job fields) and an *extended* (EXT) file (additional fields such as Division and Address). The app left-joins them on `Job ID` at load time and caches the result for one hour.

Credentials and file URLs are supplied at runtime via [Streamlit Secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

---

## Local Development

### Prerequisites

- Python 3.11+
- A `.streamlit/secrets.toml` file with the required secrets (see below)

### Setup

```bash
git clone https://github.com/pspon/ops-jobs-st-app.git
cd ops-jobs-st-app
pip install -r requirements.txt
streamlit run app.py
```

The app will be available at `http://localhost:8501`.

### Required Secrets

Create `.streamlit/secrets.toml` with the following keys:

```toml
GITHUB_TOKEN        = "ghp_..."          # PAT with read access to the data repo
REPO_OWNER          = "..."
REPO_NAME           = "..."
BRANCH              = "main"
DIRECTORY           = "data"

CURRENT_CSV_URL     = "https://raw.githubusercontent.com/..."
RECENT_CSV_URL      = "https://raw.githubusercontent.com/..."
HISTORICAL_CSV_URL  = "https://raw.githubusercontent.com/..."

CURRENT_EXT_URL     = "https://raw.githubusercontent.com/..."
RECENT_EXT_URL      = "https://raw.githubusercontent.com/..."
HISTORICAL_EXT_URL  = "https://raw.githubusercontent.com/..."

MIN_SALARY          = 60000   # Default lower bound of the salary slider
MAX_SALARY          = 120000  # Default upper bound of the salary slider
```

---

## Project Structure

```
ops-jobs-st-app/
├── app.py                        # Main Streamlit application
├── requirements.txt              # Python dependencies
├── README.md                     # This file
├── .devcontainer/
│   └── devcontainer.json         # VS Code / Codespaces dev container config
├── .github/
│   └── workflows/
│       └── keep_alive.yml        # Hourly cron job to prevent app hibernation
└── refresher/
    ├── Dockerfile                # Docker image for the Puppeteer probe
    ├── action.yml                # GitHub Action definition
    └── probe.js                  # Headless browser script to wake a hibernated app
```

---

## Keep-Alive Mechanism

Streamlit Community Cloud hibernates free-tier apps after a period of inactivity. Two mechanisms prevent this:

1. **`keep_alive.yml`** — A GitHub Actions workflow that runs every hour, pushes a trivial commit to trigger a Streamlit redeploy, then sends a `GET` request to the app URL.
2. **`refresher/probe.js`** — A Puppeteer script that navigates to the app and clicks the *"Yes, get this app back up!"* button if the hibernation screen is detected. It is packaged as a reusable Docker-based GitHub Action (`refresher/action.yml`).

---

## Dependencies

| Package | Purpose |
|---|---|
| `streamlit` | Web UI framework |
| `pandas` | Data loading and manipulation |
| `requests` | GitHub API HTTP calls |
| `plotly` | Interactive charts |

> `tqdm`, `matplotlib`, `seaborn`, and `multiprocessing` were previously imported but are not used and have been removed.
