import BIBparsley as bp

# Example usage
bibtex_filename = "ParaResWEC"  # Replace with your BibTeX file
parsed_bib = bp.read_bibtex_entries( bibtex_filename + ".bib" )

with open( bibtex_filename + "_updated.bib", "w" ) as bib_file:

    for key, entry in parsed_bib.items():

        bp.remove_dummy_fields( entry )
        bp.update_DOI( entry )
        str = bp.entry2str( key, entry ) 

        print( str, end='' )
        bib_file.write( str )
