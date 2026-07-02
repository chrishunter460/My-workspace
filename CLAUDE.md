# My-workspace — Claude Context

## Project overview

A Streamlit-based data management tool for actuarial analytics. Lets users ingest data (from CSV files or Google Sheets) into Snowflake, and manage/drop tables in the target schema.

## Tech stack

| Layer | Technology |
|---|---|
| UI | Streamlit 1.58 |
| Data | pandas 2.x, pyarrow 24 |
| Snowflake | snowflake-connector-python 4.6, write_pandas |
| Google | google-api-python-client, google-auth-oauthlib (installed-app OAuth) |
| SSL | truststore (injects Windows certificate store into Python's SSL) |
| Runtime | Python 3.x, .venv at `.venv/` |

## Snowflake target

- **Account:** `ux97206.us-east4.gcp` (GCP us-east4)
- **Auth:** `externalbrowser` (SSO via browser popup)
- **Role:** `RL_SNOWFLAKE_ACTUARIAL_PROD`
- **Warehouse:** `CLOVER_MA_ACTUARIAL`
- **Database / Schema:** `CLOVER_MA_UNCONTROLLED.ACTUARIAL`

## Google Auth

OAuth 2.0 installed-app flow. Requires two files in `DataMart/` (both git-ignored):
- `client_secrets.json` — downloaded from GCP Console
- `google_token.json` — written automatically after first login, auto-refreshed

Scopes: `spreadsheets.readonly`, `userinfo.email`, `openid`

## Key files

| File | Purpose |
|---|---|
| [DataMart/Datamart import.py](DataMart/Datamart%20import.py) | All application code (config, utilities, Streamlit UI) |
| [requirements.txt](requirements.txt) | Pinned dependencies for `.venv` |
| [.gitignore](.gitignore) | Excludes OAuth secrets, `.venv`, caches |
| [My-workspace.code-workspace](My-workspace.code-workspace) | VSCode workspace config |

## Running the app

```bash
.venv/Scripts/streamlit run "DataMart/Datamart import.py"
```

## Architecture notes

- `get_snowflake_conn()` is `@st.cache_resource` — one connection per session, cleared with the "Refresh" button.
- `prepare_session()` sets role/database/schema. Warehouse is only activated for ingestion, not hygiene, because the user may lack warehouse grants.
- `upload_csv_to_snowflake_chunked()` streams large CSVs in pandas chunks (default 100k rows) inside a single `BEGIN/COMMIT` transaction. All fields read as `dtype=str` to avoid PyArrow type inference failures on codes, ZIPs, and IDs.
- Column headers are normalized by `clean_headers()`: spaces/hyphens → underscores, non-alphanumeric stripped, uppercased.
- The "Data Hygiene" tab lists tables and views in the schema and allows bulk-drop with ownership warnings; it does not need a warehouse.

## Sensitive files (never commit)

- `DataMart/client_secrets.json`
- `DataMart/google_token.json`
- `.env` / `.env.*`
