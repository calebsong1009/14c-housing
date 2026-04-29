from typing import Literal, Union
from pydantic import BaseModel, Field

# ============================================================
# DOCUMENT SPECIFICATION DSL
# ============================================================
# A document_spec is a recursive expression that describes what
# documents satisfy a requirement. Three node types:
#   - "document": a leaf — a single document type
#   - "all_of":   every child must be satisfied (AND)
#   - "one_of":   at least one child must be satisfied (OR)
# Nesting allows arbitrary combinations.

class DocumentLeaf(BaseModel):
    type: Literal["document"]
    document_type: str  # references DocumentTypeCatalog (e.g., "paystub")
    notes: str | None = None  # human-readable detail, e.g. "5 consecutive"

class AllOf(BaseModel):
    type: Literal["all_of"]
    children: list["DocumentSpec"]

class OneOf(BaseModel):
    type: Literal["one_of"]
    children: list["DocumentSpec"]

DocumentSpec = Union[DocumentLeaf, AllOf, OneOf]
AllOf.model_rebuild()
OneOf.model_rebuild()


# ============================================================
# ACTIVATION CONDITION DSL (for triggers)
# ============================================================
# Small closed vocabulary of predicates over household data.
# Combinators: any, all, not. Leaves: comparison predicates.

class Predicate(BaseModel):
    type: Literal["predicate"]
    field: str           # dotted path into household data, e.g. "applicant.income_sources"
    operator: Literal["equals", "not_equals", "contains",
                      "greater_than", "less_than", "in", "exists"]
    value: object | None = None

class Any_(BaseModel):
    type: Literal["any"]
    children: list["Condition"]

class All_(BaseModel):
    type: Literal["all"]
    children: list["Condition"]

class Not_(BaseModel):
    type: Literal["not"]
    child: "Condition"

Condition = Union[Predicate, Any_, All_, Not_]
Any_.model_rebuild()
All_.model_rebuild()
Not_.model_rebuild()


# ============================================================
# SOURCE REFERENCE (audit trail)
# ============================================================

class SourceReference(BaseModel):
    document: str                    # "Maple Square FCFS Application 2026"
    page: int | None = None
    section: str | None = None       # "Required Documents item 5"
    quote: str | None = None         # short verbatim excerpt for auditing


# ============================================================
# TRIGGER CATALOG
# ============================================================

class Trigger(BaseModel):
    trigger_id: str
    description: str
    activation: Condition
    # When the trigger fires, which requirements get instantiated.
    # Many-to-many: one trigger → multiple requirements.
    emits_requirements: list[str]    # list of requirement_ids
    # Per-member instantiation: if set, the trigger fires once per
    # household member matching the inner condition (flattened).
    # If null, fires once per household.
    per_member_scope: Condition | None = None
    source_reference: SourceReference


# ============================================================
# DOCUMENT SET REQUIREMENT CATALOG
# ============================================================

class DocumentSetRequirement(BaseModel):
    requirement_id: str
    description: str
    document_spec: DocumentSpec
    source_reference: SourceReference


# ============================================================
# RUNTIME: REQUIREMENT INSTANCE
# ============================================================
# Produced by the engine after evaluating triggers against household data.
# This is what the document-checker actually evaluates.

class RequirementInstance(BaseModel):
    instance_id: str                 # e.g. "wage_income_proof::member_002"
    requirement_id: str              # references catalog
    triggered_by: list[str]          # trigger_ids that emitted this (audit)
    applies_to_member: str | None = None  # member_id, or None for household-level
    document_spec: DocumentSpec      # copied from catalog (pre-resolved)