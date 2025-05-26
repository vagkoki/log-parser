import os
import tempfile
import pandas as pd
import streamlit as st
from logparser.Drain import LogParser as DrainParser
from logparser.Spell import LogParser as SpellParser
from logparser.LogCluster import LogParser as LogClusterParser
from logparser.IPLoM import LogParser as IPLoMParser
from logparser.MoLFI import LogParser as MoLFIParser


PARSER_FACTORY = {
    "Drain": lambda args: DrainParser(
        args["log_format"],
        indir=args["indir"],
        outdir=args["outdir"],
        depth=int(args["depth"]),
        st=float(args["threshold"]),
        rex=args.get("rex", [])
    ),
    "Spell": lambda args: SpellParser(
        indir=args["indir"],
        outdir=args["outdir"],
        log_format=args["log_format"],
        tau=float(args["threshold"]),
        rex=args.get("rex", [])
    ),
    "LogCluster": lambda args: LogClusterParser(
        args["indir"],
        args["log_format"],
        args["outdir"],
        rsupport=int(args["rsupport"])
    ),
    "IPLoM": lambda args: IPLoMParser(
        log_format=args["log_format"],
        indir=args["indir"],
        outdir=args["outdir"],
        CT=float(args["CT"]),
        lowerBound=float(args["lowerBound"]),
        rex=args.get("rex", [])
    ),
    "MoLFI": lambda args: MoLFIParser(
        indir=args["indir"],
        outdir=args["outdir"],
        log_format=args["log_format"],
        rex=args.get("rex", [])
    )
}

PARSER_DEFAULTS = {
    "Drain": {
        "Windows": {"depth": "5", "threshold": "0.7"},
        "Linux": {"depth": "4", "threshold": "0.39"},
        "Mac": {"depth": "6", "threshold": "0.7"},
        "Suricata": {"depth": "4", "threshold": "0.7"}
    },
    "Spell": {
        "Windows": {"threshold": "0.7"},
        "Linux": {"threshold": "0.55"},
        "Mac": {"threshold": "0.6"},
        "Suricata": {"threshold": "0.7"}
    },
    "LogCluster": {
        "Windows": {"rsupport": "1"},
        "Linux": {"rsupport": "40"},
        "Mac": {"rsupport": "1"},
        "Suricata": {"rsupport": "1"}
    },
    "IPLoM": {
        "Windows": {"CT": "0.3", "lowerBound": "0.25"},
        "Linux": {"CT": "0.3", "lowerBound": "0.3"},
        "Mac": {"CT": "0.3", "lowerBound": "0.25"},
        "Suricata": {"CT": "0.3", "lowerBound": "0.25"}
    },
    "MoLFI": {
        "Windows": {},
        "Linux": {},
        "Mac": {},
        "Suricata": {}
    }
}

REGEX_PATTERNS = {
    "Windows": [
        r'0x[0-9a-fA-F]+',  # Hex addresses and pointers
        r'@0x[0-9a-fA-F]+',  # Hex pointers με @
        r'v\d+\.\d+\.\d+\.\d+',  # Version numbers
        r'[A-Za-z]:\\[^ ]+\.(dll|sqm|exe)',  # File paths
        r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}',  # GUIDs/Session IDs
        r'\d+_\d+',  # IDs με underscore (π.χ. 1234_56)
        r'\[HRESULT = 0x[0-9a-fA-F]+ - [A-Z_]+\]',  # HRESULT codes
        r'0000000[0-9a-fA-F]',  # CSI sequence numbers
        r'stack @0x[0-9a-fA-F]+( @0x[0-9a-fA-F]+)+',  # Stack traces
        r'\d+'  # Απλοί ακέραιοι αριθμοί (π.χ. 4991456)
    ],
    "Linux": [
        r"\([^\)]*\)",  # Παρενθέσεις ολόκληρες (π.χ. (something.domain.com))
        r"(?:/[a-zA-Z0-9._-]+)+/?",  # Paths (π.χ. /var/log/syslog)
        r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",  # Email addresses
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\b",  # Full date like "Mon Jul 25"
        r"\b\d{2}:\d{2}:\d{2}\b",  # Time (hh:mm:ss)
        r"(?<![\w.-])\d{1,3}(?:\.\d{1,3}){3}(?![\w.-])",  # IP address (μόνο όταν είναι standalone)
        r"\bport\s+\d+\b",  # Ports (π.χ. port 1234)
        r"\b0x[0-9a-fA-F]+\b",  # Hexadecimal IDs
        r"\b\d{5,}\b",  # Numeric IDs (μεγάλοι αριθμοί π.χ. PID 12345)
        r"\b\d+\b"  # Μικροί ακέραιοι (προαιρετικά μικροί αριθμοί)
    ],
    "Mac": [
        r"\([^\)]*\)",  # Παρενθέσεις ολόκληρες (π.χ. (something.domain.com))
        r"(?:/[a-zA-Z0-9._-]+)+/?",  # Paths (π.χ. /var/log/syslog)
        r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",  # Email addresses
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\b",  # Full date like "Mon Jul 25"
        r"\b\d{2}:\d{2}:\d{2}\b",  # Time (hh:mm:ss)
        r"(?<![\w.-])\d{1,3}(?:\.\d{1,3}){3}(?![\w.-])",  # IP address (μόνο όταν είναι standalone)
        r"\bport\s+\d+\b",  # Ports (π.χ. port 1234)
        r"\b0x[0-9a-fA-F]+\b",  # Hexadecimal IDs
        r"\b\d{5,}\b",  # Numeric IDs (μεγάλοι αριθμοί π.χ. PID 12345)
        r"\b\d+\b"  # Μικροί ακέραιοι (προαιρετικά μικροί αριθμοί)
    ],
    "Suricata": [
        r'\[([A-Z]+ \d+)\]',  # θα πιάσει [TCP 22], [UDP 53] κλπ
        r"\([^\)]*\)",  # Παρενθέσεις ολόκληρες (π.χ. (something.domain.com))
        r"(?:/[a-zA-Z0-9._-]+)+/?",  # Paths (π.χ. /var/log/syslog)
        r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",  # Email addresses
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\b",  # Full date like "Mon Jul 25"
        r"\b\d{2}:\d{2}:\d{2}\b",  # Time (hh:mm:ss)
        r"(?<![\w.-])\d{1,3}(?:\.\d{1,3}){3}(?![\w.-])",  # IP address (μόνο όταν είναι standalone)
        r"\bport\s+\d+\b",  # Ports (π.χ. port 1234)
        r"\b0x[0-9a-fA-F]+\b",  # Hexadecimal IDs
        r"\b\d{5,}\b",  # Numeric IDs (μεγάλοι αριθμοί π.χ. PID 12345)
        r"\b\d+\b"  # Μικροί ακέραιοι (προαιρετικά μικροί αριθμοί)
    ]
}

PARSER_PARAM_TYPES = {
    "Drain": {"depth": int, "threshold": float},
    "Spell": {"threshold": float},
    "LogCluster": {"rsupport": int},
    "IPLoM": {"CT": float, "lowerBound": float},
    "MoLFI": {}
}

def run_parser(uploaded_file, parser_choice, log_format, regex, **kwargs):
    try:
        with tempfile.TemporaryDirectory() as tmp_input_dir, tempfile.TemporaryDirectory() as tmp_output_dir:
            # Αποθήκευση αρχείου
            temp_log_path = os.path.join(tmp_input_dir, uploaded_file.name)
            with open(temp_log_path, "wb") as f:
                f.write(uploaded_file.read())

            # Δημιουργία args
            parser_args = {
                "log_format": log_format,
                "indir": tmp_input_dir,
                "outdir": tmp_output_dir,
                "rex": regex
            }
            parser_args.update(kwargs)

            # Έλεγχος παραμέτρων
            param_types = PARSER_PARAM_TYPES.get(parser_choice, {})
            for key, expected_type in param_types.items():
                try:
                    if key in kwargs:
                        kwargs[key] = expected_type(kwargs[key])
                except ValueError:
                    st.error(f"❗ Η παράμετρος '{key}' πρέπει να είναι τύπου {expected_type.__name__}.")
                    st.stop()
                    
            # Απόκτηση parser
            parser_factory = PARSER_FACTORY.get(parser_choice)
            if not parser_factory:
                st.warning("Άγνωστος parser.")
                return pd.DataFrame(), pd.DataFrame()

            parser = parser_factory(parser_args)
            parser.parse(uploaded_file.name)

            # Ανάγνωση αποτελεσμάτων
            structured_path = os.path.join(tmp_output_dir, uploaded_file.name + "_structured.csv")
            templates_path = os.path.join(tmp_output_dir, uploaded_file.name + "_templates.csv")

            df_structured = pd.read_csv(structured_path) if os.path.exists(structured_path) else pd.DataFrame()
            df_templates = pd.read_csv(templates_path) if os.path.exists(templates_path) else pd.DataFrame()

            return df_structured, df_templates
    except Exception as e:
        st.error(f"❗ Σφάλμα κατά την εκτέλεση του parser: {e}")
        return pd.DataFrame(), pd.DataFrame()
