from .controller import WorkstationController
from .integration import install_into_registry_module, merged_page_classes
from .workstations import PHASE4_PAGE_CLASSES

__all__ = [
    "PHASE4_PAGE_CLASSES",
    "WorkstationController",
    "install_into_registry_module",
    "merged_page_classes",
]
