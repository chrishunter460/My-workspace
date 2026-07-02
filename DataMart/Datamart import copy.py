
import io
import re

try:
    import truststore

    truststore.inject_into_ssl()
except Exception:
    pass

import pandas as pd
import requests
import snowflake.connector
import streamlit as st
from snowflake.connector.pandas_tools import write_pandas

# Native Google Auth
import google.auth
from google.auth.transport.requests import AuthorizedSession, Request
from googleapiclient.discovery import build

# ==============================================================
# 1. CONFIGURATION
# ==============================================================
SNOWFLAKE_ACCOUNT   = "ux97206.us-east4.gcp"
SNOWFLAKE_USER      = "CHRIS.HUNTER@CLOVERHEALTH.COM"
SNOWFLAKE_ROLE      = "RL_SNOWFLAKE_ACTUARIAL_PROD"
SNOWFLAKE_WAREHOUSE = "CLOVER_MA_ACTUARIAL"
TARGET_DATABASE     = "CLOVER_MA_UNCONTROLLED"
TARGET_SCHEMA       = "ACTUARIAL"
DESIRED_UPLOAD_LIMIT_MB = 4096
GOOGLE_SHEETS_READ_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]
GOOGLE_IDENTITY_SCOPES = ["https://www.googleapis.com/auth/userinfo.email"]
GOOGLE_AUTH_COMMAND = (
    "gcloud auth application-default login "
    "--scopes=https://www.googleapis.com/auth/cloud-platform,"
    "https://www.googleapis.com/auth/drive.readonly,"
    "https://www.googleapis.com/auth/spreadsheets.readonly,"
    "https://www.googleapis.com/auth/userinfo.email"
)

# ==============================================================
# 2. CORE UTILITIES
# ==============================================================

def sf_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def sf_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def is_yes(value) -> bool:
    return str(value).strip().upper() in {"Y", "YES", "TRUE", "1"}


def get_google_credentials(scopes: list[str]):
    creds, _ = google.auth.default(scopes=scopes)
    creds.refresh(Request())
    return creds


@st.cache_resource
def get_snowflake_conn():
    # Connect bare so we can validate role/db/schema/warehouse separately.
    return snowflake.connector.connect(
        user=SNOWFLAKE_USER,
        account=SNOWFLAKE_ACCOUNT,
        authenticator="externalbrowser",
        insecure_mode=True,
    )


def run_df(conn, sql: str) -> pd.DataFrame:
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        if cursor.description is None:
            return pd.DataFrame()
        cols = [desc[0].upper() for desc in cursor.description]
        rows = cursor.fetchall()
        return pd.DataFrame(rows, columns=cols)
    finally:
        cursor.close()


def has_exact_name(df: pd.DataFrame, expected_name: str) -> bool:
    if df.empty or "NAME" not in df.columns:
        return False
    return df["NAME"].astype(str).str.upper().eq(str(expected_name).upper()).any()


def prepare_session(conn, require_warehouse: bool = False) -> dict:
    """
    Set role/database/schema. Only validate+use warehouse when required.
    This lets hygiene work even if warehouse grants are missing.
    """
    steps = []
    cur = conn.cursor()

    def add_step(step: str, target: str, ok: bool, detail: str = ""):
        steps.append(
            {
                "STEP": step,
                "TARGET": target,
                "STATUS": "OK" if ok else "FAIL",
                "DETAIL": detail,
            }
        )

    try:
        # Role
        try:
            cur.execute(f"USE ROLE {sf_ident(SNOWFLAKE_ROLE)}")
            add_step("USE ROLE", SNOWFLAKE_ROLE, True)
        except Exception as e:
            add_step("USE ROLE", SNOWFLAKE_ROLE, False, str(e))
            return {"ok": False, "message": f"Cannot use role {SNOWFLAKE_ROLE}: {e}", "steps_df": pd.DataFrame(steps)}

        # Secondary roles
        try:
            cur.execute("USE SECONDARY ROLES ALL")
            add_step("USE SECONDARY ROLES", "ALL", True)
        except Exception as e:
            add_step("USE SECONDARY ROLES", "ALL", False, str(e))

        # Warehouse only when needed
        if require_warehouse:
            wh_df = run_df(conn, f"SHOW WAREHOUSES LIKE {sf_literal(SNOWFLAKE_WAREHOUSE)}")
            if not has_exact_name(wh_df, SNOWFLAKE_WAREHOUSE):
                add_step("SHOW WAREHOUSES", SNOWFLAKE_WAREHOUSE, False, "Warehouse not visible to current role.")
                return {
                    "ok": False,
                    "message": (
                        f"Warehouse {SNOWFLAKE_WAREHOUSE} is not visible to role {SNOWFLAKE_ROLE}. "
                        "Ask a Snowflake admin to grant USAGE on that warehouse, or update SNOWFLAKE_WAREHOUSE."
                    ),
                    "steps_df": pd.DataFrame(steps),
                }

            try:
                cur.execute(f"USE WAREHOUSE {sf_ident(SNOWFLAKE_WAREHOUSE)}")
                add_step("USE WAREHOUSE", SNOWFLAKE_WAREHOUSE, True)
            except Exception as e:
                add_step("USE WAREHOUSE", SNOWFLAKE_WAREHOUSE, False, str(e))
                return {
                    "ok": False,
                    "message": f"Cannot use warehouse {SNOWFLAKE_WAREHOUSE}: {e}",
                    "steps_df": pd.DataFrame(steps),
                }

        # Database
        db_df = run_df(conn, f"SHOW DATABASES LIKE {sf_literal(TARGET_DATABASE)}")
        if not has_exact_name(db_df, TARGET_DATABASE):
            add_step("SHOW DATABASES", TARGET_DATABASE, False, "Database not visible to current role.")
            return {
                "ok": False,
                "message": f"Database {TARGET_DATABASE} is not visible to role {SNOWFLAKE_ROLE}.",
                "steps_df": pd.DataFrame(steps),
            }

        try:
            cur.execute(f"USE DATABASE {sf_ident(TARGET_DATABASE)}")
            add_step("USE DATABASE", TARGET_DATABASE, True)
        except Exception as e:
            add_step("USE DATABASE", TARGET_DATABASE, False, str(e))
            return {"ok": False, "message": f"Cannot use database {TARGET_DATABASE}: {e}", "steps_df": pd.DataFrame(steps)}

        # Schema
        schema_df = run_df(
            conn,
            f"SHOW SCHEMAS LIKE {sf_literal(TARGET_SCHEMA)} IN DATABASE {sf_ident(TARGET_DATABASE)}",
        )
        if not has_exact_name(schema_df, TARGET_SCHEMA):
            add_step("SHOW SCHEMAS", f"{TARGET_DATABASE}.{TARGET_SCHEMA}", False, "Schema not visible to current role.")
            return {
                "ok": False,
                "message": f"Schema {TARGET_DATABASE}.{TARGET_SCHEMA} is not visible to role {SNOWFLAKE_ROLE}.",
                "steps_df": pd.DataFrame(steps),
            }

        try:
            cur.execute(f"USE SCHEMA {sf_ident(TARGET_DATABASE)}.{sf_ident(TARGET_SCHEMA)}")
            add_step("USE SCHEMA", f"{TARGET_DATABASE}.{TARGET_SCHEMA}", True)
        except Exception as e:
            add_step("USE SCHEMA", f"{TARGET_DATABASE}.{TARGET_SCHEMA}", False, str(e))
            return {
                "ok": False,
                "message": f"Cannot use schema {TARGET_DATABASE}.{TARGET_SCHEMA}: {e}",
                "steps_df": pd.DataFrame(steps),
            }

        return {"ok": True, "message": "Session ready.", "steps_df": pd.DataFrame(steps)}

    finally:
        cur.close()


def get_google_identity():
    try:
        creds = get_google_credentials(GOOGLE_IDENTITY_SCOPES)
        service = build("oauth2", "v2", credentials=creds)
        user_info = service.userinfo().get().execute()
        return user_info.get("email")
    except Exception:
        return None


def clean_headers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        re.sub(r"[^a-zA-Z0-9_]", "", str(c).replace(" ", "_").replace("-", "_")).upper()
        for c in df.columns
    ]
    return df


def convert_to_export_url(url: str) -> str:
    if "docs.google.com/spreadsheets" in url and "/export" not in url:
        base_url = url.split("/edit")[0]
        gid_match = re.search(r"gid=(\d+)", url)
        gid = gid_match.group(1) if gid_match else "0"
        return f"{base_url}/export?format=csv&gid={gid}"
    return url


def download_google_sheet_csv(export_url: str) -> str:
    auth_error = None
    try:
        creds = get_google_credentials(GOOGLE_SHEETS_READ_SCOPES)
        response = AuthorizedSession(creds).get(export_url, timeout=60)
    except Exception as e:
        auth_error = e
        response = requests.get(export_url, timeout=60)

    if response.status_code in {401, 403}:
        if auth_error is not None:
            raise RuntimeError(
                "Google denied access to this sheet, and this app does not have Google credentials configured. "
                "For a private Sheet, export it as CSV and use CSV Upload, publish/share the Sheet so the CSV "
                f"export is accessible, or run this in PowerShell and restart the app: {GOOGLE_AUTH_COMMAND}. "
                f"Google authentication failed with: {auth_error}"
            )
        raise RuntimeError(
            "Google denied access to this sheet. Share/publish the Sheet so the CSV export is accessible, "
            "or export it as CSV and use CSV Upload."
        )

    response.raise_for_status()
    return response.text





def get_streamlit_upload_limit_mb() -> int | None:
    try:
        return int(st.get_option("server.maxUploadSize"))
    except Exception:
        return None


def show_upload_limit_warning():
    current_limit = get_streamlit_upload_limit_mb()
    if current_limit is not None and current_limit < DESIRED_UPLOAD_LIMIT_MB:
        st.warning(
            f"Current Streamlit upload limit is {current_limit} MB. "
            f"Files larger than this will be rejected before Python can chunk them. "
            f"Set .streamlit/config.toml to server.maxUploadSize = {DESIRED_UPLOAD_LIMIT_MB} and restart Streamlit."
        )

def upload_csv_to_snowflake_chunked(
    conn,
    csv_file,
    table_name: str,
    read_chunksize: int = 100_000,
    write_chunk_size: int = 100_000,
    max_upload_mb: int | None = None,
) -> int:
    """
    Stream a CSV into Snowflake without loading the whole file into memory.

    Behavior mirrors the R pattern:
      - first chunk: create/replace table
      - following chunks: append
      - transaction: BEGIN / COMMIT, with ROLLBACK on error

    `read_chunksize` controls pandas CSV rows per DataFrame.
    `write_chunk_size` controls Snowflake connector parquet/write chunks.
    """
    target_name = table_name.strip().upper()
    if not target_name:
        raise ValueError("Snowflake table name is required.")

    if csv_file is None:
        raise ValueError("CSV file is required.")

    file_size_bytes = getattr(csv_file, "size", None)
    if max_upload_mb and file_size_bytes is not None:
        max_bytes = max_upload_mb * 1024 * 1024
        if file_size_bytes > max_bytes:
            raise ValueError(
                f"File is {file_size_bytes / 1024 / 1024:,.1f} MB, "
                f"which exceeds the configured limit of {max_upload_mb:,} MB."
            )

    # Ensure rereads start at byte 0 after Streamlit has handled the upload.
    try:
        csv_file.seek(0)
    except Exception:
        pass

    total_rows = 0
    first_chunk = True

    progress = st.progress(0)
    status = st.empty()
    detail_box = st.empty()

    cur = conn.cursor()
    try:
        cur.execute("BEGIN")

        # Read every CSV field as text. This is important for claims/billing files:
        # pandas can otherwise infer mixed object/float values for columns like
        # TYPE_OF_BILL_CODE, diagnosis codes, CPT codes, IDs, ZIP codes, etc.,
        # which can make PyArrow/write_pandas fail with errors such as
        # "Expected bytes, got a float object".
        reader = pd.read_csv(
            csv_file,
            chunksize=read_chunksize,
            dtype=str,
            keep_default_na=False,
            low_memory=False,
        )

        for i, chunk in enumerate(reader, start=1):
            chunk = clean_headers(chunk)

            # Normalize blanks / textual null sentinels to real NULLs before upload.
            # Leave all non-null values as strings so Snowflake creates VARCHAR columns.
            chunk = chunk.astype(str)
            chunk = chunk.replace(
                {
                    "": None,
                    "nan": None,
                    "NaN": None,
                    "None": None,
                    "<NA>": None,
                    "NULL": None,
                    "null": None,
                }
            )

            success, num_chunks, num_rows, output = write_pandas(
                conn=conn,
                df=chunk,
                table_name=target_name,
                database=TARGET_DATABASE,
                schema=TARGET_SCHEMA,
                auto_create_table=True,
                overwrite=first_chunk,
                chunk_size=write_chunk_size,
                bulk_upload_chunks=False,
                quote_identifiers=True,
            )

            if not success:
                raise RuntimeError(f"write_pandas failed on CSV chunk {i}: {output}")

            total_rows += int(num_rows)
            first_chunk = False

            status.info(f"Uploaded CSV chunk {i:,}; total rows loaded: {total_rows:,}")
            detail_box.caption(
                f"Last Snowflake write: {num_rows:,} rows across {num_chunks:,} connector chunk(s)."
            )

            # Unknown final row count, so make this an activity indicator that moves but does not promise completion.
            progress.progress(min(0.95, (i % 20 + 1) / 20))

        if first_chunk:
            raise ValueError("CSV appears to be empty; no rows were uploaded.")

        cur.execute("COMMIT")
        progress.progress(1.0)
        status.success(f"Committed {total_rows:,} rows to {target_name}.")
        return total_rows

    except Exception:
        try:
            cur.execute("ROLLBACK")
        except Exception:
            pass
        raise

    finally:
        cur.close()


def load_hygiene_objects(conn) -> pd.DataFrame:
    scope = f"{sf_ident(TARGET_DATABASE)}.{sf_ident(TARGET_SCHEMA)}"

    tables = run_df(conn, f"SHOW TABLES IN SCHEMA {scope}")
    views = run_df(conn, f"SHOW VIEWS IN SCHEMA {scope}")

    frames = []

    if not tables.empty:
        t = tables.rename(
            columns={
                "NAME": "TABLE_NAME",
                "OWNER": "TABLE_OWNER",
                "CREATED_ON": "CREATED",
                "ROWS": "ROW_COUNT",
            }
        ).copy()

        if "DROPPED_ON" in t.columns:
            t = t[t["DROPPED_ON"].isna() | (t["DROPPED_ON"] == "")]

        def classify_table(row) -> str:
            if is_yes(row.get("IS_DYNAMIC", "N")) and is_yes(row.get("IS_ICEBERG", "N")):
                return "DYNAMIC ICEBERG TABLE"
            if is_yes(row.get("IS_DYNAMIC", "N")):
                return "DYNAMIC TABLE"
            if is_yes(row.get("IS_EXTERNAL", "N")):
                return "EXTERNAL TABLE"
            if is_yes(row.get("IS_ICEBERG", "N")):
                return "ICEBERG TABLE"
            if is_yes(row.get("IS_EVENT", "N")):
                return "EVENT TABLE"
            if is_yes(row.get("IS_HYBRID", "N")):
                return "HYBRID TABLE"

            kind = str(row.get("KIND", "TABLE")).upper()
            if kind == "TEMPORARY":
                return "TEMPORARY TABLE"
            if kind == "TRANSIENT":
                return "TRANSIENT TABLE"
            return "BASE TABLE"

        t["TABLE_TYPE"] = t.apply(classify_table, axis=1)
        frames.append(t[["TABLE_NAME", "TABLE_TYPE", "TABLE_OWNER", "CREATED", "ROW_COUNT"]])

    if not views.empty:
        v = views.rename(
            columns={
                "NAME": "TABLE_NAME",
                "OWNER": "TABLE_OWNER",
                "CREATED_ON": "CREATED",
            }
        ).copy()

        v["ROW_COUNT"] = pd.NA
        v["TABLE_TYPE"] = (
            v["KIND"]
            .astype(str)
            .str.upper()
            .map({"VIEW": "VIEW", "MATERIALIZED_VIEW": "MATERIALIZED VIEW"})
            .fillna("VIEW")
        )
        frames.append(v[["TABLE_NAME", "TABLE_TYPE", "TABLE_OWNER", "CREATED", "ROW_COUNT"]])

    if not frames:
        return pd.DataFrame(columns=["TABLE_NAME", "TABLE_TYPE", "TABLE_OWNER", "CREATED", "ROW_COUNT"])

    out = pd.concat(frames, ignore_index=True)
    out["CREATED"] = pd.to_datetime(out["CREATED"], errors="coerce")
    return out.sort_values("CREATED", ascending=False, na_position="last").reset_index(drop=True)


def build_drop_sql(object_type: str, object_name: str) -> str:
    fqn = (
        f"{sf_ident(TARGET_DATABASE)}."
        f"{sf_ident(TARGET_SCHEMA)}."
        f"{sf_ident(object_name)}"
    )

    tt = str(object_type).upper()

    if tt == "VIEW":
        return f"DROP VIEW IF EXISTS {fqn}"
    if tt == "MATERIALIZED VIEW":
        return f"DROP MATERIALIZED VIEW IF EXISTS {fqn}"
    if tt == "EXTERNAL TABLE":
        return f"DROP EXTERNAL TABLE IF EXISTS {fqn}"
    if tt == "ICEBERG TABLE":
        return f"DROP ICEBERG TABLE IF EXISTS {fqn}"
    if tt in {"DYNAMIC TABLE", "DYNAMIC ICEBERG TABLE"}:
        return f"DROP DYNAMIC TABLE IF EXISTS {fqn}"

    return f"DROP TABLE IF EXISTS {fqn}"


# ==============================================================
# 3. UI
# ==============================================================

st.set_page_config(page_title="PHI-Secure Data Manager", layout="wide")

with st.sidebar:
    st.header("🔐 Authentication")
    st.info(f"User: **{SNOWFLAKE_USER}**\n\nTarget Role: **{SNOWFLAKE_ROLE}**")

    user_email = get_google_identity()
    if user_email:
        st.success(f"G-Cloud Identity: {user_email}")
    else:
        st.warning("G-Cloud identity not configured. Private Google Sheets require CSV upload, public access, or ADC.")
        with st.expander("G-Cloud setup command", expanded=False):
            st.code(GOOGLE_AUTH_COMMAND, language="powershell")
        if st.button("Authenticate G-Cloud", use_container_width=True):
            st.info(f"Run this in PowerShell, then restart the app: `{GOOGLE_AUTH_COMMAND}`")

    st.divider()

    try:
        conn_for_status = get_snowflake_conn()
        hygiene_status = prepare_session(conn_for_status, require_warehouse=False)
        if hygiene_status["ok"]:
            st.success("Snowflake ready for hygiene.")
        else:
            st.error(hygiene_status["message"])

        ingest_status = prepare_session(conn_for_status, require_warehouse=True)
        if ingest_status["ok"]:
            st.success("Warehouse ready for ingestion.")
        else:
            st.warning(ingest_status["message"])

        with st.expander("Snowflake diagnostics", expanded=not ingest_status["ok"]):
            if not ingest_status["steps_df"].empty:
                st.dataframe(ingest_status["steps_df"], hide_index=True, use_container_width=True)
            elif not hygiene_status["steps_df"].empty:
                st.dataframe(hygiene_status["steps_df"], hide_index=True, use_container_width=True)
    except Exception as e:
        st.error(f"Snowflake bootstrap error: {e}")

    if st.button("🔄 Refresh Snowflake Connection", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()

tab_ingest, tab_hygiene = st.tabs(["📤 Ingest Data", "🧹 Data Hygiene"])

# --------------------------------------------------------------
# TAB 1: INGESTION
# --------------------------------------------------------------
with tab_ingest:
    st.subheader("📤 Ingest Data")

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("🌐 Google Sheets")
        gs_url = st.text_input("Google Sheet URL")
        gs_table = st.text_input("Snowflake Table Name (GS)", key="gs_t")

    with c2:
        st.subheader("📄 CSV Upload")
        show_upload_limit_warning()
        current_limit = get_streamlit_upload_limit_mb()
        if current_limit is not None:
            st.caption(f"Active Streamlit upload limit: {current_limit} MB")
        csv_file = st.file_uploader("Browse CSV File", type="csv")
        csv_table = st.text_input("Snowflake Table Name (CSV)", key="csv_t")

        with st.expander("CSV chunk settings", expanded=False):
            read_chunksize = st.number_input(
                "Rows to read per pandas chunk",
                min_value=1_000,
                max_value=1_000_000,
                value=100_000,
                step=10_000,
            )
            write_chunk_size = st.number_input(
                "Rows per Snowflake write_pandas chunk",
                min_value=1_000,
                max_value=1_000_000,
                value=100_000,
                step=10_000,
            )

    if st.button("🚀 EXECUTE SYNC", type="primary", use_container_width=True):
        try:
            conn = get_snowflake_conn()
            ingest_status = prepare_session(conn, require_warehouse=True)
            if not ingest_status["ok"]:
                st.error(ingest_status["message"])
                st.dataframe(ingest_status["steps_df"], hide_index=True, use_container_width=True)
                st.stop()
        except Exception as e:
            st.error(f"Snowflake connection error: {e}")
            st.stop()

        # Google Sheets ingestion
        if gs_url and gs_table:
            try:
                export_url = convert_to_export_url(gs_url)
                with st.spinner("Downloading Google Sheet..."):
                    csv_text = download_google_sheet_csv(export_url)
                    gs_df = pd.read_csv(io.StringIO(csv_text), dtype=str, keep_default_na=False)
                gs_df = clean_headers(gs_df)
                target_name = gs_table.strip().upper()
                with st.spinner(f"Uploading {len(gs_df):,} rows to {target_name}..."):
                    success, num_chunks, num_rows, output = write_pandas(
                        conn=conn,
                        df=gs_df,
                        table_name=target_name,
                        database=TARGET_DATABASE,
                        schema=TARGET_SCHEMA,
                        auto_create_table=True,
                        overwrite=True,
                        quote_identifiers=True,
                    )
                if success:
                    st.success(f"Uploaded {num_rows:,} rows from Google Sheet to {target_name}.")
                else:
                    st.error(f"write_pandas failed: {output}")
            except Exception as e:
                st.error(f"Google Sheets ingestion error: {e}")

        # CSV ingestion
        if csv_file and csv_table:
            try:
                upload_csv_to_snowflake_chunked(
                    conn=conn,
                    csv_file=csv_file,
                    table_name=csv_table,
                    read_chunksize=int(read_chunksize),
                    write_chunk_size=int(write_chunk_size),
                    max_upload_mb=DESIRED_UPLOAD_LIMIT_MB,
                )
            except Exception as e:
                st.error(f"CSV ingestion error: {e}")

        if not gs_url and not csv_file:
            st.warning("Provide a Google Sheet URL or upload a CSV file.")

# --------------------------------------------------------------
# TAB 2: DATA HYGIENE
# --------------------------------------------------------------
with tab_hygiene:
    st.subheader("🧹 Data Hygiene")

    try:
        conn_h = get_snowflake_conn()
        hygiene_result = prepare_session(conn_h, require_warehouse=False)
        if not hygiene_result["ok"]:
            st.error(hygiene_result["message"])
            st.stop()
    except Exception as e:
        st.error(f"Snowflake connection error: {e}")
        st.stop()

    if st.button("🔄 Refresh Object List", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()

    with st.spinner("Loading tables and views..."):
        objects_df = load_hygiene_objects(conn_h)

    if objects_df.empty:
        st.info(f"No tables or views found in {TARGET_DATABASE}.{TARGET_SCHEMA}.")
    else:
        st.dataframe(objects_df, hide_index=True, use_container_width=True)

        st.divider()
        st.subheader("Drop an Object")

        object_names = objects_df["TABLE_NAME"].tolist()
        selected_name = st.selectbox("Select object to drop", options=object_names)

        if selected_name:
            row = objects_df[objects_df["TABLE_NAME"] == selected_name].iloc[0]
            object_type = row["TABLE_TYPE"]
            drop_sql = build_drop_sql(object_type, selected_name)

            st.code(drop_sql, language="sql")
            st.warning(f"This will permanently drop **{selected_name}** ({object_type}). This cannot be undone.")

            if st.button("🗑️ Confirm Drop", type="primary"):
                try:
                    run_df(conn_h, drop_sql)
                    st.success(f"Dropped {object_type} {selected_name}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Drop failed: {e}")
