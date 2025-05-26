import streamlit as st
import importlib
from windows_logs3 import process_windows_log as process_windows, show_dashboard as show_dashboard_windows  # Εισαγωγή από windows_logs.py
from linux_logs2 import process_linux_log as process_linux, show_dashboard as show_dashboard_linux  # Εισαγωγή από linux_logs.py
from mac_logs4 import process_mac_log as process_mac, show_dashboard as show_dashboard_mac  # Εισαγωγή από mac_logs.py
from suricata_logs4 import process_suricata_log as process_suricata, show_dashboard as show_dashboard_suricata  # Εισαγωγή από suricata_logs.py
from log_utils import PARSER_DEFAULTS

DASHBOARD_MAP = {
    "Windows": show_dashboard_windows,
    "Linux": show_dashboard_linux,
    "Mac": show_dashboard_mac,
    "Suricata": show_dashboard_suricata
}

st.set_page_config(page_title="Log Parser", layout="wide")
st.title("📄 Log Parser Dashboard")

# Sidebar with settings
with st.sidebar:
    st.header("⚙️ Ρυθμίσεις Parser")
    log_type = st.selectbox("🖥️ Τύπος Log", options=["Windows", "Linux", "Mac", "Suricata"])
    parser_choice = st.selectbox("🧩 Διάλεξε Log Parser", options=["Drain", "Spell", "LogCluster", "IPLoM", "MoLFI"]
)

    parser_params = {}
    # Conditional rendering for input fields
    
    default_params = PARSER_DEFAULTS.get(parser_choice, {}).get(log_type, {})
    
    for param_key, param_val in default_params.items():
        parser_params[param_key] = st.text_input(param_key, value=param_val)
        
    st.markdown("---")
    run_parse = st.button("🚀 Parse")

# Upload area
uploaded_file = st.file_uploader("Ανέβασε το αρχείο log σου", type=["log", "txt"])

if uploaded_file is not None:
    st.success(f"✅ Το αρχείο ανέβηκε: `{uploaded_file.name}`")

# If parse button is pressed
if "df_structured" not in st.session_state:
    st.session_state.df_structured = None
if "df_templates" not in st.session_state:
    st.session_state.df_templates = None

if uploaded_file is not None and run_parse:
    # Κλήση της συνάρτησης για την ανάλυση του log
    common_args = {"uploaded_file": uploaded_file, "parser_choice": parser_choice, **parser_params}
    
    if log_type == "Windows":
        df_structured, df_templates = process_windows(**common_args)
    elif log_type == "Linux":
        df_structured, df_templates = process_linux(**common_args)
    elif log_type == "Mac":
        df_structured, df_templates = process_mac(**common_args)
    elif log_type == "Suricata":
        df_structured, df_templates = process_suricata(**common_args)
    
    # Αποθήκευση αποτελεσμάτων στο session state
    st.session_state.df_structured = df_structured
    st.session_state.df_templates = df_templates
        
 
if st.session_state.df_structured is not None and not st.session_state.df_structured.empty:
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "📋 Structured Logs", "🔧 Log Templates"])
    
    with tab1:
        st.subheader("📊 Dashboard")
        dashboard_fn = DASHBOARD_MAP.get(log_type)
        if dashboard_fn:
            dashboard_fn(df_structured)
        else:
            st.warning("Δεν υπάρχει dashboard για αυτόν τον τύπο log.")
    
    with tab2:
        st.subheader("📋 Structured Log Data")
        st.dataframe(st.session_state.df_structured)
    
    with tab3:
        st.subheader("🔧 Log Templates")
        st.dataframe(st.session_state.df_templates, use_container_width=True)