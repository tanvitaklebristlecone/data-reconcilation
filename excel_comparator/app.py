from __future__ import annotations

from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

from core.auto_mapper import auto_map_columns
from core.comparator import ExcelComparator
from core.loader import load_excel
from core.mapper import ColumnMapper
from core.writer import write_annotated_excel
from utils.helpers import classify_remark, get_output_filename

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(layout="wide", page_icon="📊", page_title="DataSync Comparator")

st.markdown(
    """
<style>
[data-testid="stSidebar"] { background: #0F1923; color: white; }
.main { background: #F8F9FC; }
.card {
    background: white;
    border-radius: 12px;
    padding: 24px;
    border: 1px solid #E2E8F0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    margin-bottom: 20px;
}
.section-title {
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #64748B;
    margin-bottom: 12px;
}
.stButton > button {
    background: #1E6FD9;
    color: white;
    border-radius: 8px;
    font-weight: 600;
    padding: 10px 28px;
    border: none;
}
.stButton > button:hover { background: #1558B0; color: white; }
</style>
""",
    unsafe_allow_html=True,
)

# ── Session state ──────────────────────────────────────────────────────────────
for _k in ("run_output", "run_summary", "annotated_df"):
    if _k not in st.session_state:
        st.session_state[_k] = None


# ── Helpers ────────────────────────────────────────────────────────────────────
def _load_file(uploaded, sheet_key: str):
    """Load an uploaded file, with optional sheet selection."""
    if uploaded is None:
        return None
    raw = BytesIO(uploaded.getvalue())
    initial = load_excel(raw)
    active = initial["active_sheet"]
    if len(initial["sheets"]) > 1:
        active = st.selectbox(
            f"Select sheet — {uploaded.name}",
            options=initial["sheets"],
            index=initial["sheets"].index(active),
            key=sheet_key,
        )
    loaded = load_excel(BytesIO(uploaded.getvalue()), sheet_name=active)
    loaded["name"] = uploaded.name
    loaded["bytes"] = uploaded.getvalue()
    return loaded


def _safe_df(df: pd.DataFrame) -> pd.DataFrame:
    """Cast all columns to string to prevent Arrow serialisation errors."""
    return df.astype(str)


# ── Header ─────────────────────────────────────────────────────────────────────
st.title("📊 DataSync Comparator")
st.caption(
    "Upload Source and Target Excel files. "
    "Columns are mapped automatically — no manual configuration needed."
)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — UPLOAD
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("---")
st.subheader("📂 Step 1 — Upload Files")

col_src, col_tgt = st.columns(2)
source_payload = None
target_payload = None

with col_src:
    src_file = st.file_uploader(
        "Source File (.xlsx / .xls)", type=["xlsx", "xls"], key="src_upload"
    )
    if src_file:
        try:
            source_payload = _load_file(src_file, "src_sheet")
            st.success(
                f"✅ **{source_payload['name']}** — "
                f"{source_payload['row_count']:,} rows × {source_payload['col_count']} cols"
            )
            with st.expander("👁️ Preview Source (top 5 rows)"):
                st.dataframe(_safe_df(source_payload["df"].head(5)), use_container_width=True)
        except ValueError as exc:
            st.error(str(exc))

with col_tgt:
    tgt_file = st.file_uploader(
        "Target File — IBP (.xlsx / .xls)", type=["xlsx", "xls"], key="tgt_upload"
    )
    if tgt_file:
        try:
            target_payload = _load_file(tgt_file, "tgt_sheet")
            st.success(
                f"✅ **{target_payload['name']}** — "
                f"{target_payload['row_count']:,} rows × {target_payload['col_count']} cols"
            )
            with st.expander("👁️ Preview Target (top 5 rows)"):
                st.dataframe(_safe_df(target_payload["df"].head(5)), use_container_width=True)
        except ValueError as exc:
            st.error(str(exc))
        except PermissionError:
            st.error("Please close the target file and retry.")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — AUTO-MAPPING + RUN (only when both files are ready)
# ══════════════════════════════════════════════════════════════════════════════
if source_payload and target_payload:

    # ── Auto-detect mapping ────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🔗 Detected Column Mapping")
    st.caption(
        "The tool automatically matched source and target columns. "
        "Key columns identify matching rows; the Compare column is checked for quantity differences."
    )

    try:
        mapping_result = auto_map_columns(source_payload["df"], target_payload["df"])
    except Exception as exc:
        st.error(f"Auto-mapping failed: {exc}")
        st.stop()

    display_rows = mapping_result["display"]
    if not display_rows:
        st.error("Could not detect any column mapping. Please ensure columns have meaningful names.")
        st.stop()

    mapping_table = pd.DataFrame(display_rows)[["logical", "source_col", "target_col", "role"]]
    mapping_table.columns = ["Logical Field", "Source Column", "Target Column", "Role"]
    st.table(mapping_table)

    has_compare = any(r["role"] == "📊 Compare" for r in display_rows)
    if not has_compare:
        st.warning(
            "⚠️ No quantity/compare column was detected. "
            "Ensure at least one column contains numeric values."
        )

    if not any(r["role"] == "🔑 Key" for r in display_rows):
        st.error("No key columns detected. Cannot proceed with comparison.")
        st.stop()

    # ── Run ────────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("⚙️ Step 2 — Run Comparison")

    run_clicked = st.button("🚀 RUN COMPARISON", type="primary")

    if run_clicked:
        st.session_state.run_output = None
        st.session_state.run_summary = None
        st.session_state.annotated_df = None

        progress = st.progress(0, text="Initialising…")
        status = st.empty()

        try:
            status.info("Validating column mapping…")
            mapper = ColumnMapper(mapping_result["mapping"])
            mapper.validate(source_payload["df"], target_payload["df"])
            progress.progress(20, text="Mapping validated")

            status.info("Building composite keys…")
            comparator = ExcelComparator(source_payload["df"], target_payload["df"], mapper)
            progress.progress(40, text="Keys built")

            with st.spinner("Comparing rows…"):
                annotated_df, summary = comparator.run([1, 2, 3, 4])
            progress.progress(70, text="Comparison done")

            status.info("Writing annotated Excel…")
            output = write_annotated_excel(
                annotated_df,
                original_target_path=BytesIO(target_payload["bytes"]),
                sheet_name=target_payload["active_sheet"],
            )
            progress.progress(90, text="Excel written")

            st.session_state.annotated_df = annotated_df
            st.session_state.run_summary = summary
            st.session_state.run_output = output.getvalue()
            progress.progress(100, text="Done ✅")
            status.success("Comparison complete.")

        except ValueError as exc:
            st.warning(str(exc))
        except PermissionError:
            st.error("Please close the target file and retry.")
        except Exception as exc:
            st.error(f"Comparison failed: {exc}")

    # ── Results ───────────────────────────────────────────────────────────────
    if st.session_state.run_summary is not None and st.session_state.annotated_df is not None:
        summary = st.session_state.run_summary
        annotated_df = st.session_state.annotated_df.copy()
        annotated_df["Scenario"] = annotated_df["Remarks"].apply(classify_remark)

        st.markdown("---")
        st.subheader("📊 Summary Report")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("✅ Matched", summary.get("matched", 0))
        m2.metric("⚠️ Qty Mismatch", summary.get("qty_mismatch", 0))
        m3.metric("❌ Missing in Target", summary.get("missing_in_target", 0))
        m4.metric("🔶 Extra in Target", summary.get("extra_in_target", 0))

        chart_df = pd.DataFrame(
            {
                "Scenario": ["Matched", "Qty Mismatch", "Missing in Target", "Extra in Target"],
                "Count": [
                    summary.get("matched", 0),
                    summary.get("qty_mismatch", 0),
                    summary.get("missing_in_target", 0),
                    summary.get("extra_in_target", 0),
                ],
            }
        )
        fig = px.bar(
            chart_df,
            x="Scenario",
            y="Count",
            color="Scenario",
            title="Scenario Breakdown",
            color_discrete_map={
                "Matched": "#C6EFCE",
                "Qty Mismatch": "#FFEB9C",
                "Missing in Target": "#FFC7CE",
                "Extra in Target": "#FFD18C",
            },
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

        filter_options = [
            "All",
            "MATCHED",
            "QTY MISMATCH",
            "MISSING IN TARGET",
            "EXTRA IN TARGET",
            "Unremarked",
        ]
        filter_val = st.selectbox("Filter by scenario", filter_options, key="result_filter")
        display_df = (
            annotated_df
            if filter_val == "All"
            else annotated_df[annotated_df["Scenario"] == filter_val]
        )
        st.dataframe(
            _safe_df(display_df.drop(columns=["Scenario"])),
            use_container_width=True,
        )

        st.markdown("---")
        output_name = get_output_filename(target_payload["name"])
        st.download_button(
            label="⬇️ Download Annotated Target Excel",
            data=st.session_state.run_output,
            file_name=output_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
        st.caption(f"File: **{output_name}** — Original Target columns + Remarks")
        st.success("✅ Comparison complete! File ready for download.")
