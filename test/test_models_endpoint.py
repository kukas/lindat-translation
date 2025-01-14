# pylint: disable=missing-timeout
import unittest
import requests
import os
from pprint import pp
from test_languages_endpoint import _upload_binary_file

class ModelsEndpointTester(unittest.TestCase):
    ADDRESS_BASE = 'http://127.0.0.1:5000/api/v2/models'

    def setUp(self):
        os.makedirs("test_data", exist_ok=True)

    def test_list_models(self):
        r = requests.get(self.ADDRESS_BASE)
        self.assertEqual(r.status_code, 200)
        # test valid json
        self.assertTrue(r.json())
        # test that model list is in the json
        self.assertTrue("_links" in r.json())
    
    def test_model_info(self):
        r = requests.get(self.ADDRESS_BASE + "/en-cs")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json())
        self.assertTrue(r.json()["model"] == "en-cs")
    
    def test_translate(self):
        # Test successful translation request, direct input
        r = requests.post(self.ADDRESS_BASE+"/en-cs", data={
            "input_text": "this is a sample text"
        })
        # we need to set the encoding, 
        # the server does not define charset and it defaults to ISO-8859-1 for text/plain
        r.encoding = 'utf-8'
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'toto je ukázkový text\n')

        # Test successful translation request, file upload
        r = requests.post(self.ADDRESS_BASE+"/en-cs", headers={
            "accept": "application/json",
        }, files={
            'input_text': ('hello.txt', 'this is a sample text', 'text/plain')
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()[0], 'toto je ukázkový text\n')


    def test_empty(self):
        # Test empty request (input_text not set)
        r = requests.post(self.ADDRESS_BASE+"/en-cs")
        self.assertEqual(r.status_code, 400)
        self.assertIn("No text found", r.text)

        r = requests.post(self.ADDRESS_BASE+"/en-cs", data={
            "input_text": ""
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '')
        # with open("test_data/empty.txt", "w+") as f:
        #     f.write("hello world")
        r = requests.post(self.ADDRESS_BASE+"/en-cs", files={
            'input_text': ('empty.txt', '', 'text/plain', {'Expires': '0'})
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '')


    def test_srctgt_query(self):
        # correct usage of src/tgt on /model endpoint
        r = requests.post(self.ADDRESS_BASE+"/en-cs?src=en&tgt=cs", data={
            "input_text": "this is a sample text"
        })
        r.encoding = 'utf-8'
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'toto je ukázkový text\n')

        # incorrect usages
        for src, tgt in [("en", "uk"), ("uk", "cs"), ("cs", "en"), ("", 123)]:
            r = requests.post(self.ADDRESS_BASE+f"/en-cs?src={src}&tgt={tgt}", data={
                "input_text": "this is a sample text"
            })
            r.encoding = 'utf-8'
            self.assertEqual(r.status_code, 404)
            self.assertIn('This model does not support ', r.text)

    def test_srctgt_formdata(self):
        # correct usage of src/tgt on /model endpoint
        r = requests.post(self.ADDRESS_BASE+"/en-cs", data={
            "src": "en",
            "tgt": "cs",
            "input_text": "this is a sample text"
        })
        r.encoding = 'utf-8'
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'toto je ukázkový text\n')

        # incorrect usages
        for src, tgt in [("en", "uk"), ("uk", "cs"), ("cs", "en"), ("", 123)]:
            r = requests.post(self.ADDRESS_BASE+"/en-cs", data={
                "src": src,
                "tgt": tgt,
                "input_text": "this is a sample text"
            })
            r.encoding = 'utf-8'
            self.assertEqual(r.status_code, 404)
            self.assertIn('This model does not support ', r.text)

    def test_document_html(self):
        # Test successful translation request, file upload
        r = requests.post(self.ADDRESS_BASE+"/en-cs/file", files={
            'input_file': ('hello.html', '<p>This is <i>a <b>sample</b> text</i></p>', 'text/html')
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text.replace(" ", ""), '<p>Totoje<i><b>ukázkový</b>text</i></p>')

    def test_document_xml(self):
        # Test successful translation request, file upload
        r = requests.post(self.ADDRESS_BASE+"/en-cs/file", files={
            'input_file': ('hello.xml', '<p>This is <i>a <b>sample</b> text</i></p>', 'text/xml')
        })
        self.assertEqual(r.status_code, 200)
        expected = '<?xml version="1.0" encoding="UTF-8"?>\n'
        expected += '<p>Tohle je <i>a <b>vzorek</b> text</i></p>'
        self.assertEqual(r.text, expected)

    def test_document_odt(self):
        r = _upload_binary_file(self.ADDRESS_BASE+"/cs-en/file", "test_libreoffice.odt", "cs-en")
        self.assertEqual(r.status_code, 200)

    def test_translate_batch_wrong_contenttype(self):
        r = requests.post(self.ADDRESS_BASE+"/en-cs/batch", headers={
            "Content-Type": "text/plain",
            "accept": "application/json",
        }, json={
            "input_texts": ["Apple", "Banana", "Pineapple"]
        })
        r.encoding = 'utf-8'
        self.assertEqual(r.status_code, 415)
        self.assertEqual(r.json(),  {'message': 'Did not attempt to load JSON data because the request Content-Type was not \'application/json\'.'})



    def test_translate_batch(self):
        r = requests.post(self.ADDRESS_BASE+"/en-cs/batch", headers={
            "Content-Type": "application/json",
            "accept": "application/json",
        }, json={
            "input_texts": ["Apple", "Banana", "Pineapple"]
        })
        r.encoding = 'utf-8'
        # pp(r.json())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(),  {"translations": ["Jablko\n", "Banán\n", "Ananas\n"]})

        r = requests.post(self.ADDRESS_BASE+"/doc-en-cs/batch", json={
            "input_texts": [
                "Text about beautiful river banks, where one can swim in or chill out.",
                "I repeat, this text is about these banks."
            ]
        })
        # pp(r.json())
        r.encoding = 'utf-8'
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(),  {"translations": [
            "Text o krásných březích řek, kde si člověk může zaplavat nebo se odreagovat.\n", 
            "Opakuji, tento text je o těchto bankách.\n"
        ]})


if __name__ == "__main__":
    unittest.main()
