from pydantic import BaseModel, Field
from typing import Literal, Optional, Union

class NamedEntity(BaseModel):
    #id: str = Field(..., description="Locally unique id for this entity within the text, used for referencing in relationships.")
    label: str = Field(..., description="")
    def __init_subclass__(cls):
        super().__init_subclass__() # call BaseModel's __init_subclass__
        cls.model_fields["label"].description = f"Surface form (name) of the {cls.__name__} as it appears in the text."

# function to retrieve entity list that includes all classes. If multiple inheritance is used, recursively get all subclasses
def Entity_Collector(root = NamedEntity, recursion=False):
    if recursion:
        subclasses = set(root.__subclasses__())
        for sub in root.__subclasses__():
            subclasses.update(Entity_Collector(sub, recursion=True))
        return list(subclasses)

    return [cls for cls in NamedEntity.__subclasses__()]

def export_entities_json(filepath: str = "classes.json") -> None:
    """
    Export a simple JSON schema of direct subclasses of NamedEntity.
    - Skips NamedEntity itself and the inherited 'label' field.
    - Uses class __doc__ verbatim as 'description'.
    - Emits 'enum' for Literal[...] (excluding None), and 'nullable' if None is allowed.
    - Maps primitive types (str, int, float, bool) to 'type'.
    """
    import json
    from typing import get_origin, get_args, Union

    out = {}

    for cls in NamedEntity.__subclasses__():
        desc = cls.__doc__ or ""
        # remove any multiple whitespace but keep newlines
        desc = "\n".join(" ".join(line.split()) for line in desc.splitlines()).strip()
        attrs = {}

        for fname, field in getattr(cls, "model_fields", {}).items():
            if fname == "label":
                continue

            ann = field.annotation
            nullable = False
            enum_vals = None
            type_name = None

            # Handle Optional/Union[... , None]
            origin = get_origin(ann)
            args = list(get_args(ann)) if origin is not None else []

            # If Literal directly
            if str(origin).endswith("Literal"):
                enum_vals = [v for v in args if v is not None]
                nullable = any(v is None for v in args)
            else:
                # Unwrap Optional/Union with None (PEP 604 or typing.Union)
                if origin in (Union, getattr(__import__("types"), "UnionType", Union)):
                    non_none = [a for a in args if a is not type(None)]
                    nullable = len(non_none) < len(args)
                    ann = non_none[0] if len(non_none) == 1 else ann
                    origin = get_origin(ann)
                    args = list(get_args(ann)) if origin is not None else []

                # Literal after unwrapping?
                if str(origin).endswith("Literal"):
                    enum_vals = [v for v in args if v is not None]
                    nullable = nullable or any(v is None for v in args)
                else:
                    # Primitive mapping
                    if ann in (str,):
                        type_name = "string"
                    elif ann in (int,):
                        type_name = "integer"
                    elif ann in (float,):
                        type_name = "number"
                    elif ann in (bool,):
                        type_name = "boolean"

            # Build field entry
            if enum_vals is not None:
                attrs[fname] = {"enum": enum_vals, "nullable": bool(nullable)}
            else:
                entry = {"nullable": bool(nullable)}
                if type_name is not None:
                    entry["type"] = type_name # type: ignore
                attrs[fname] = entry

        out[cls.__name__] = {"description": desc, "attributes": attrs}

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=4, ensure_ascii=False)

class Protein(NamedEntity):
    """
    A polypeptide chain (or set of chains) that folds into a functional 3D structure, often acting as a receptor, structural molecule, transporter, etc.
    Examples: "EGFR", "SCN1A", "SLC2A1", "TP53", "ELAVL1", "RPLP0", "SNRNP70", "ACTB", "insulin", "IGHG1", "F2", "EGF", "GRB2".
    """

class ProteinDomain(NamedEntity):
    """
    A stable, independently folding structural or functional unit within a protein, often conserved across proteins.
    Examples: "SH3 domain", "SH2 domain", "GAF domain", "Kringle domain", "WD40 repeat", "Zinc finger domain".
    """

class Gene(NamedEntity):
    """
    A stretch of DNA (or locus) that encodes (or is associated with) a functional product, such as an RNA or protein.
    Examples: "BRCA1", "TP53", "EGFR gene", "MYC", "APOE".
    """

class GeneFamily(NamedEntity):
    """
    A set of genes descended by duplication from a common ancestral gene, often with related functions.
    Examples: "HOX gene family", "Cytochrome P450 family", "G-protein coupled receptor family", "WntFamily",  "keratin gene family".
    """

class Disease(NamedEntity):
    """
    A medical condition or disorder affecting an organism, typically with recognized signs/symptoms or pathology.
    Examples: "Alzheimer's disease", "Type 2 diabetes", "Breast cancer", "Cystic fibrosis", "Malaria".
    """

class Drug(NamedEntity):
    """
    A medicine, chemical or biologic agent used to treat, cure, prevent, mitigate or diagnose disease.
    Examples: "Imatinib", "Aspirin", "Trastuzumab", "Metformin", "Penicillin", "Nivolumab", "Atorvastatin".
    """

class CellType(NamedEntity):
    """
    A basic living unit of an organism, often a specialized cell type in multicellular organisms.
    Examples: "hematopoietic stem cell", "radial glial cell", "dopaminergic neuron", "astrocyte", "CD4+ T cell", "keratinocyte", "vascular endothelial cell", "fibroblast", "cardiomyocyte", "oocyte", "erythrocyte".
    """

class CellLine(NamedEntity):
    """
    A cultured population of cells maintained as a resource for experimental use, often immortalized or derived from a specific donor, tissue, or disease context. 
    Cell lines are distinct from natural cell types, as they are experimental materials with stable identifiers and provenance.
    Examples: "HeLa cell", "HEK293 cell", "MCF-7 cell", "Jurkat cell", "NIH-3T3 cell".
    """

class Chromosome(NamedEntity):
    """
    A long DNA molecule (plus associated proteins) that bears genes in a linear (or circular) arrangement.
    Examples: "chromosome 17", "X chromosome", "chr1p36.3", "chromosome 21", "Y chromosome".
    """

class SequenceVariant(NamedEntity):
    """
    A variant (mutation, polymorphism, insertion, deletion, etc.) in a DNA, RNA, or protein sequence relative to a reference.
    Synonyms: allele
    Examples: "BRCA1 c.68_69delAG", "EGFR L858R", "rs334 (HbS)" (the sickle variant), "KRAS G12D", "ΔF508 CFTR", "BRAF V600E"
    """

class MacromolecularComplex(NamedEntity):
    """
    A stable assembly of two or more macromolecules (proteins, nucleic acids, carbohydrates, lipids etc) in which at least one component is a protein and the constituent parts function together.
    Examples: "proteasome", "ATP synthase", "spliceosome", "RNA polymerase II holoenzyme", "photosystem II", "ribosome.
    """

class Pathway(NamedEntity):
    """
    A series of biochemical or signaling steps in a cell, through which molecules interact and transform, resulting in certain cellular outcomes.
    Examples: "Glycolysis pathway", "MAPK signaling pathway", "Wnt signaling", "TCA cycle", "PI3K-Akt signaling pathway", "Gluconeogenesis".
    """

class MolecularActivity(NamedEntity):
    """
    An execution of a molecular function carried out by a gene product or macromolecular complex.
    Examples: "kinase activity", "DNA binding activity", "phosphatase activity", "helicase activity", "oxidoreductase activity", "ligase activity".
    """

class PhenotypicFeature(NamedEntity):
    """
    An observable trait, characteristic, or phenotype at organism, tissue, or cellular level. It is constructed broadly as any kind of quality of an organism part, a collection of these qualities, or a change in quality or qualities (e.g. abnormally increased temperature).
    Synonyms: sign, symptom, phenotype, trait, endophenotype
    Examples: "hypertension", "hypercholesterolemia", "dysplasia", "reduced growth rate", "anemia", "microcephaly", "insulin resistance".
    """

class GeneticInheritance(NamedEntity):
    """
    The pattern or 'mode' in which a particular genetic trait or disorder is passed from one generation to the next.
    Examples: "autosomal dominant", "autosomal recessive".
    """
    type: Literal["autosomal dominant", "autosomal recessive", "X-linked dominant", "X-linked recessive", "Y-linked", "mitochondrial", "polygenic", "multifactorial"] | None = Field(None, description="Type of genetic inheritance, None if generic or other.")

class MolecularEntity(NamedEntity):
    """
    A chemical entity composed of individual or covalently bonded atoms. Also includes nucleic acid entities (gene databases of nucleotide-based sequence) and small-molecules present in databases of SMILES, InChI, IUPAC, or other unambiguous representation of its structure. Even if it is not strictly molecular (e.g., sodium ion)
    Examples: "glucose", "ATP", "cAMP", "ethanol", "hexaclorobenzene", "chloride ion", "caffeine".
    """

class MolecularMixture(NamedEntity):
    """
    A chemical mixture composed of two or more molecular entities with known concentration and stoichiometry (excluding drugs). 
    Examples: "blood plasma", "cell culture media", "seawater", "urine", "saliva".
    """

class UnknownMoleculerMixture(NamedEntity): # biolink ComplexMolecularMixture
    """
    A chemical mixture composed of two or more molecular entities with unknown concentration and stoichiometry.
    Examples:
    """

class NucleosomeModification(NamedEntity):
    """
    A chemical modification of a histone protein within a nucleosome octomer or a substitution of a histone with a variant histone isoform.
    Examples: Histone 4 Lysine 20 methylation (H4K20me), histone variant H2AZ substituting H2A.
    """

class PosttranslationalModification(NamedEntity):
    """
    A chemical modification of a polypeptide or protein that occurs after translation.
    Examples: "methylation" or "acetylation" of histone tail amino acids, protein "ubiquitination", polypeptide "cleavage", "phosphorylation", "glycosylation", "sumoylation", "lipidation".
    """

class Food(NamedEntity):
    """
    A substance whose context implies it is consumed or eaten by a living organism as a source of nutrition.
    Examples: "apple", "bread", "milk", "rice", "chicken", "broccoli", "salmon", "yogurt", "spinach", "almonds".
    """

class FoodAdditive(NamedEntity):
    """
    A substance added to food to preserve flavor or enhance its taste, appearance, or other qualities.
    Examples: "sodium benzoate", "monosodium glutamate (MSG)", "tartrazine", "ascorbic acid (vitamin C)", "citric acid", "sucrose", "calcium propionate", "E202".
    """

class TissueOrOrgan(NamedEntity):
    """
    A multicellular structure or collection of cells forming a functional part of an organism.
    Examples: "liver", "kidney cortex", "heart tissue", "pancreatic islets", "skeletal muscle", "retina", "bone marrow".
    """

class Polypeptide(NamedEntity):
    """
    A linear chain of amino acids (protein or fragment) that may or may not fold into a functional domain.
    Examples: "insulin B chain", "synthetic peptide fragment p53(15-29)", "amyloid-β (1-42)", "angiotensin II peptide".
    """

class CellularComponent(NamedEntity):
    """
    A subcellular structure or location within a cell (organelle, compartment, etc.).
    Examples: "cytoplasm", "mitochondrion", "nucleus", "endoplasmic reticulum", "Golgi apparatus", "ribosome", "lysosome", "peroxisome", "plasma membrane".
    """

class BrainRegion(NamedEntity):
    """
    A distinct anatomical region or structure of the brain, involved in specific neural functions or processes.
    Examples: "hippocampus", "amygdala", "cerebral cortex", "hindbrain", "midbrain", "thalamus", "cerebellum".
    """

class BiologicalProcess(NamedEntity):
    """
    A coordinated series of molecular, cellular, or physiological events carried out by one or more living organisms to achieve a specific biological function or outcome.
    Examples:  "direct/indirect neurogenesis", "cell cycle", "apoptosis", "DNA repair", "signal transduction", "angiogenesis", "autophagy", "immune response".
    """

class Bacterium(NamedEntity):
    """
    A single-celled prokaryotic microorganism belonging to the domain Bacteria.
    Examples: "Escherichia coli", "Staphylococcus aureus", "Mycobacterium tuberculosis", "Helicobacter pylori", "Bacillus subtilis".
    """

class Virus(NamedEntity):
    """
    A submicroscopic infectious agent consisting of nucleic acid enclosed in a protein coat, sometimes with a lipid envelope, that replicates only inside host cells.
    Examples: "Influenza A virus", "SARS-CoV-2", "Human papillomavirus 16", "HIV-1", "Hepatitis B virus".
    """

class OrganismTaxon(NamedEntity):
    """
    A classification of a set of organisms. Can also be used to represent strains or subspecies.
    Examples: "Homo Sapiens", "Bacteria", "Arabidopsis thaliana", "Saccharomyces cerevisiae", "Caenorhabditis elegans", "Drosophila melanogaster".
    """
class Metabolite(NamedEntity):
    """
    A small molecule that is an intermediate or product of metabolism, often found in specific biochemical pathways.
    Examples: "pyruvate", "lactate", "glutamate", "cholesterol", "acetyl-CoA", "succinate", "uridine".
    """
class Intron(NamedEntity):
    """
    A non-coding segment of a gene that is transcribed into RNA but removed during RNA splicing, so it does not appear in the mature RNA transcript.
    Examples: "BRCA1 intron 2", "TP53 intron 4", "CFTR gene intron 8", "intron 44 of gene DMD".
    """

class Exon(NamedEntity):
    """
    A contiguous segment of a gene that remains in the mature RNA transcript after splicing.
    Examples: "BRCA1 gene exon 11", "TP53 exon 7", "DMD exon 45", "exon 10 of CFTR gene".
    """

class RnaTranscript(NamedEntity): # Synonim: transcript ?? maybe not
    """
    Any RNA/Transcript molecule (excludes rybozymes and viral rna).
    Examples: "c-Myc mRNA", "tRNA^Met", "yeast 25S rRNA", "miRNA-200c", "MALAT1 transcript", "U1 snRNA", "SNORD44", "circHIPK3", "piR-651", "CRISPR-Cas9 gRNA".
    """
    type: Literal["mRNA", "tRNA", "rRNA", "miRNA", "lncRNA", "snRNA", "snoRNA", "circRNA", "piRNA", "gRNA"] | None = Field(None, description="Type of RNA molecule, None if generic or other.")   

# class ViralRna(NamedEntity):
#     """
#     An RNA molecule that is part of a virus's genetic material, which can be single-stranded or double-stranded.
#     Examples: "SARS-CoV-2 RNA genome", "Hepatitis C virus RNA", "Influenza A virus segment 4", "Ebola virus RNA", "Zika virus RNA".
#     """

class CNSFunction(NamedEntity):
    """
    A specific function or process carried out by the central nervous system (CNS), which includes the brain and spinal cord.
    Examples: "Vision", "motor control", "temperature regulation", "emotional regulation", "language comprehension", "hearing", "balance", "breathing control".
    """
    type: Literal["SensoryFunction", "MotorFunction", "RegulatoryFunction", "HigherCognitiveFunction"] | None = Field(None, description="Type of CNS function, None if generic or other.")

class MouseDevelopmentalTimepoint(NamedEntity): # is-a LifeStage biolink
    """
    Developmental timepoints (or ranges) used specifically for Mus musculus (mouse).
    Embryonic examples:
      - Embryonic day: "pre-E5", "E10", "E12.5"  (a.k.a. 12.5 dpc)
      - Somite count: "16-somite stage" 
      - Theiler stage: "TS17" 
    Postnatal examples:
      - Postnatal day: "P0", "P14"
      - Postnatal week/month: "PW6" (week), "PM3" (month)
      - Lactation day (dam-centric): "LD10"
    """
    type: Literal["Embryonic", "Postnatal"] | None = Field(None, description="Broad developmental phase, None if generic or other.")
    scale: Literal[
        "E",   
        "Somite",    
        "TS",   
        "P",   
        "PW",  
        "PM", 
        "LD" 
    ] | None= Field(None, description="Mentioned/infered developmental scale")

    start_value: Optional[float] = Field(None, description="Numeric value (or start if range) on the selected scale (e.g., 12.5 for E12.5, 16 for 16-somite, 10 for E10-E12 or P10-P14)")
    end_value: Optional[float] = Field(None, description="If range, end value on the same scale (e.g., 14 for E12.5-E14)")

class HumanDevelopmentalTimepoint(NamedEntity): # is-a LifeStage biolink
    """
    Developmental timepoints (or ranges) used specifically for Homo sapiens (human).
    Embryonic examples:
      - Carnegie stage: "CS13"
      - Post-conception week: "PCW8", "4 weeks post-conception"
    Fetal examples:
      - Gestational week (from LMP): "GW20", "GA18w"
      - Trimester: "T1", "T2", "T3"
    Postnatal examples:
      - Day of life: "DOL3"
      - Postnatal age in weeks/months: "PNA6w", "PNA3m"
      - Postmenstrual age (GA + postnatal): "PMA35w"
    """
    type: Literal["Embryonic", "Fetal", "Postnatal"] | None = Field(None, description="Broad developmental phase, None if generic or other."
    )
    scale: Literal[
        "CS",  
        "PCW", 
        "GW",   
        "T",    
        "DOL", 
        "PNA",  
        "PMA"  
    ] | None = Field(..., description="Mentioned/infered developmental scale")

    start_value: Optional[float] = Field(None, description="Numeric value (or start if range) on the selected scale (e.g., 20 for GW20, 13 for CS13, 8 for 8 PCW, 3 for DOL3, or start of a range).")
    end_value: Optional[float] = Field(None, description="If range, end value on the same scale (e.g., 22 for GW20–GW22, 10 for PCW8–PCW10).")

if __name__ == "__main__":
    print(f"Exported entity schema")
    export_entities_json()