import streamlit as st
import pandas as pd
import altair as alt
from log_utils import run_parser, REGEX_PATTERNS

def process_suricata_log(uploaded_file, parser_choice, **kwargs):
    
    log_format = '<Month>/<Date>/<Year>-<Time>\.<Ms> \[\*\*\] (\[<SID>:<Revision>\]) ET <EventType> <Content> \[\*\*\] (\[Classification: <ClassDescription>\]) (\[Priority: <PriorityValue>\]) {<Protocol>} <SrcIP>:<SrcPort> -> <DstIP>:<DstPort>'
    regex = REGEX_PATTERNS["Windows"]
    return run_parser(uploaded_file, parser_choice, log_format, regex, **kwargs)

def show_dashboard(df_structured):
    """Dashboard για Suricata Logs με filters, widgets και γραφήματα"""

    # Δημιουργούμε στήλη datetime
    df_structured["Year"] = df_structured["Year"].astype(str)
    df_structured["Month"] = df_structured["Month"].astype(str).str.zfill(2)
    df_structured["Date"] = df_structured["Date"].astype(str).str.zfill(2)
    df_structured["Time"] = df_structured["Time"].astype(str)
    
    df_structured["datetime"] = pd.to_datetime(
        df_structured["Year"] + "-" +
        df_structured["Month"] + "-" +
        df_structured["Date"] + " " +
        df_structured["Time"],
        errors="coerce"
    )  

    # === Filters ===
    eventtypes_available = df_structured["EventType"].dropna().unique().tolist()
    classes_available = df_structured["ClassDescription"].dropna().unique().tolist()
    protocols_available = df_structured["Protocol"].dropna().unique().tolist()
    srcports_available = df_structured["SrcPort"].dropna().unique().tolist()
    dstports_available = df_structured["DstPort"].dropna().unique().tolist()

    min_date = df_structured["datetime"].dt.date.min()
    max_date = df_structured["datetime"].dt.date.max()

    # Προσθήκη επιλογής ALL
    all_eventtypes_option = "ALL"
    all_classes_option = "ALL"
    all_protocols_option = "ALL"
    all_srcports_option = "ALL"
    all_dstports_option = "ALL"

    eventtype_options = [all_eventtypes_option] + eventtypes_available
    class_options = [all_classes_option] + classes_available
    protocol_options = [all_protocols_option] + protocols_available
    srcport_options = [all_srcports_option] + srcports_available
    dstport_options = [all_dstports_option] + dstports_available

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        selected = st.multiselect("Επέλεξε EventType(s):", eventtype_options)
        selected_eventtypes = eventtypes_available if all_eventtypes_option in selected or not selected else selected

    with col2:
        selected = st.multiselect("Επέλεξε Class(es):", class_options)
        selected_classes = classes_available if all_classes_option in selected or not selected else selected

    with col3:
        selected = st.multiselect("Επέλεξε Protocol(s):", protocol_options)
        selected_protocols = protocols_available if all_protocols_option in selected or not selected else selected

    with col4:
        selected = st.multiselect("Επέλεξε SrcPort(s):", srcport_options)
        selected_srcports = srcports_available if all_srcports_option in selected or not selected else selected

    with col5:
        selected = st.multiselect("Επέλεξε DstPort(s):", dstport_options)
        selected_dstports = dstports_available if all_dstports_option in selected or not selected else selected

    with col6:
        selected_date_range = st.date_input("Ημερομηνίες:", value=[min_date, max_date])

    st.markdown("---")

    # === Εφαρμογή φίλτρων ===
    filtered_df = df_structured[
        df_structured["EventType"].isin(selected_eventtypes) &
        df_structured["ClassDescription"].isin(selected_classes) &
        df_structured["Protocol"].isin(selected_protocols) &
        df_structured["SrcPort"].isin(selected_srcports) &
        df_structured["DstPort"].isin(selected_dstports) &
        (df_structured["datetime"].dt.date >= selected_date_range[0]) &
        (df_structured["datetime"].dt.date <= selected_date_range[1])
    ]

    if filtered_df.empty:
        st.warning("⚠️ Δεν υπάρχουν δεδομένα για τα επιλεγμένα φίλτρα. Δοκιμάστε άλλες επιλογές.")
        return

    # === Widgets ===
    total_logs = len(filtered_df)
    unique_templates = filtered_df["EventTemplate"].nunique()
    unique_eventtypes = filtered_df["EventType"].nunique()
    unique_classes = filtered_df["ClassDescription"].nunique()
    unique_protocols = filtered_df["Protocol"].nunique()

    cols = st.columns(5)

    with cols[0]:
        st.caption("Συνολικές Εγγραφές")
        st.markdown(f"<h2>{total_logs}</h2>", unsafe_allow_html=True)

    with cols[1]:
        st.caption("Μοναδικά Templates")
        st.markdown(f"<h2>{unique_templates}</h2>", unsafe_allow_html=True)

    with cols[2]:
        st.caption("Μοναδικά EventTypes")
        st.markdown(f"<h2>{unique_eventtypes}</h2>", unsafe_allow_html=True)

    with cols[3]:
        st.caption("Μοναδικά ClassDescriptions")
        st.markdown(f"<h2>{unique_classes}</h2>", unsafe_allow_html=True)

    with cols[4]:
        st.caption("Μοναδικά Protocols")
        st.markdown(f"<h2>{unique_protocols}</h2>", unsafe_allow_html=True)

    st.markdown("---")

    # === Προετοιμασία line chart ===
    df_resample = filtered_df.set_index("datetime")
    resampled = df_resample.groupby(pd.Grouper(freq="1min")).size().reset_index(name="Count")

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("📈 Χρονική Κατανομή Logs ανά λεπτό")
        st.line_chart(data=resampled, x="datetime", y="Count", use_container_width=True)

    with col_chart2:
        st.markdown("📊 Τα Log Templates με τις περισσότερες εμφανίσεις")
        if "EventTemplate" in filtered_df.columns:
            top_templates = filtered_df["EventTemplate"].value_counts().nlargest(10).reset_index()
            top_templates.columns = ["EventTemplate", "Count"]
            chart_templates = alt.Chart(top_templates).mark_bar().encode(
                x=alt.X("Count:Q", title="Συχνότητα"),
                y=alt.Y("EventTemplate:N", sort='-x', title="Event Template"),
                tooltip=["EventTemplate:N", "Count:Q"],
                color=alt.value("#4C78A8")
            ).properties(width=700, height=400)
            st.altair_chart(chart_templates, use_container_width=True)

    # === Grouped Bar Chart: EventType + PriorityValue ===
    st.markdown("📊 Ομαδοποιημένο Ραβδόγραμμα EventType & PriorityValue")
    
    if "EventType" in filtered_df.columns and "PriorityValue" in filtered_df.columns:
        # Μετατροπή PriorityValue σε κατηγορικό για να ελεγχθεί η σειρά
        filtered_df["PriorityValue"] = filtered_df["PriorityValue"].astype(str)
    
        priority_df = filtered_df.groupby(["EventType", "PriorityValue"]).size().reset_index(name="Count")
        color_scale = alt.Scale(
            domain=["1", "2", "3"],
            range=["#F06548", "#F7B84B", "#28C76F"]
        )    
        grouped_bar = alt.Chart(priority_df).mark_bar().encode(
            x=alt.X("Count:Q", title="Αριθμός Logs"),
            y=alt.Y("EventType:N", sort='-x', title="EventType"),
            color=alt.Color("PriorityValue:N", title="Priority", scale=color_scale),
            tooltip=["EventType", "PriorityValue", "Count"]
        ).properties(width=800, height=400)
    
        st.altair_chart(grouped_bar, use_container_width=True)

    # === Heatmap SrcPort vs DstPort ===
    st.markdown("🌡️ Heatmap SrcPort vs DstPort")
    if "SrcPort" in filtered_df.columns and "DstPort" in filtered_df.columns:
        heatmap_df = filtered_df.groupby(["SrcPort", "DstPort"]).size().reset_index(name="Count")
        chart_heatmap = alt.Chart(heatmap_df).mark_rect().encode(
            x=alt.X("SrcPort:N"),
            y=alt.Y("DstPort:N"),
            color=alt.Color("Count:Q", scale=alt.Scale(scheme='viridis')),
            tooltip=["SrcPort:N", "DstPort:N", "Count:Q"]
        ).properties(width=700, height=400)
        st.altair_chart(chart_heatmap, use_container_width=True)

    # === Scatter Plot: Όλες οι IPs (Src & Dst) με Χρωματισμό ανά EventType ===
    st.markdown("🔬 Scatter Plot: IP Διευθύνσεις ανά EventType με Χρονική Κατανομή")
    
    required_cols = {"EventType", "SrcIP", "DstIP", "datetime"}
    
    if required_cols.issubset(filtered_df.columns):
        ip_df = filtered_df.copy()
    
        # Μετατροπή σε long format (SrcIP/DstIP σε κοινή στήλη IP_Address)
        ip_long = pd.melt(
            ip_df,
            id_vars=["datetime", "EventType", "Protocol"],
            value_vars=["SrcIP", "DstIP"],
            var_name="IP_Type",         # SrcIP ή DstIP
            value_name="IP_Address"     # IP string
        )
    
        # Chart
        scatter_all = alt.Chart(ip_long).mark_circle(size=50, opacity=0.6).encode(
            x=alt.X("datetime:T", title="Χρόνος"),
            y=alt.Y("IP_Address:N", title="Διεύθυνση IP"),
            color=alt.Color("EventType:N", title="Κατηγορία Συμβάντος"),
            tooltip=[
                alt.Tooltip("datetime:T", title="Χρόνος"),
                alt.Tooltip("IP_Address:N", title="Διεύθυνση IP"),
                alt.Tooltip("IP_Type:N", title="Τύπος IP"),
                alt.Tooltip("EventType:N", title="Event Type"),
                alt.Tooltip("Protocol:N", title="Πρωτόκολλο")
            ]
        ).properties(
            width=800,
            height=450
        )
    
        st.altair_chart(scatter_all, use_container_width=True)
    else:
        st.info("Λείπουν απαραίτητα πεδία για την εμφάνιση του γραφήματος.")