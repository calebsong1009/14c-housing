from typing import Literal, Union
from pydantic import BaseModel, Field, model_validator

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
    # Advisory only in MVP: the engine checks presence, not "5 consecutive",
    # recency, or coverage windows. See catalog_templates/README.md.
    notes: str | None = None

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

PredicateValue = int | float | str | bool | list[int | float | str | bool] | None


class Predicate(BaseModel):
    type: Literal["predicate"]
    field: str           # dotted path into household data, e.g. "applicant.income_sources"
    operator: Literal["equals", "not_equals", "contains",
                      "greater_than", "less_than", "in", "exists"]
    value: PredicateValue = None

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

# Applicant and co-applicant live outside `household.members[]` in the
# input schema, so they are first-class scopes — not addressable via
# per_member_scope. See catalog_templates/README.md.
InstanceScope = Literal["household", "applicant", "co_applicant", "per_member"]


class Trigger(BaseModel):
    trigger_id: str
    description: str
    activation: Condition
    # When the trigger fires, which requirements get instantiated.
    # Many-to-many: one trigger → multiple requirements.
    emits_requirements: list[str]    # list of requirement_ids
    instance_scope: InstanceScope = "household"
    # Only consulted when instance_scope == "per_member". Predicate.field
    # inside per_member_scope is interpreted relative to the member object
    # (e.g. "age", "relationship"), not the household root.
    per_member_scope: Condition | None = None
    source_reference: SourceReference

    @model_validator(mode="after")
    def _scope_matches_per_member(self) -> "Trigger":
        if self.instance_scope == "per_member" and self.per_member_scope is None:
            raise ValueError("per_member_scope is required when instance_scope == 'per_member'")
        if self.instance_scope != "per_member" and self.per_member_scope is not None:
            raise ValueError("per_member_scope must be None when instance_scope != 'per_member'")
        return self


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
    applies_to_role: Literal["household", "applicant", "co_applicant", "member"]
    # Engine-minted stable hash of the member tuple. Required iff
    # applies_to_role == "member"; must be None otherwise.
    applies_to_member: str | None = None
    document_spec: DocumentSpec      # copied from catalog (pre-resolved)

    @model_validator(mode="after")
    def _member_hash_matches_role(self) -> "RequirementInstance":
        if self.applies_to_role == "member" and self.applies_to_member is None:
            raise ValueError("applies_to_member is required when applies_to_role == 'member'")
        if self.applies_to_role != "member" and self.applies_to_member is not None:
            raise ValueError("applies_to_member must be None when applies_to_role != 'member'")
        return self