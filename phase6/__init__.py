from .controller import DeepDrillController
from .detail_view import DeepDetailView
from .inspectors import INSPECTORS, inspect
from .integration import attach
from .routes import EntityRef, infer

__all__ = [
    "DeepDetailView",
    "DeepDrillController",
    "EntityRef",
    "INSPECTORS",
    "attach",
    "infer",
    "inspect",
]
