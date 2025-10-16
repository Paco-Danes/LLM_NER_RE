from .utils.relation_utils import RelationshipSpec, FixedChoiceField, FreeTextField, DynamicEntityField, CandidateSpec, build_relationship_models
from .utils.my_enums import *

# your enums live here

# ----------------------------
# Example specs (yours)
# ----------------------------

CHEMICAL_AFFECTS_GENE = RelationshipSpec(
    name="ChemicalAffectsGene",
    description= "Describes an effect that a chemical has on a gene or gene product (e.g. an impact of on its abundance, activity,localization, processing, expression, etc.)",
    subject_classes=["SmallMolecule"],
    object_classes=["Gene", "Protein", "RnaTranscript"],
    predicate_choices=["affects", "causes"],
    fixed_fields=[
        FixedChoiceField("subject_form_or_variant", CHEMICAL_OR_GENE_OR_GENE_PRODUCT_FORM_OR_VARIANT_ENUM, optional=True),
        FixedChoiceField("subject_part", GENE_OR_GENE_PRODUCT_OR_CHEMICAL_PART_QUALIFIER_ENUM, optional=True),
        FixedChoiceField("subject_derivative", CHEMICAL_ENTITY_DERIVATIVE_ENUM, optional=True),
        FixedChoiceField("subject_aspect", GENE_OR_GENE_PRODUCT_OR_CHEMICAL_ENTITY_ASPECT_ENUM, optional=True),
        FixedChoiceField("subject_direction", DIRECTION_QUALIFIER_ENUM, optional=True),
        FixedChoiceField("object_form_or_variant", CHEMICAL_OR_GENE_OR_GENE_PRODUCT_FORM_OR_VARIANT_ENUM, optional=True),
        FixedChoiceField("object_part", GENE_OR_GENE_PRODUCT_OR_CHEMICAL_PART_QUALIFIER_ENUM, optional=True),
        FixedChoiceField("object_aspect", GENE_OR_GENE_PRODUCT_OR_CHEMICAL_ENTITY_ASPECT_ENUM, optional=True),
        FixedChoiceField("object_direction", DIRECTION_QUALIFIER_ENUM, optional=True),
        FixedChoiceField("causal_mechanism", CAUSAL_MECHANISM_QUALIFIER_ENUM, optional=True),
    ],
    dynamic_fields=[
        DynamicEntityField("subject_context", classes=["CellType", "CellLine", "CellularComponent", "TissueOrOrgan"], optional=True),
        DynamicEntityField("object_context", classes=["CellType", "CellLine", "CellularComponent", "TissueOrOrgan"], optional=True),
        DynamicEntityField("anatomical_context", classes=["CellType", "CellLine", "CellularComponent", "TissueOrOrgan"], optional=True),
        DynamicEntityField("species_context", classes=["OrganismTaxon"], optional=True),
    ],
)

CHEMICAL_TO_PATHWAY = RelationshipSpec(
    name="ChemicalToPathway",
    description="An interaction between a chemical entity and a biological process or pathway.",
    subject_classes=["SmallMolecule"],
    object_classes=["Pathway"],
    predicate_choices=["participates_in", "actively_involved_in", "consumed_by", "is_output_of", "enables", "catalyzes"]
)

# DiseaseOrPhenotypicFeatureToGeneticInheritance
DISEASE_OR_PHENOTYPIC_FEATURE_TO_GENETIC_INHERITANCE = RelationshipSpec(
    name="DiseaseOrPhenotypicFeatureToGeneticInheritance",
    description="A relationship between either a disease or a phenotypic feature and its mode of (genetic) inheritance.",
    subject_classes=["Disease", "PhenotypicFeature"],
    object_classes=["GeneticInheritance"],
    predicate_choices=["has_mode_of_inheritance"],
)

DISEASE_TO_PHENOTYPIC_FEATURE = RelationshipSpec(
    name="DiseaseToPhenotypicFeature",
    description="A relationship between a disease and a phenotypic feature in which the phenotypic feature is associated with the disease in some way.",
    subject_classes=["Disease"],
    object_classes=["PhenotypicFeature"],
    predicate_choices=["has_phenotype"],
    fixed_fields=[
        FreeTextField("subject_aspect", optional=True), # e.g stability, abundance, expression, exposure
        FixedChoiceField("subject_direction", DIRECTION_QUALIFIER_ENUM, optional=True),
        FreeTextField("object_aspect", optional=True), # e.g stability, abundance, expression, exposure
        FixedChoiceField("object_direction", DIRECTION_QUALIFIER_ENUM, optional=True),
        FreeTextField("frequency", optional=True), # e.g. "80% of patients", "very common", "rarely"
    ],
    dynamic_fields=[
        DynamicEntityField("disease_context", classes=["Disease"], optional=True)
    ]
)

GENE_TO_GENE_COEXPRESSION = RelationshipSpec( # CHECK !!!!! 
    name="GeneToGeneCoexpression",
    description="Indicates that two genes or gene products are co-expressed, generally under the same conditions.",
    subject_classes=["Gene", "Protein", "RnaTranscript"],
    object_classes=["Gene", "Protein", "RnaTranscript"],
    predicate_choices=['coexpressed_with'],
    fixed_fields=[
        FreeTextField("quantifier", optional=True), # e.g. Optional quantitative value indicating degree of expression.
    ],
    dynamic_fields=[
        DynamicEntityField("expression_site", classes=["CellType", "CellularComponent", "TissueOrOrgan"], optional=True),
        DynamicEntityField("stage_qualifier", classes=["MouseDevelopmentalTimepoint", "HumanDevelopmentalTimepoint"], optional=True),
    ]
)

DEFAULT_SPECS: list[RelationshipSpec] = [
    CHEMICAL_AFFECTS_GENE,
    CHEMICAL_TO_PATHWAY,
    DISEASE_OR_PHENOTYPIC_FEATURE_TO_GENETIC_INHERITANCE,
    DISEASE_TO_PHENOTYPIC_FEATURE,
    GENE_TO_GENE_COEXPRESSION,
]
