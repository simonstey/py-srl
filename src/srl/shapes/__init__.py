"""Opt-in SHACL 1.2 Core subset for rule-to-shape targeting (not part of the SRL spec)."""

from .model import (
    SH,
    Constraint,
    NodeShape,
    PropertyShape,
    UnsupportedShapeFeatureError,
    load_shape,
)
from .validate import conforms

__all__ = [
    "NodeShape",
    "PropertyShape",
    "Constraint",
    "SH",
    "load_shape",
    "UnsupportedShapeFeatureError",
    "conforms",
]
