from .audit import run as compatibility_audit
from .bootstrap import FeatureFlags, IntegratedUI, bootstrap
from .diagnostics import write_report
from .performance import page_refresh_report
from .rollback import disable
from .save_compat import extension_payload, restore_extensions, strip_extensions

__all__ = [
    "FeatureFlags",
    "IntegratedUI",
    "bootstrap",
    "compatibility_audit",
    "disable",
    "extension_payload",
    "page_refresh_report",
    "restore_extensions",
    "strip_extensions",
    "write_report",
]
