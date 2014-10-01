## Consumer for DOE Pages for SHARE

import time
import requests
from lxml import etree
from datetime import date, timedelta, datetime

import json

from nameparser import HumanName

from dateutil.parser import *

from scrapi.linter import lint
from scrapi.linter.document import RawDocument, NormalizedDocument

NAME = 'doepages'
TODAY = date.today()

NAMESPACES = {'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#', 
            'dc': 'http://purl.org/dc/elements/1.1/',
            'dcq': 'http://purl.org/dc/terms/'}

def consume(days_back=15):
    start_date = TODAY - timedelta(days_back)
    base_url = 'http://www.osti.gov/pages/pagesxml?nrows={0}&EntryDateFrom={1}'
    url = base_url.format('1', start_date.strftime('%m/%d/%Y'))
    initial_data = requests.get(url)
    initial_doc = etree.XML(initial_data.content)

    num_results = int(initial_doc.xpath('//records/@count', namespaces=NAMESPACES)[0])

    url = base_url.format(num_results, start_date.strftime('%m/%d/%Y'))
    print url
    data = requests.get(url)
    doc = etree.XML(data.content)

    records = doc.xpath('records/record')

    xml_list = []
    for record in records:
        doc_id = record.xpath('dc:ostiId/node()', namespaces=NAMESPACES)[0]
        record = etree.tostring(record)
        record = '<?xml version="1.0" encoding="UTF-8"?>\n' + record
        xml_list.append(RawDocument({
                    'doc': record,
                    'source': NAME,
                    'docID': doc_id,
                    'filetype': 'xml'
                }))

    return xml_list

def get_ids(doc, raw_doc):
    ids = {}
    ids['doi'] = (doc.xpath('//dc:doi/node()', namespaces=NAMESPACES) or [''])[0]
    ids['serviceID'] = raw_doc.get('docID')
    url = (doc.xpath('//dcq:identifier-citation/node()', namespaces=NAMESPACES) or [''])[0]
    if url == '':
        url = 'http://dx.doi.org/' + ids['doi']
    if url == '':
        raise Exception('Warning: url field is blank!')
    ids['url'] = url

    return ids

def get_contributors(doc):
    contributor_list = []
    full_contributors = doc.xpath('//dc:creator/node()', namespaces=NAMESPACES)[0].split(';')
    for person in full_contributors:
        name = HumanName(person)
        contributor = {
            'prefix': name.title,
            'given': name.first,
            'middle': name.middle,
            'family': name.last,
            'suffix': name.suffix,
            'email': '',
            'ORCID': ''
        }
        contributor_list.append(contributor)

    return contributor_list
def get_properties(doc):
    publisherInfo = {
        'publisher': (doc.xpath('//dcq:publisher/node()', namespaces=NAMESPACES) or [''])[0],
        'publisherSponsor': (doc.xpath('//dcq:publisherSponsor/node()', namespaces=NAMESPACES) or [''])[0],
        'publisherAvailability': (doc.xpath('//dcq:publisherAvailability/node()', namespaces=NAMESPACES) or [''])[0],
        'publisherResearch': (doc.xpath('//dcq:publisherResearch/node()', namespaces=NAMESPACES) or [''])[0],
        'publisherCountry': (doc.xpath('//dcq:publisherCountry/node()', namespaces=NAMESPACES) or [''])[0],
    }
    properties = {
        'publisherInfo': publisherInfo,
        'language': (doc.xpath('//dc:language/node()', namespaces=NAMESPACES) or [''])[0],
        'type': (doc.xpath('//dc:type/node()', namespaces=NAMESPACES) or [''])[0]
    }
    return properties

   # "publisherInfo": {
   #      "publisher": 
   #      "publisherSponsor": 
   #      "publisherAvailability": 
   #      "publisherResearch": 
   #      "publisherCountry": 
   #  },  

def get_date_created(doc):
    date_created = doc.xpath('//dc:date/node()', namespaces=NAMESPACES)[0]
    return parse(date_created).isoformat()

def get_date_updated(doc):
    date_updated = doc.xpath('//dc:dateEntry/node()', namespaces=NAMESPACES)[0]
    return parse(date_updated).isoformat()

def get_tags(doc):
    all_tags = doc.xpath('//dc:subject/node()', namespaces=NAMESPACES) + doc.xpath('//dc:subjectRelated/node()', namespaces=NAMESPACES)
    tags = []
    for taglist in all_tags:
        tags += taglist.split(',')
    return list(set([tag.lower().strip() for tag in tags]))

def normalize(raw_doc, timestamp):
    raw_doc_string = raw_doc.get('doc')
    doc = etree.XML(raw_doc_string)

    normalized_dict = {
        'title': doc.xpath('//dc:title/node()', namespaces=NAMESPACES)[0],
        'contributors': get_contributors(doc),
        'properties': get_properties(doc),
        'description': (doc.xpath('//dc:description/node()', namespaces=NAMESPACES) or [''])[0],
        'id': get_ids(doc, raw_doc),
        'source': NAME,
        'tags': get_tags(doc),
        'dateCreated': get_date_created(doc),
        'dateUpdated': get_date_updated(doc),
        'timestamp': str(timestamp)
    }

    print json.dumps(normalized_dict['tags'], indent=4)
    return NormalizedDocument(normalized_dict)


if __name__ == '__main__':
    print(lint(consume, normalize))
