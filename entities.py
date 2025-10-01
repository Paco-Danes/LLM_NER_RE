from pydantic import BaseModel, Field

class NamedEntity(BaseModel):
    name: str = Field(..., description="")
    def __init_subclass__(cls):
        super().__init_subclass__() # call BseModel's __init_subclass__
        cls.model_fields["name"].description = f"Name of the {cls.__name__.lower()} as it appears in the text."

# ---- Your entities (add more here) from BioLink model ----
class Protein(NamedEntity):
    """
    A polypeptide chain (or set of chains) that folds into a functional 3D structure, often acting as an enzyme, receptor, structural molecule, transporter, etc.
    Examples: "Hemoglobin", "EGFR", "p53" (TP53 protein), "Insulin", "Cytochrome c", "Myosin heavy chain", "CFTR".
    """

class ProteinDomain(NamedEntity):
    """
    A stable, independently folding structural or functional unit within a protein, often conserved across proteins.
    Examples: "SH3 domain", "SH2 domain", "GAF domain", "Kringle domain", "WD40 repeat", "Zinc finger domain".
    """

class Gene(NamedEntity):
    """
    A stretch of DNA (or locus) that encodes (or is associated with) a functional product, such as an RNA or protein.
    Examples: "BRCA1", "TP53", "EGFR gene", "MYC", "APOE", "CFTR gene", "HBB".
    """

class GeneFamily(NamedEntity):
    """
    A set of genes descended by duplication from a common ancestral gene, often with related functions.
    Examples: "HOX gene family", "Cytochrome P450 family", "G-protein coupled receptor family", "WntFamily", "NotchLigandFamily".
    """

class Disease(NamedEntity):
    """
    A medical condition or disorder affecting an organism, typically with recognized signs/symptoms or pathology.
    Examples: "Alzheimer's disease", "Type 2 diabetes", "Breast cancer", "Cystic fibrosis", "Parkinson's disease", "Malaria".
    """

class Drug(NamedEntity):
    """
    A chemical or biologic agent used to treat, cure, prevent, or diagnose disease.
    Examples: "Imatinib", "Aspirin", "Trastuzumab", "Metformin", "Penicillin", "Nivolumab", "Atorvastatin".
    """

class Cell(NamedEntity):
    """
    A basic living unit of an organism, often a specialized cell type in multicellular organisms.
    Examples: "HeLa cell", "T-cell", "epithelial cell", "neuron", "adipocytes", "myocytes", "erythrocytes", "leukocytes", "osteocytes", "microglia", "B-cell".
    """

class Chromosome(NamedEntity):
    """
    A long DNA molecule (plus associated proteins) that bears genes in a linear (or circular) arrangement.
    Examples: "Chromosome 17", "X chromosome", "chr1p36.3", "Chromosome 21", "Y chromosome", "mtDNA" (mitochondrial DNA).
    """

class SequenceVariant(NamedEntity):
    """
    A variant (mutation, polymorphism, insertion, deletion, etc.) in a DNA, RNA, or protein sequence relative to a reference.
    Examples: "BRCA1 c.68_69delAG", "EGFR L858R", "rs334 (HbS)" (the sickle variant), "KRAS G12D", "ΔF508 CFTR", "BRAF V600E".
    """

class MacromolecularComplex(NamedEntity):
    """
    A functional complex formed by multiple molecules (proteins, nucleic acids, etc.) interacting together.
    Examples: "ribosome", "proteasome", "ATP synthase", "spliceosome", "RNA polymerase II holoenzyme", "photosystem II".
    """

class Pathway(NamedEntity):
    """
    A series of biochemical or signaling steps in a cell, through which molecules interact and transform, resulting in certain cellular outcomes.
    Examples: "Glycolysis pathway", "MAPK signaling pathway", "Wnt signaling", "TCA cycle", "PI3K-Akt signaling pathway", "Notch signaling".
    """

class MolecularActivity(NamedEntity):
    """
    An execution of a molecular function carried out by a gene product or macromolecular complex.
    Examples: "kinase activity", "DNA binding activity", "phosphatase activity", "helicase activity", "oxidoreductase activity", "ligase activity".
    """

class PhenotypicFeature(NamedEntity):
    """
    An observable trait, characteristic, or phenotype at organism, tissue, or cellular level.
    Examples: "hypertension", "hypercholesterolemia", "dysplasia", "reduced growth rate", "anemia", "microcephaly", "insulin resistance".
    """

class SmallMolecule(NamedEntity):
    """
    A low-molecular-weight organic or inorganic compound (not a large polymer), often used as metabolite, drug, ligand, or probe.
    Examples: "glucose", "ATP", "ibuprofen", "cAMP", "NADH", "dopamine", "lactic acid".
    """

class TissueOrOrgan(NamedEntity):
    """
    A multicellular structure or collection of cells forming a functional part of an organism.
    Examples: "liver", "kidney cortex", "heart tissue", "pancreatic islets", "skeletal muscle", "retina", "bone marrow".
    """

class Transcript(NamedEntity):
    """
    The RNA product transcribed from a gene (before or after splicing), such as mRNA, noncoding RNA, etc.
    Examples: "BRCA1-201 (transcript isoform)", "TP53 mRNA variant", "miR-21 precursor RNA", "XIST lncRNA", "HBB transcript variant 2".
    """

class Polypeptide(NamedEntity):
    """
    A linear chain of amino acids (protein or fragment) that may or may not fold into a functional domain.
    Examples: "insulin B chain", "synthetic peptide fragment p53(15-29)", "amyloid-β (1-42)", "angiotensin II peptide".
    """

class CellularComponent(NamedEntity):
    """
    A subcellular structure or location within a cell (organelle, compartment, etc.).
    Examples: "mitochondrion", "nucleus", "endoplasmic reticulum", "Golgi apparatus", "ribosome", "lysosome", "peroxisome", "plasma membrane".
    """

class BrainRegion(NamedEntity):
    """
    A distinct anatomical region of the brain, involved in specific neural functions or processes.
    Examples: "hippocampus", "amygdala", "cerebral cortex", "hindbrain", "midbrain", "thalamus", "cerebellum".
    """

class BiologicalProcess(NamedEntity):
    """
    One or more causally connected executions of molecular functions.
    Examples: "cell cycle", "apoptosis", "DNA repair", "signal transduction", "angiogenesis", "autophagy", "immune response".
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

class CellularOrganism(NamedEntity):
    """
    Any life form made up of one or more cells, including animals, plants, fungi, and protists.
    Examples: "Homo sapiens", "Arabidopsis thaliana", "Saccharomyces cerevisiae", "Caenorhabditis elegans", "Drosophila melanogaster".
    """

class Metabolite(NamedEntity):
    """
    A small molecule that is an intermediate or product of metabolism, often found in specific biochemical pathways.
    Examples: "pyruvate", "lactate", "glutamate", "cholesterol", "acetyl-CoA", "succinate", "uridine".
    """

class Intron(NamedEntity):
    """
    A non-coding segment of a gene that is transcribed into RNA but removed during RNA splicing, so it does not appear in the mature RNA transcript.
    Examples: "BRCA1 intron 2", "TP53 intron 4", "CFTR gene [...] in its intron 8", "intron 44 of gene DMD".
    """

class Exon(NamedEntity):
    """
    A contiguous segment of a gene that remains in the mature RNA transcript after splicing.
    Examples: "BRCA1 gene [...] by analysis of its exon 11", "TP53 exon 7", "DMD exon 45", "exon 10 of CFTR gene".
    """

class MessengerRNA(NamedEntity):
    """
    Messenger RNA (mRNA) molecules that serve as templates for protein synthesis, often gene-specific and with transcript isoforms.
    Examples: "TP53 mRNA", "BRCA1-201 transcript", "EGFR mRNA variant 3" "c-Myc mRNA", "VEGF-A messenger RNA".
    """

class TransferRNA(NamedEntity):
    """
    Transfer RNA (tRNA) molecules that carry amino acids to ribosomes during protein synthesis.
    Examples: "tRNA^Met", "initiator methionyl-tRNA", "human mitochondrial tRNA-Leu(UUR)", "tRNAGly(GCC)", "E. coli tRNA^Lys".
    """

class RibosomalRNA(NamedEntity):
    """
    Ribosomal RNA (rRNA) molecules that form structural and catalytic components of ribosomes.
    Examples: "16S rRNA gene fragment", "human 28S rRNA", "yeast 25S rRNA", "5.8S rRNA", "E. coli 23S ribosomal RNA".
    """

class MicroRNA(NamedEntity):
    """
    Small (~21–25 nt) non-coding RNAs that regulate gene expression post-transcriptionally.
    Examples: "miR-34a-5p", "let-7 family", "miRNA-200c", "miR-155 expression", "hsa-miR-17".
    """

class LongNoncodingRNA(NamedEntity):
    """
    Non-protein-coding RNAs >200 nucleotides, often involved in regulation and chromatin remodeling.
    Examples: "XIST lncRNA", "MALAT1 transcript", "HOTAIR RNA", "NEAT1", "GAS5 noncoding RNA".
    """

class SmallNuclearRNA(NamedEntity):
    """
    Small nuclear RNAs (snRNAs) mainly functioning in pre-mRNA splicing and snRNP complexes.
    Examples: "U1 snRNA", "U2 small nuclear RNA", "human U6atac", "Drosophila U7 snRNA", "spliceosomal RNA U5".
    """

class SmallNucleolarRNA(NamedEntity):
    """
    Small nucleolar RNAs (snoRNAs) that guide chemical modifications (methylation, pseudouridylation) of rRNAs and other RNAs.
    Examples: "SNORD44", "U3 snoRNA", "mouse SNORD116 cluster".
    """

class CircularRNA(NamedEntity):
    """
    Covalently closed circular RNAs with regulatory or potential coding roles.
    Examples: "circHIPK3", "circular RNA derived from CDR1as", "circZNF609", "circMTO1", "hsa_circ_0000064".
    """

class PiwiInteractingRNA(NamedEntity):
    """
    Small RNAs (piRNAs) associated with PIWI proteins, mainly silencing transposable elements.
    Examples: "piR-651", "piRNA-54265", "piR-hsa-823", "mouse pachytene piRNAs".
    """

class GuideRNA(NamedEntity):
    """
    RNA molecules that guide sequence-specific modification or cleavage, including CRISPR gRNAs and RNA editing guides.
    Examples: "sgRNA targeting TP53 exon 4", "CRISPR-Cas9 gRNA against EGFR", "tracrRNA", "mitochondrial gRNA".
    """

# function to retrieve entity list that includes all classes. If multiple inheritance is used, recursively get all subclasses
def Entity_Collector(root = NamedEntity, recursion=False):
    if recursion:
        subclasses = set(root.__subclasses__())
        for sub in root.__subclasses__():
            subclasses.update(Entity_Collector(sub, recursion=True))
        return list(subclasses)

    return [cls for cls in NamedEntity.__subclasses__()]