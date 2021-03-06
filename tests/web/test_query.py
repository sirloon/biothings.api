'''
    Biothings Query Component Common Tests
'''


from helper import BiothingsTestCase


class TestQuery(BiothingsTestCase):

    def setUp(self):
        super().setUp()
        client = self.settings.get_es_client()
        client.index(
            index='bts_test',
            doc_type=self.settings.ES_DOC_TYPE,
            body={
                "1101": "test-299",
                "1102": "test-300"
            }, id=1)
        self.settings.ES_INDEX = 'bts_test'

    def test_01(self):
        ''' KWARGS CTRL Format Json '''
        self.query(q='__all__', size='1')

    def test_02(self):
        ''' KWARGS CTRL Format Yaml '''
        res = self.request('query?q=__all__&size=1&format=yaml').text
        assert res.startswith('max_score:')

    def test_03(self):
        ''' KWARGS CTRL Format Html '''
        res = self.request('query?q=__all__&size=1&format=html').text
        assert '<html>' in res

    def test_11(self):
        ''' GET DOC '''
        res = self.request('doc/1')
        assert res.json()['_id'] == '1'

    def test_21(self):
        ''' GET QUERY'''
        self.query(q=299)

    def test_51(self):
        ''' HANDLE Unmatched Quotes'''
        # Sentry
        # Issue 529121368
        # Event 922fc99638cb4987bccbfd30c914ff03
        _q = 'query?q=c("ZNF398", "U2AF...'
        self.request(_q, expect_status=400)
