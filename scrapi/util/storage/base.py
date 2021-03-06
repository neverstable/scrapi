import os
import json
from base64 import b64encode

from scrapi import settings
from scrapi.util import make_dir


class BaseStorage(object):
    METHOD = None

    # :: Str -> Str -> Nothing
    def _store(string, path):
        raise NotImplementedError('No store method')

    # :: Str -> Bool -> [RawDocument]
    def iter_raws(source, include_normalized=False):
        raise NotImplementedError('No iter raws method')

    # :: Str -> Str
    def get_as_string(self, path):
        raise NotImplementedError('No get as string method')

    # :: Str -> Dict
    def get_as_json(self, path):
        return json.loads(self.get_as_string(path))

    # :: Str -> Str
    def _build_path(self, raw_doc):
        path = [
            settings.ARCHIVE_DIRECTORY,
            raw_doc['source'],
            b64encode(raw_doc['docID']),
            raw_doc['timestamps']['harvestFinished']
        ]
        path = os.path.join(*path)
        make_dir(path)

        return path

    # :: NormalizedDocument -> Nothing
    def store_normalized(self, raw_doc, document, overwrite=False, is_push=False):

        path = self._build_path(raw_doc)
        path = os.path.join(path, 'normalized.json')
        self._store(json.dumps(document.attributes), path, overwrite=overwrite)

    # :: RawDocument -> Nothing
    def store_raw(self, document, is_push=False):
        if is_push:
            file_manifest = {'fileFormat': 'json'}
        else:
            file_manifest = settings.MANIFESTS[document['source']]

        manifest = {
            'harvestedTimestamp': document['timestamps']['harvestFinished'],
            'source': document['source']
        }

        doc_name = 'raw.{}'.format(file_manifest['fileFormat'])
        path = self._build_path(document)

        self.update_manifest(path, manifest)

        path = os.path.join(path, doc_name)

        self._store(document.get('doc'), path)

    # :: RawDocument -> Dict -> Nothing
    def update_manifest(self, path, fields):
        path = os.path.join(path, 'manifest.json')
        try:
            manifest = self.get_as_json(path)
        except Exception:  # TODO Make this more specific
            manifest = {}

        manifest.update(fields)
        self._store(json.dumps(manifest), path, overwrite=True)
