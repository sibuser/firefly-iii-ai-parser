import os
import structlog
import structlog_pretty
import structlog.processors
import structlog.dev
from dotenv import load_dotenv

load_dotenv()

def configure_logging():
    structlog.configure(
        processors=[
            # Pretty-print JSON stored in 'payload_pretty'
            structlog_pretty.JSONPrettifier(['payload_pretty']),
            # Optional syntax highlighting for JSON strings
            structlog_pretty.SyntaxHighlighter({'payload_pretty': 'json'}),
            # Print multi-line JSON nicely
            structlog_pretty.MultilinePrinter(['payload_pretty']),
            # Standard structlog processors
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(os.getenv("LOG_LEVEL", os.getenv("LOG_LEVEL", "INFO"))),
        cache_logger_on_first_use=True,
    )

def get_logger(name=None):
    configure_logging()
    return structlog.get_logger(name)