from templates import DocumentLeaf, AllOf, OneOf, Predicate, Any_, All_, Not_, SourceReference, Trigger, DocumentSetRequirement, RequirementInstance
import json

with open(handcoded_trigger_catalog.json) as handcoded:
    # list of dicts defining the catalog
    json_defining_catalog = handcoded



