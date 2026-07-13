"""Opt-in SHACL 1.2 Core subset for rule-to-shape targeting (not part of the SRL spec)."""
from .model import NodeShape, PropertyShape, Constraint, SH, load_shape, UnsupportedShapeFeatureError

__all__ = ["NodeShape", "PropertyShape", "Constraint", "SH", "load_shape", "UnsupportedShapeFeatureError"]
