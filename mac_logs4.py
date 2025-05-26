import streamlit as st
import pandas as pd
import altair as alt
import plotly.express as px
from log_utils import run_parser, REGEX_PATTERNS
from datetime import timedelta

def process_mac_log(uploaded_file, parser_choice, **kwargs):
       
    log_format = '<Month>  <Date> <Time> <User> <Component>\[<PID>\]( \(<Address>\))?: <Content>'
    regex = REGEX_PATTERNS["Windows"]
    return run_parser(uploaded_file, parser_choice, log_format, regex, **kwargs)

def show_dashboard(df_structured):
    """Dashboard για Mac Logs χωρίς Level, με filters, widgets και γραφήματα"""

    # === Δημιουργία datetime από Month + Date + Time + Year ===
    current_year = pd.Timestamp.now().year
    df_structured["datetime"] = pd.to_datetime(
        df_structured["Month"] + " " + df_structured["Date"].astype(str) + " " + str(current_year) + " " + df_structured["Time"],
        errors="coerce"
    )

    # === Filters ===
    components_available = df_structured["Component"].dropna().unique().tolist()
    users_available = df_structured["User"].dropna().unique().tolist()
    pids_available = df_structured["PID"].dropna().unique().tolist()

    min_date = df_structured["datetime"].dt.date.min()
    max_date = df_structured["datetime"].dt.date.max()

    all_components_option = "ALL"
    all_users_option = "ALL"
    all_pids_option = "ALL"

    component_options = [all_components_option] + components_available
    user_options = [all_users_option] + users_available
    pid_options = [all_pids_option] + pids_available

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        selected = st.multiselect("Επέλεξε Component(s):", component_options)
        if all_components_option in selected or not selected:
            selected_components = components_available
        else:
            selected_components = selected

    with col2:
        selected = st.multiselect("Επέλεξε User(s):", user_options)
        if all_users_option in selected or not selected:
            selected_users = users_available
        else:
            selected_users = selected

    with col3:
        selected = st.multiselect("Επέλεξε PID(s):", pid_options)
        if all_pids_option in selected or not selected:
            selected_pids = pids_available
        else:
            selected_pids = selected

    with col4:
        selected_date_range = st.date_input("Ημερομηνίες:", value=[min_date, max_date])

    st.markdown("---")

    # === Εφαρμογή φίλτρων ===
    filtered_df = df_structured[
        df_structured["Component"].isin(selected_components) &
        df_structured["User"].isin(selected_users) &
        df_structured["PID"].isin(selected_pids) &
        (df_structured["datetime"].dt.date >= selected_date_range[0]) &
        (df_structured["datetime"].dt.date <= selected_date_range[1])
    ]

    if filtered_df.empty:
        st.warning("⚠️ Δεν υπάρχουν δεδομένα για τα επιλεγμένα φίλτρα. Δοκιμάστε άλλες επιλογές.")
        return

    # === Widgets ===
    total_logs = len(filtered_df)
    unique_templates = filtered_df["EventTemplate"].nunique()
    unique_components = filtered_df["Component"].nunique()
    unique_users = filtered_df["User"].nunique()
    unique_pids = filtered_df["PID"].nunique()

    cols = st.columns(5)

    with cols[0]:
        st.caption("Συνολικές Εγγραφές")
        st.markdown(f"<h2>{total_logs}</h2>", unsafe_allow_html=True)

    with cols[1]:
        st.caption("Μοναδικά Templates")
        st.markdown(f"<h2>{unique_templates}</h2>", unsafe_allow_html=True)

    with cols[2]:
        st.caption("Μοναδικά Components")
        st.markdown(f"<h2>{unique_components}</h2>", unsafe_allow_html=True)

    with cols[3]:
        st.caption("Μοναδικοί Χρήστες")
        st.markdown(f"<h2>{unique_users}</h2>", unsafe_allow_html=True)

    with cols[4]:
        st.caption("Μοναδικά PIDs")
        st.markdown(f"<h2>{unique_pids}</h2>", unsafe_allow_html=True)

    st.markdown("---")

    # === Προετοιμασία δεδομένων για line chart ===
    df_resample = filtered_df.set_index("datetime")
    resampled = df_resample.groupby(pd.Grouper(freq="1min")).size().reset_index(name="Count")

    # === Τοποθέτηση 2 γραφημάτων δίπλα-δίπλα ===
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("📈 Χρονική Κατανομή Logs ανά λεπτό")
        st.line_chart(data=resampled, x="datetime", y="Count", use_container_width=True)

    with col_chart2:
        st.markdown("📊 Τα Components με τις περισσότερες εμφανίσεις")
        if "Component" in filtered_df.columns:
            top_templates = filtered_df["Component"].value_counts().nlargest(10).reset_index()
            top_templates.columns = ["Component", "Count"]
            chart_templates = alt.Chart(top_templates).mark_bar().encode(
                x=alt.X("Count:Q", title="Συχνότητα"),
                y=alt.Y("Component:N", sort='-x', title="Component"),
                tooltip=["Component:N", "Count:Q"],
                color=alt.value("#4C78A8")
            ).properties(width=700, height=400)
            st.altair_chart(chart_templates, use_container_width=True)
        
    # === Stacked Bar Chart: Χρονική Κατανομή Δραστηριότητας για τα Top Components ===
    st.markdown("📊 Χρονική Κατανομή Δραστηριότητας για τα Top Components")
    
    start_time = filtered_df["datetime"].min()
    end_time = filtered_df["datetime"].max()
    delta = end_time - start_time
    
    if delta <= timedelta(hours=1):
        freq = "1min"
    elif delta <= timedelta(hours=6):
        freq = "5min"
    elif delta <= timedelta(days=1):
        freq = "15min"
    elif delta <= timedelta(days=3):
        freq = "30min"
    elif delta <= timedelta(days=7):
        freq = "1H"
    elif delta <= timedelta(days=30):
        freq = "3H"
    else:
        freq = "1D"
    
    filtered_df["datetime_grouped"] = filtered_df["datetime"].dt.floor(freq)
    
    top_n = 10
    top_components = filtered_df["Component"].value_counts().nlargest(top_n).index.tolist()
    filtered_df["Component_TopN"] = filtered_df["Component"].apply(
        lambda x: x if x in top_components else "Άλλο"
    )
    
    grouped = filtered_df.groupby(["datetime_grouped", "Component_TopN"]).size().reset_index(name="Count")
    
    stacked_chart = alt.Chart(grouped).mark_bar().encode(
        x=alt.X("datetime_grouped:T", title=f"Χρόνος (ανά {freq})"),
        y=alt.Y("Count:Q", title="Αριθμός Logs"),
        color=alt.Color("Component_TopN:N", title="Component"),
        tooltip=["datetime_grouped:T", "Component_TopN:N", "Count:Q"]
    ).properties(width=800, height=400)
    
    st.altair_chart(stacked_chart, use_container_width=True)

    # === Scatter Plot (PID vs Time) ===
    st.markdown("🔬 Scatter Plot PID ανά Χρόνο")
    if "PID" in filtered_df.columns:
        scatter_df = filtered_df.dropna(subset=["PID", "datetime"])
        scatter_plot = alt.Chart(scatter_df).mark_circle(size=60).encode(
            x=alt.X("datetime:T", title="Χρόνος"),
            y=alt.Y("PID:N", title="PID"),
            color=alt.Color("User:N"),
            tooltip=["datetime:T", "PID:N", "Component:N", "User:N"]
        ).properties(width=800, height=400)
        st.altair_chart(scatter_plot, use_container_width=True)
