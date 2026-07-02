import os
import re
import truststore
truststore.inject_into_ssl()

import pandas as pd
import snowflake.connector
import streamlit as st
from snowflake.connector.pandas_tools import write_pandas

# Google Auth via installed-app OAuth flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ==============================================================
# 1. CONFIGURATION
# ==============================================================
SNOWFLAKE_ACCOUNT = "ux97206.us-east4.gcp"
SNOWFLAKE_USER = "chris.hunter@cloverhealth.com"
SNOWFLAKE_ROLE = "RL_SNOWFLAKE_ACTUARIAL_PROD"
SNOWFLAKE_WAREHOUSE = "CLOVER_MA_ACTUARIAL"
TARGET_DATABASE = "CLOVER_MA_UNCONTROLLED"
TARGET_SCHEMA = "ACTUARIAL"
DESIRED_UPLOAD_LIMIT_MB = 4096

# Path to the OAuth client secrets JSON downloaded from GCP console
# and the cached token file written after first login
GOOGLE_CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), "client_secrets.json")
GOOGLE_TOKEN_FILE = os.path.join(os.path.dirname(__file__), "google_token.json")
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

# ==============================================================
# 2. CORE UTILITIES
# ==============================================================

def sf_ident(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def sf_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def is_yes(value) -> bool:
    return str(value).strip().upper() in {"Y", "YES", "TRUE", "1"}


@st.cache_resource
def get_snowflake_conn():
    # Connect bare so we can validate role/db/schema/warehouse separately.
    return snowflake.connector.connect(
        user=SNOWFLAKE_USER,
        account=SNOWFLAKE_ACCOUNT,
        authenticator="externalbrowser",
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


def get_google_creds() -> Credentials | None:
    creds = None
    if os.path.exists(GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_FILE, GOOGLE_SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(GOOGLE_TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
            return creds
        except Exception:
            pass
    if not os.path.exists(GOOGLE_CLIENT_SECRETS):
        return None
    flow = InstalledAppFlow.from_client_secrets_file(GOOGLE_CLIENT_SECRETS, GOOGLE_SCOPES)
    creds = flow.run_local_server(port=0)
    with open(GOOGLE_TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    return creds


def get_google_identity():
    try:
        creds = get_google_creds()
        if not creds:
            return None
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
        if st.button("Authenticate G-Cloud", use_container_width=True):
            st.info("Run `gcloud auth application-default login` in your terminal.")

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

        has_gs = bool(gs_url and gs_table)
        has_csv = bool(csv_file is not None and csv_table)

        if csv_table and csv_file is None:
            st.warning(
                "CSV table name was provided, but no CSV file reached the app. "
                "If you selected a file, Streamlit rejected it before Python received it. "
                "Increase server.maxUploadSize in .streamlit/config.toml and restart Streamlit."
            )
        elif not has_gs and not has_csv:
            st.warning("Provide a Google Sheet URL + table name and/or a CSV file + table name.")
        else:
            if has_gs:
                try:
                    creds = get_google_creds()
                    if not creds:
                        st.error("Google credentials not found. Download client_secrets.json from GCP Console and place it in the DataMart folder, then restart.")
                        st.stop()

                    # Extract spreadsheet ID and optional sheet gid from URL
                    sid_match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", gs_url)
                    if not sid_match:
                        st.error("Could not parse a spreadsheet ID from the URL.")
                        st.stop()
                    spreadsheet_id = sid_match.group(1)

                    gid_match = re.search(r"gid=(\d+)", gs_url)
                    gid = int(gid_match.group(1)) if gid_match else 0

                    # Use Sheets API v4 to read values — works with OAuth ADC, no export URL needed
                    service = build("sheets", "v4", credentials=creds)
                    sheet_meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
                    sheets = sheet_meta.get("sheets", [])
                    sheet_name = None
                    for s in sheets:
                        if s["properties"]["sheetId"] == gid:
                            sheet_name = s["properties"]["title"]
                            break
                    if sheet_name is None and sheets:
                        sheet_name = sheets[0]["properties"]["title"]

                    result = (
                        service.spreadsheets()
                        .values()
                        .get(spreadsheetId=spreadsheet_id, range=sheet_name)
                        .execute()
                    )
                    rows = result.get("values", [])
                    if not rows:
                        st.error("Google Sheet appears to be empty.")
                    else:
                        df_gs = clean_headers(pd.DataFrame(rows[1:], columns=rows[0]))
                        target_name = gs_table.strip().upper()
                        write_pandas(conn, df_gs, target_name, auto_create_table=True, overwrite=True)
                        st.success(f"Uploaded Google Sheet to {target_name} ({len(df_gs):,} rows)")
                except Exception as e:
                    st.error(f"Google Sheet sync error: {e}")

            if has_csv:
                try:
                    target_name = csv_table.strip().upper()
                    rows_loaded = upload_csv_to_snowflake_chunked(
                        conn=conn,
                        csv_file=csv_file,
                        table_name=target_name,
                        read_chunksize=int(read_chunksize),
                        write_chunk_size=int(write_chunk_size),
                    )
                    st.success(f"Uploaded CSV as {target_name} ({rows_loaded:,} rows)")
                except Exception as e:
                    st.error(f"CSV sync error: {e}")

# --------------------------------------------------------------
# TAB 2: HYGIENE
# --------------------------------------------------------------
with tab_hygiene:
    st.subheader("🧹 Ad-hoc Table Cleanup")

    try:
        conn = get_snowflake_conn()
        hygiene_status = prepare_session(conn, require_warehouse=False)
        if not hygiene_status["ok"]:
            st.error(hygiene_status["message"])
            st.dataframe(hygiene_status["steps_df"], hide_index=True, use_container_width=True)
            st.stop()
    except Exception as e:
        st.error(f"Snowflake connection error: {e}")
        st.stop()

    st.caption(
        f"Target context → role={SNOWFLAKE_ROLE}, database={TARGET_DATABASE}, schema={TARGET_SCHEMA}"
    )

    try:
        df_objects = load_hygiene_objects(conn)
    except Exception as e:
        st.error(f"Metadata load error: {e}")
        st.stop()

    if df_objects.empty:
        st.info("No tables or views found.")
    else:
        df_objects.insert(0, "Select", False)
        df_objects["OWNER_MATCH"] = (
            df_objects["TABLE_OWNER"].astype(str).str.upper() == SNOWFLAKE_ROLE.upper()
        )

        edited_df = st.data_editor(
            df_objects,
            hide_index=True,
            use_container_width=True,
            disabled=["TABLE_NAME", "TABLE_TYPE", "TABLE_OWNER", "CREATED", "ROW_COUNT", "OWNER_MATCH"],
            column_config={
                "Select": st.column_config.CheckboxColumn("Drop?", default=False),
                "OWNER_MATCH": st.column_config.CheckboxColumn("Owner role matches target role", disabled=True),
            },
        )

        to_delete_df = edited_df[edited_df["Select"] == True].copy()

        if not to_delete_df.empty:
            st.divider()
            st.write("### Review Deletions")
            st.table(to_delete_df[["TABLE_NAME", "TABLE_TYPE", "TABLE_OWNER"]])

            mismatches = to_delete_df[to_delete_df["OWNER_MATCH"] == False]
            if not mismatches.empty:
                st.warning(
                    "Some selected objects are owned by a different role. They may fail to drop if this role lacks ownership."
                )

            confirm = st.checkbox("Confirm permanent deletion")

            if st.button("🔥 EXECUTE DROPS", type="primary", disabled=not confirm, use_container_width=True):
                cursor = conn.cursor()
                try:
                    for _, row in to_delete_df.iterrows():
                        object_name = str(row["TABLE_NAME"])
                        object_type = str(row["TABLE_TYPE"])
                        sql = build_drop_sql(object_type, object_name)

                        try:
                            cursor.execute(sql)
                            st.success(f"✅ Dropped {object_type}: {object_name}")
                        except Exception as e:
                            st.error(f"❌ Failed to drop {object_name}")
                            st.code(f"SQL Attempted:\n{sql}\n\nError:\n{e}")
                finally:
                    cursor.close()

                st.cache_resource.clear()
                st.rerun()
