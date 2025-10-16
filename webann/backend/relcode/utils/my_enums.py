CAUSAL_MECHANISM_QUALIFIER_ENUM = [
    "binding", "inhibition", "antibody_inhibition", "antagonism", "molecular_channel_blockage", "inverse_agonism", "negative_allosteric_modulation", 
    "agonism", "molecular_channel_opening", "positive_allosteric_modulation", "potentiation", "activation", "inducer", "transcriptional_regulation", 
    "signaling_mediated_control", "stabilization", "stimulation", "releasing_activity"]

DIRECTION_QUALIFIER_ENUM = ["increased", "decreased", "upregulated", "downregulated"]

GENE_OR_GENE_PRODUCT_OR_CHEMICAL_ENTITY_ASPECT_ENUM = [
    "abundance", "activity", "expression", "synthesis", "degradation","cleavage", "hydrolysis", "metabolic_processing", "mutation_rate",
    "stability", "folding", "localization", "transport", "absorption","aggregation", "interaction", "release", "secretion", "uptake",
    "splicing", "molecular_interaction", "guanyl_nucleotide_exchange","adenyl_nucleotide_exchange", "molecular_modification", "acetylation",
    "acylation", "alkylation", "amination", "carbamoylation", "ethylation","glutathionylation", "glycation", "glycosylation", "glucuronidation",
    "n_linked_glycosylation", "o_linked_glycosylation", "hydroxylation","lipidation", "farnesylation", "geranoylation", "myristoylation",
    "palmitoylation", "prenylation", "methylation", "nitrosation","nucleotidylation", "phosphorylation", "ribosylation", "ADP-ribosylation",
    "sulfation", "sumoylation", "ubiquitination", "oxidation", "reduction","carboxylation"
]

CHEMICAL_ENTITY_DERIVATIVE_ENUM = ["metabolite"]

CHEMICAL_OR_GENE_OR_GENE_PRODUCT_FORM_OR_VARIANT_ENUM = [
    "genetic_variant_form", "modified_form", "loss_of_function_variant_form","non_loss_of_function_variant_form", "gain_of_function_variant_form",
    "dominant_negative_variant_form", "polymorphic_form", "snp_form","analog_form"
]

GENE_OR_GENE_PRODUCT_OR_CHEMICAL_PART_QUALIFIER_ENUM = ["3_prime_utr", "5_prime_utr", "polya_tail", "promoter", "enhancer", "exon", "intron"]

LOGICAL_INTERPRETATION_ENUM = ["some_some", "all_some", "some_all"]

REACTION_DIRECTION_ENUM = ["left_to_right", "right_to_left", "bidirectional", "neutral"]

REACTION_SIDE_ENUM = ["left", "right"]

STRAND_ENUM = ["positive", "negative", "unstranded", "unknown"]

SEQUENCE_ENUM = ["nucleic_acid", "amino_acid"]

DRUG_DELIVERY_ENUM = ["inhalation", "oral", "skin_absorption", "intravenous_injection"]

RESPONSE_TARGET_ENUM = ["cohort", "cell line", "individual", "sample"]

RESPONSE_ENUM = ["therapeutic_response", "negative"]

