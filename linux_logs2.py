import streamlit as st
import pandas as pd
import altair as alt
import plotly.express as px
from log_utils import run_parser, REGEX_PATTERNS

def process_linux_log(uploaded_file, parser_choice, **kwargs):
   
    log_format = '<Month> <Date> <Time> <Level> (<Component>)?(\[<PID>\])?: <Content>'
    regex = REGEX_PATTERNS["Windows"]
    return run_parser(uploaded_file, parser_choice, log_format, regex, **kwargs)

def show_dashboard(df_structured):
    """Dashboard για Linux Logs με filters, widgets και γραφήματα"""

    # === Δημιουργία datetime column από Month + Date + Time (προσθέτουμε default year)
    current_year = pd.Timestamp.now().year
    df_structured["datetime"] = pd.to_datetime(
        df_structured["Month"] + " " + df_structured["Date"].astype(str) + " " + str(current_year) + " " + df_structured["Time"],
        errors="coerce"
    )

    # === Filters ===
    levels_available = df_structured["Level"].dropna().unique().tolist()
    components_available = df_structured["Component"].dropna().unique().tolist()
    pids_available = df_structured["PID"].dropna().unique().tolist()
    
    min_date = df_structured["datetime"].dt.date.min()
    max_date = df_structured["datetime"].dt.date.max()
    
    all_levels_option = "ALL"
    all_components_option = "ALL"
    all_pids_option = "ALL"
    
    level_options = [all_levels_option] + levels_available
    component_options = [all_components_option] + components_available
    pid_options = [all_pids_option] + pids_available
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        selected = st.multiselect("Επέλεξε Level(s):", level_options)
        if all_levels_option in selected or not selected:
            selected_levels = levels_available
        else:
            selected_levels = selected
    
    with col2:
        selected = st.multiselect("Επέλεξε Component(s):", component_options)
        if all_components_option in selected or not selected:
            selected_components = components_available
        else:
            selected_components = selected
    
    with col3:
        selected = st.multiselect("Επέλεξε PID(s):", pid_options)
        if all_pids_option in selected or not selected:
            selected_pids = pids_available
        else:
            selected_pids = selected
    
    with col4:
        selected_date_range = st.date_input("Επέλεξε Ημερομηνίες:", value=[min_date, max_date])
    
    st.markdown("---")

    # === Εφαρμογή φίλτρων ===
    filtered_df = df_structured[
        df_structured["Level"].isin(selected_levels) &
        df_structured["Component"].isin(selected_components) &
        df_structured["PID"].isin(selected_pids) &
        (df_structured["datetime"].dt.date >= selected_date_range[0]) &
        (df_structured["datetime"].dt.date <= selected_date_range[1])
    ]

    if filtered_df.empty:
        st.warning("⚠️ Δεν υπάρχουν δεδομένα για τα επιλεγμένα φίλτρα. Δοκιμάστε άλλες επιλογές.")
        return

    # === Metrics Widgets ===
    total_logs = len(filtered_df)
    unique_templates = filtered_df["EventTemplate"].nunique()
    unique_components = filtered_df["Component"].nunique()
    unique_pids = filtered_df["PID"].nunique()

    if not filtered_df["datetime"].isna().all():
        start = filtered_df["datetime"].min()
        end = filtered_df["datetime"].max()
        delta = end - start
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        time_range = f"{days}D, {hours:02d}h, {minutes:02d}m"
    else:
        time_range = "N/A"

    unique_levels = filtered_df["Level"].unique()
    num_columns = len(unique_levels) + 4  # 4 σταθερά widgets

    cols = st.columns(num_columns)

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
        st.caption("Μοναδικά PIDs")
        st.markdown(f"<h2>{unique_pids}</h2>", unsafe_allow_html=True)

    for i, level in enumerate(unique_levels):
        count = filtered_df[filtered_df["Level"] == level].shape[0]
        with cols[i + 4]:
            st.caption(f"{level} Logs")
            st.markdown(f"<h2 style='color:{get_color_for_level(level)}'>{count}</h2>", unsafe_allow_html=True)

    st.markdown("---")

    # === Stacked Area Chart (Level over time) ===
    df_resample = filtered_df.set_index("datetime")
    resampled = df_resample.groupby([pd.Grouper(freq="1min"), "Level"]).size().unstack(fill_value=0).reset_index()
    df_long = resampled.melt(id_vars="datetime", var_name="Log Level", value_name="Count")

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("📈 Χρονική Κατανομή Logs ανά λεπτό")
        st.line_chart(
            data=df_long,
            x="datetime",
            y="Count",
            color="Log Level",
            use_container_width=True
        )

    # === Bar Chart (Top EventTemplates) ===
    with col_chart2:
        st.markdown("📊 Τα Log Templates με τις περισσότερες εμφανίσεις")
        if "EventTemplate" in filtered_df.columns:
            top_templates = filtered_df["EventTemplate"].value_counts().nlargest(10).reset_index()
            top_templates.columns = ["EventTemplate", "Count"]
            chart_templates = alt.Chart(top_templates).mark_bar().encode(
                x=alt.X("Count:Q", title="Συχνότητα"),
                y=alt.Y("EventTemplate:N", sort="-x", title="Event Template"),
                tooltip=["EventTemplate:N", "Count:Q"],
                color=alt.value("#4C78A8")
            ).properties(width=700, height=400)
            st.altair_chart(chart_templates, use_container_width=True)
            
    # === Grouped Bar (Component + EventTemplate) ===
    st.markdown("📊 Ομαδοποιημένο Ραβδόγραμμα ανά Component & Log Level")
    if "Level" in filtered_df.columns and "Component" in filtered_df.columns:
        bar_df = filtered_df.groupby(["Level", "Component"]).size().reset_index(name="Count")
        fig_bar = alt.Chart(bar_df).mark_bar().encode(
            x=alt.X("Count:Q", title="Αριθμός Εμφανίσεων"),
            y=alt.Y("Component:N", sort='-x', title="Component"),
            color=alt.Color("Level:N", legend=alt.Legend(title="Level")),
            tooltip=["Level", "Component", "Count"]
        ).properties(width=800, height=400)
        st.altair_chart(fig_bar, use_container_width=True)
        
    # === Heatmap (Component vs Level) ===
    st.markdown("🌡️ Heatmap Κατανομής Component ανά Timestamp")
    df_heatmap = filtered_df.groupby(["Component", "datetime"]).size().reset_index(name="Count")
    
    fig = px.density_heatmap(
        df_heatmap,
        x="datetime",
        y="Component",
        z="Count",
        nbinsx=100,  # προσαρμόζεται ανάλογα με το πλήθος των logs
        color_continuous_scale="Viridis",
        labels={"datetime": "Χρόνος", "Component": "Component", "Count": "Logs"},
    )
    
    fig.update_layout(
        xaxis_title="Χρόνος",
        yaxis_title="Component",
        xaxis_tickformat="%d-%m %H:%M",
        autosize=True,
        height=500
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # === Προαιρετικό Scatter Plot (PID vs Time) ===
    st.markdown("🔬 Scatter Plot PID ανά Timestamp")
    if "PID" in filtered_df.columns:
        scatter_df = filtered_df.dropna(subset=["PID", "datetime"])
        scatter_plot = alt.Chart(scatter_df).mark_circle(size=60).encode(
            x=alt.X("datetime:T", title="Χρόνος"),
            y=alt.Y("PID:N", title="PID"),
            color=alt.Color("Level:N"),
            tooltip=["datetime:T", "PID:N", "Level:N", "PID:N"]
        ).properties(width=800, height=400)
        st.altair_chart(scatter_plot, use_container_width=True)
        
def get_color_for_level(level):
    color_map = {
        "INFO": "#528AFF",
        "WARNING": "#F7B84B",
        "ERROR": "#F06548",
        "DEBUG": "#00BFFF",  # Πρόσθετο παράδειγμα για DEBUG
    }
    return color_map.get(level, "#528AFF")  # Επιστρέφει μπλε αν το level δεν υπάρχει στο color_map
