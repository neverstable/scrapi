"""
A harvester for metadata from the ResearchWorks at the University of Washington, for the SHARE project

More information available at: https://github.com/CenterForOpenScience/SHARE/blob/master/providers/edu.washington.researchworks.md

Sample API call: http://digital.lib.washington.edu/dspace-oai/request?verb=ListRecords&metadataPrefix=oai_dc&from=2014-10-01
"""

from __future__ import unicode_literals

from scrapi.base import OAIHarvester


uwashington = OAIHarvester(
    name='uwashington',
    base_url='http://digital.lib.washington.edu/dspace-oai/request',
    property_list=['type', 'source', 'publisher', 'format', 'date',
                   'identifier', 'setSpec', 'rights', 'language']
)

harvest = uwashington.harvest
normalize = uwashington.normalize
