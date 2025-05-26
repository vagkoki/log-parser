import streamlit as st
import pandas as pd
import altair as alt
from log_utils import run_parser, REGEX_PATTERNS

def process_windows_log(uploaded_file, parser_choice, **kwargs):
    
    log_format = '<Date> <Time>, <Level> <Component> <Content>'
    regex = REGEX_PATTERNS["Windows"]
    return run_parser(uploaded_file, parser_choice, log_format, regex, **kwargs)

def show_dashboard(df_structured):
    """Δημιουργεί τα γραφήματα και τα widgets για το Dashboard"""


    # === Filters για Windows ===
    levels_available = df_structured["Level"].dropna().unique().tolist()
    components_available = df_structured["Component"].dropna().unique().tolist()
    
    min_date = pd.to_datetime(df_structured["Date"]).min().date()
    max_date = pd.to_datetime(df_structured["Date"]).max().date()
    
    all_levels_option = "ALL"
    all_components_option = "ALL"
    
    level_options = [all_levels_option] + levels_available
    component_options = [all_components_option] + components_available
    
    col1, col2, col3 = st.columns(3)
    
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
        selected_date_range = st.date_input("Επέλεξε Ημερομηνίες:", value=[min_date, max_date])
    
    st.markdown("---")
    
    # Εφαρμογή φίλτρων
    filtered_df = df_structured[
        df_structured["Level"].isin(selected_levels) &
        df_structured["Component"].isin(selected_components) &
        (pd.to_datetime(df_structured["Date"]) >= pd.to_datetime(selected_date_range[0])) &
        (pd.to_datetime(df_structured["Date"]) <= pd.to_datetime(selected_date_range[1]))
    ]
    if filtered_df.empty:
        st.warning("⚠️ Δεν υπάρχουν δεδομένα για τα επιλεγμένα φίλτρα. Παρακαλώ δοκιμάστε άλλες επιλογές.")
        return  # Σταματάει την εκτέλεση της συνάρτησης εδώ
    
    # Δημιουργούμε στήλη datetime από Date + Time
    filtered_df["datetime"] = pd.to_datetime(filtered_df["Date"] + " " + filtered_df["Time"], errors="coerce")
    
    # Parse χρόνος αν υπάρχει
    try:
        filtered_df["ParsedTime"] = pd.to_datetime(filtered_df["Time"], errors="coerce")
    except:
        filtered_df["ParsedTime"] = pd.NaT
    
    df_valid_time = filtered_df.dropna(subset=["ParsedTime"])
    
    # Μετρήσεις πάνω
    total_logs = len(filtered_df)
    unique_templates = filtered_df["EventTemplate"].nunique() if "EventTemplate" in filtered_df else "N/A"
    

    time_range = "N/A"
    if not filtered_df["datetime"].isna().all():
        start = filtered_df["datetime"].min()
        end = filtered_df["datetime"].max()
        delta = end - start
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        time_range = f"{days}D, " if days > 0 else ""
        time_range += f"{hours:02d}h, {minutes:02d}m"
    
    # Υπολογίζουμε τον αριθμό των στηλών (όσες οι τιμές του Level + 3 για τα σταθερά widgets)
    unique_levels = filtered_df["Level"].unique()
    num_columns = len(unique_levels) + 3  # 3 για τα σταθερά widgets
    
    # Δημιουργούμε δυναμικά τις στήλες
    cols = st.columns(num_columns)
    
    # Σταθερά widgets
    with cols[0]:
        st.caption("Συνολικές Εγγραφές")
        st.markdown(f"<h2 style='padding-top: 0px; padding-bottom: 0px;'>{total_logs}</h2>", unsafe_allow_html=True)
            
    with cols[1]:
        st.caption("Μοναδικά Templates")
        st.markdown(f"<h2 style='padding-top: 0px; padding-bottom: 0px;'>{unique_templates}</h2>", unsafe_allow_html=True)
    
    # Δημιουργούμε ένα widget για κάθε μοναδικό επίπεδο "Level"
    for i, level in enumerate(unique_levels):
        count = filtered_df[filtered_df["Level"] == level].shape[0]
        with cols[i + 2]:  # Αρχίζουμε από την 3η στήλη για τα "Level" widgets
            st.caption(f"{level} Logs")
            st.markdown(f"<h2 style='color:{get_color_for_level(level)}; padding-top: 0px; padding-bottom: 0px;'>{count}</h2>", unsafe_allow_html=True)
    
    # Σταθερό widget για τη χρονική περίοδο
    with cols[-1]:  # Χρησιμοποιούμε την τελευταία στήλη
        st.caption("Χρονική Περίοδος")
        st.markdown(f"<h2 style='padding-top: 0px; padding-bottom: 0px;'>{time_range}</h2>", unsafe_allow_html=True)                    
    
    st.markdown("---")
                    
    
    # 1. Προετοιμασία δεδομένων για το line chart

    # Εξασφαλίζουμε ότι η στήλη "Level" έχει τις σωστές τιμές (π.χ., INFO, WARNING, ERROR)
    filtered_df["Level"] = filtered_df["Level"].str.upper()
    
    # Ομαδοποιούμε τα δεδομένα κατά datetime και Level, ώστε να έχουμε ένα count για κάθε επίπεδο και κάθε χρονική στιγμή
    df_resample = filtered_df.set_index("datetime")
    
    # Ομαδοποιούμε κατά datetime και Level, και υπολογίζουμε τον αριθμό για κάθε επίπεδο
    resampled = (
        df_resample.groupby([pd.Grouper(freq="1min"), "Level"])  # Χρησιμοποιούμε το πεδίο "Level"
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )
    
    # Επαναμορφοποίηση σε long format για να χρησιμοποιηθεί στο γράφημα
    df_long = resampled.melt(id_vars="datetime", var_name="Log Level", value_name="Count")

    
    # 2. Bar Chart για top 10 templates
    fig_templates = None
    if "EventTemplate" in filtered_df.columns:
        top_templates = filtered_df["EventTemplate"].value_counts().nlargest(10).reset_index()
        top_templates.columns = ["EventTemplate", "Count"]
        
        fig_templates = alt.Chart(top_templates).mark_bar().encode(
            x=alt.X("Count:Q", title="Συχνότητα"),
            y=alt.Y("EventTemplate:N", sort='-x', title="Event Template"),
            tooltip=["EventTemplate:N", "Count:Q"],
            color=alt.value("#4C78A8")
        ).properties(width=700, height=400)

    # Τοποθέτηση των 2 γραφημάτων δίπλα δίπλα
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        # Χρήση st.line_chart (wide format)
        st.markdown("📈 Χρονική Κατανομή Logs ανά λεπτό")
        st.line_chart(
            data=df_long,
            x="datetime",
            y="Count",
            color="Log Level",  # Χρησιμοποιούμε την στήλη "Log Level" για τα χρώματα
            use_container_width=True
        )
    
    with col_chart2:
        st.markdown("📊 Τα Log Templates με τις περισσότερες εμφανίσεις")
        if fig_templates:
            st.altair_chart(fig_templates, use_container_width=True)
    
    # 3. Treemap
    st.markdown("📊 Ομαδοποιημένο Ραβδόγραμμα ανά Component & Template")
    if "Component" in filtered_df.columns and "EventTemplate" in filtered_df.columns:
        # Ομαδοποίηση των δεδομένων κατά Component και EventTemplate
        bar_df = filtered_df.groupby(["Component", "EventTemplate"]).size().reset_index(name="Count")
            
        # Δημιουργία του Grouped Bar Chart με Altair
        fig_bar = alt.Chart(bar_df).mark_bar().encode(
            x=alt.X("Count:Q", title="Αριθμός Εμφανίσεων"),
            y=alt.Y("EventTemplate:N", sort='-x', title="Event Template"),
            color=alt.Color("Component:N", legend=alt.Legend(title="Component")),
            tooltip=["Component", "EventTemplate", "Count"]
        ).properties(
            width=800,
            height=400,
        )
            
        # Εμφάνιση του γραφήματος
        st.altair_chart(fig_bar, use_container_width=True)
        
    # 4. HEATMAP (Component vs Level)
    st.markdown("🌡️ Heatmap Κατανομής Component ανά Level")
    df_heatmap = filtered_df.groupby(["Component", "Level"]).size().reset_index(name="Count")
    
    chart_heatmap = alt.Chart(df_heatmap).mark_rect().encode(
        x=alt.X("Level:N"),
        y=alt.Y("Component:N"),
        color=alt.Color("Count:Q", scale=alt.Scale(scheme='viridis')),
        tooltip=["Component:N", "Level:N", "Count:Q"]
    ).properties(
        width=600,
        height=400,
    )
    st.altair_chart(chart_heatmap, use_container_width=True)
            
        
def get_color_for_level(level):
    color_map = {
        "Info": "#528AFF",
        "Warning": "#F7B84B",
        "Error": "#F06548",
        "Debug": "#00BFFF",  # Πρόσθετο παράδειγμα για DEBUG
    }
    return color_map.get(level, "#528AFF")  # Επιστρέφει μπλε αν το level δεν υπάρχει στο color_map