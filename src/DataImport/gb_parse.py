from Bio import SeqIO
import os
from re import search


def parse_genbank(genbank_file):
    """ Generator yielding contig and gene records

    Retrieves data from a genbank file to prepare for import to MongoDB
    :param genbank_file: a file ending with ".gb" or ".gbk" that contains genomic information
    :rtype generator[dict]: each iteration yields a record (dict) for insertion into MongoDB
    """
    with open(genbank_file, 'r') as in_handle:
        records = SeqIO.parse(in_handle, 'gb')

        # ToDo: Need a log file to record added locus_tags, species names etc, preferably with a way to reference back to original file
        for record in add_contig_data(records, genbank_file):
            yield record


def check_16S(feature):
    """
    Check if rRNA feature is a 16s gene
    :param feature: Biopython genbank feature
    :rtype Boolean: True if annotation indicates 16s and length >1000
    """
    if feature.type == 'rRNA':
        try:
            annotation = str(feature.qualifiers['product'])
        except KeyError:
            return False

        if search(r"16[sS]|ssu|SSU", annotation):
            if len(feature) > 1000:
                return True
            else:
                return False

def add_contig_data(records, genbank_file):
    contig_counter = 0
    contig_ids = []

    current_species = None
    for contig in records:
        contig_counter += 1
        try:
            species = contig.annotations['source']
        except KeyError:
            # uses filename (without extension) as species name
            species = os.path.splitext(os.path.basename(genbank_file))[0]

        if not species == current_species:
            print("Importing {}".format(species))
            current_species = species

        if contig.id in contig_ids: # in case the id field is present but not unique
            contig.id = "{}_{}".format(contig.id, contig_counter)
        else:
            contig_ids.append(contig.id)

        # ToDo: append list of gene records contained within contig?
        contig_record = {
            'type': 'contig',
            'dna_seq': str(contig.seq),
            'contig_id': contig.id,
            'species': species
        }

        yield contig_record

        for feature in add_features(contig, species):
            yield feature

def add_features(contig, species):
    locus_tag_counter = 0
    for feature in contig.features:
        locus_tag_counter += 1

        try:
            aa_seq = feature.qualifiers['translation'][0]
        except KeyError:
            aa_seq = None

        try:
            locus_tag = feature.qualifiers['locus_tag'][0]
        except KeyError:
            locus_tag = 'kv_{}'.format(str(locus_tag_counter).zfill(5))

        try:
            annotation = feature.qualifiers['product'][0]
        except KeyError:
            annotation = None

        feature_type = None
        if feature.type == 'CDS':
            feature_type = 'CDS'
        elif feature.type == 'rRNA':
            if check_16S(feature):
                feature_type = '16s'
            else:
                feature_type = 'rRNA'
        else:
            feature_type = feature.type

        # grabs DNA sequence from record object
        dna_seq = str(feature.extract(contig).seq)
        feature_record = {
            'type': feature_type,
            'dna_seq': dna_seq,
            'aa_seq': aa_seq,
            'locus_tag': locus_tag,
            'annotation': annotation,
            'species': species,
            'location': {
                'start': int(feature.location.start),
                'end': int(feature.location.end),
                'strand': feature.location.strand,
                'contig': contig.id},
        }

        yield feature_record
