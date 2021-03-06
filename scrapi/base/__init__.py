# Classes for scrAPI Harvesters
from __future__ import unicode_literals

import abc
import time
import logging
from dateutil.parser import parse
from datetime import date, timedelta

import requests
from lxml import etree
from nameparser import HumanName

from scrapi import util
from scrapi.linter import lint
from scrapi.linter.document import RawDocument, NormalizedDocument

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


class BaseHarvester(object):
    """ This is a base class that all harvesters should inheret from

    Defines the copy to unicde method, which is useful for getting standard
    unicode out of xml results.
    """
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def harvest(self, days_back=1):
        pass

    @abc.abstractmethod
    def normalize(self, raw_doc):
        pass

    def lint(self):
        return lint(self.harvest, self.normalize)


class OAIHarvester(BaseHarvester):
    """ Create a harvester with a oai_dc namespace, that will harvest
    documents within a certain date range

    Contains functions for harvesting from an OAI provider, normalizing,
    and outputting in a way that scrapi can understand, in the most
    generic terms possible.

    For more information, see the OAI PMH specification:
    http://www.openarchives.org/OAI/openarchivesprotocol.html
    """

    NAMESPACES = {'dc': 'http://purl.org/dc/elements/1.1/',
                  'oai_dc': 'http://www.openarchives.org/OAI/2.0/',
                  'ns0': 'http://www.openarchives.org/OAI/2.0/'}

    RECORDS_URL = '?verb=ListRecords'

    META_PREFIX_DATE = '&metadataPrefix=oai_dc&from={}'

    RESUMPTION = '&resumptionToken='

    DEFAULT_ENCODING = 'UTF-8'

    record_encoding = None

    def __init__(self, name, base_url, timezone_granularity=False, timeout=0.5, property_list=None, approved_sets=None):
        self.name = name
        self.base_url = base_url
        self.property_list = property_list or ['date', 'language', 'type']
        self.approved_sets = approved_sets
        self.timeout = timeout
        self.timezone_granularity = timezone_granularity

    def harvest(self, days_back=1):

        start_date = str(date.today() - timedelta(int(days_back)))

        records_url = self.base_url + self.RECORDS_URL
        request_url = records_url + self.META_PREFIX_DATE.format(start_date)

        if self.timezone_granularity:
            request_url += 'T00:00:00Z'

        records = self.get_records(request_url, start_date)

        rawdoc_list = []
        for record in records:
            doc_id = record.xpath(
                'ns0:header/ns0:identifier', namespaces=self.NAMESPACES)[0].text
            record = etree.tostring(record, encoding=self.record_encoding)
            rawdoc_list.append(RawDocument({
                'doc': record,
                'source': util.copy_to_unicode(self.name),
                'docID': util.copy_to_unicode(doc_id),
                'filetype': 'xml'
            }))

        return rawdoc_list

    def get_records(self, url, start_date, resump_token=''):
        logger.info('Requesting url for harvesting: {}'.format(url))
        data = requests.get(url)

        doc = etree.XML(data.content)

        records = doc.xpath(
            '//ns0:record',
            namespaces=self.NAMESPACES
        )
        token = doc.xpath(
            '//ns0:resumptionToken/node()',
            namespaces=self.NAMESPACES
        )
        if len(token) == 1:
            time.sleep(self.timeout)
            base_url = url.replace(
                self.META_PREFIX_DATE.format(start_date), '')
            base_url = base_url.replace(self.RESUMPTION + resump_token, '')
            url = base_url + self.RESUMPTION + token[0]
            records += self.get_records(url, start_date, resump_token=token[0])

        return records

    def get_contributors(self, result):
        """ this grabs all of the fields marked contributors
        or creators in the OAI namespaces """

        contributors = result.xpath(
            '//dc:contributor/node()',
            namespaces=self.NAMESPACES
        )
        creators = result.xpath(
            '//dc:creator/node()',
            namespaces=self.NAMESPACES
        )

        all_contributors = contributors + creators

        contributor_list = []
        for person in all_contributors:
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

    def get_tags(self, result):
        tags = result.xpath('//dc:subject/node()', namespaces=self.NAMESPACES)

        for tag in tags:
            if ', ' in tag:
                tags.remove(tag)
                tags += tag.split(',')

        return [util.copy_to_unicode(tag.lower().strip()) for tag in tags]

    def get_ids(self, result, doc):
        """
        Gather the DOI and url from identifiers, if possible.
        Tries to save the DOI alone without a url extension.
        Tries to save a link to the original content at the source,
        instead of direct to a PDF, which is usually linked with viewcontent.cgi?
        in the url field
        """
        serviceID = doc.get('docID')
        identifiers = result.xpath(
            '//dc:identifier/node()', namespaces=self.NAMESPACES)
        url = ''
        doi = ''
        for item in identifiers:
            if 'doi' in item or 'DOI' in item:
                doi = item
                doi = doi.replace('doi:', '')
                doi = doi.replace('DOI:', '')
                doi = doi.replace('http://dx.doi.org/', '')
                doi = doi.strip(' ')
            if 'http://' in item or 'https://' in item:
                if 'viewcontent' not in item:
                    url = item

        return {
            'serviceID': serviceID,
            'url': util.copy_to_unicode(url),
            'doi': util.copy_to_unicode(doi)
        }

    def get_properties(self, result, property_list):
        """ property_list should be all of the properties in your particular
        OAI harvester that does not fit into the standard schema.

        When you create a class, pass a list of properties to be
        gathered in either the header or main body of the document,
        that will then be included in the properties section """

        properties = {}
        for item in property_list:
            prop = result.xpath(
                '//dc:{}/node()'.format(item),
                namespaces=self.NAMESPACES
            )
            prop.extend(result.xpath(
                '//ns0:{}/node()'.format(item),
                namespaces=self.NAMESPACES
            ))

            properties[item] = [util.copy_to_unicode(element) for element in prop]

        return properties

    def get_date_updated(self, result):
        dateupdated = result.xpath(
            '//ns0:header/ns0:datestamp/node()',
            namespaces=self.NAMESPACES
        )
        date_updated = parse(dateupdated[0]).isoformat()
        return util.copy_to_unicode(date_updated)

    def get_title(self, result):
        title = result.xpath(
            '//dc:title/node()',
            namespaces=self.NAMESPACES
        ) or ['']
        return util.copy_to_unicode(title[0])

    def get_description(self, result):
        description = result.xpath(
            '//dc:description/node()',
            namespaces=self.NAMESPACES
        ) or ['']

        return util.copy_to_unicode(description[0])

    def normalize(self, raw_doc):
        str_result = raw_doc.get('doc')
        result = etree.XML(str_result)

        if self.approved_sets:
            set_spec = result.xpath(
                'ns0:header/ns0:setSpec/node()',
                namespaces=self.NAMESPACES
            )
            # check if there's an intersection between the approved sets and the
            # setSpec list provided in the record. If there isn't, don't normalize.
            if not {x.replace('publication:', '') for x in set_spec}.intersection(self.approved_sets):
                logger.info('Series {} not in approved list'.format(set_spec))
                return None

        normalized = {
            'source': self.name,
            'title': self.get_title(result),
            'description': self.get_description(result),
            'id': self.get_ids(result, raw_doc),
            'contributors': self.get_contributors(result),
            'tags': self.get_tags(result),
            'properties': self.get_properties(result, self.property_list),
            'dateUpdated': self.get_date_updated(result)
        }

        status = result.xpath('ns0:header/@status', namespaces=self.NAMESPACES)
        if status and status[0] == 'deleted':
            logger.info('Deleted record, not normalizing {}'.format(normalized['id']['serviceID']))
            return None

        return NormalizedDocument(normalized)
