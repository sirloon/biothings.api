from biothings.utils.dataload import alwayslist

class IDMapperBase(object):
    """
    Provide mapping between different sources
    """

    def __init__(self, name=None, convert_func=None, *args, **kwargs):
        """
        'name' may match an id_type (see uploaders). If None, mapper 
        will be applied to any document from a resource without id_type argument
        """
        self.map = None
        self.convert_func = convert_func
        self.name = name

    def load(self):
        """
        Do whatever is required to fill mapper with mapping data
        Can be called multiple time, the first time only will load data
        """
        raise NotImplementedError("sub-class and implement me")

    def translate(self,_id,transparent=False):
        """
        Return _id translated through mapper, or _id itself if not part of mapper
        If 'transparent' and no match, original _id will be returned
        """
        if self.need_load():
            self.load()
        default = transparent and _id or None
        conv = self.convert_func or (lambda x: x)
        return self.map.get(self.conv(_id),default)

    def __contains__(self,_id):
        if self.need_load():
            self.load()
        return _id in self.map

    def __len__(self):
        if self.need_load():
            self.load()
        return len(self.map)

    def process(self,docs,key_to_convert="_id",transparent=True):
        """
        Process 'key_to_convert' document key using mapping.
        If transparent and no match, original key will be used
        (so there's no change). Else, if no match, document will
        be discarded (default).
        Warning: key to be translated must not be None (it's considered
        a non-match)
        """
        for doc in docs:
            _id = doc.get(key_to_convert)
            _newid = self.translate(_id,transparent)
            if _newid is None and not transparent:
                continue
            for _oneid in alwayslist(_newid):
                _oneid = str(_oneid)
                doc[key_to_convert] = _oneid
                yield doc

    def need_load(self):
        return self.map is None



class TransparentMapper(IDMapperBase):

    def load(self, *args, **kwargs):
        self.map = {} # dummy mapping dict

    def process(self, docs, *args, **kwargs):
        return docs
