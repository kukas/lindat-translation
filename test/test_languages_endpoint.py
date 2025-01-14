# pylint: disable=missing-timeout
import unittest
import requests
import os
from pprint import pp
from math import ceil

def _upload_binary_file(url, filename, langpair):
    src, tgt = langpair.split("-")
    path_in = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data", filename)
    with open(path_in, "rb") as f:
        r = requests.post(url, data={
            "src": src,
            "tgt": tgt,
        }, files={
            'input_file': f
        })

    # Uncomment to save the file:
    # outname = r.headers["X-Billing-Filename"]
    # with open(outname, 'wb') as f:
    #     for chunk in r.iter_content(chunk_size=1024): 
    #         if chunk:
    #             f.write(chunk)
    return r

class LanguagesEndpointTester(unittest.TestCase):
    ADDRESS_BASE = 'http://127.0.0.1:5000/api/v2/languages/'
    ADDRESS_FILE = ADDRESS_BASE + "file"
    ADDRESS_BATCH = ADDRESS_BASE + "batch"
    en_cs = {
        "src": "en",
        "tgt": "cs",
    }
    cs_en = {
        "src": "cs",
        "tgt": "en",
    }
    def setUp(self):
        os.makedirs("test_data", exist_ok=True)

    def test_list_languages(self):
        r = requests.get(self.ADDRESS_BASE)
        self.assertEqual(r.status_code, 200)
        # test valid json
        self.assertTrue(r.json())
        # test that language list is in the json
        self.assertTrue("_links" in r.json())
    
    def test_translate(self):
        # Test successful translation request, direct formdata input
        r = requests.post(self.ADDRESS_BASE, data={
            "src": "en",
            "tgt": "cs",
            "input_text": "this is a sample text"
        })
        # we need to set the encoding, 
        # the server does not define charset and it defaults to ISO-8859-1 for text/plain
        r.encoding = 'utf-8'
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'toto je ukázkový text\n')

        # Test successful translation request, query parameters
        r = requests.post(self.ADDRESS_BASE+"?src=en&tgt=cs", data={
            "input_text": "this is a sample text"
        })
        r.encoding = 'utf-8'
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'toto je ukázkový text\n')

        # Test successful translation request, plaintext upload
        r = requests.post(self.ADDRESS_BASE, headers={
            "accept": "application/json",
        }, data=self.en_cs, files={
            'input_text': ('hello.txt', 'this is a sample text', 'text/plain')
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()[0], 'toto je ukázkový text\n')

    def test_wrong_accept(self):
        r = requests.post(self.ADDRESS_BASE+"?src=en&tgt=cs", headers={
            "accept": "text/xml",
        }, data={
            "input_text": "this is a sample text"
        })
        self.assertEqual(r.status_code, 406)
        self.assertIn("not acceptable", r.text)

    def test_wrong_contenttype(self):
        r = requests.post(self.ADDRESS_BASE+"?src=en&tgt=cs", headers={
            "Content-Type": "text/xml",
        }, data={
            "input_text": "this is a sample text"
        })
        pp(r.text)
        self.assertEqual(r.status_code, 400)
        self.assertIn("No text found in the input_text", r.text)

    def test_empty(self):
        # Test empty request (input_text not set)
        r = requests.post(self.ADDRESS_BASE, data=self.en_cs)
        self.assertEqual(r.status_code, 400)
        self.assertIn("No text found", r.text)

        r = requests.post(self.ADDRESS_BASE, data={
            "src": "en",
            "tgt": "cs",
            "input_text": ""
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '')
        r = requests.post(self.ADDRESS_FILE, data=self.en_cs, files={
            'input_file': ('empty.txt', '', 'text/plain')
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, '')
        r = requests.post(self.ADDRESS_FILE, data=self.en_cs, files={
            'input_file': ('empty.txt', None, 'text/plain')
        })
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.text, '{"message": "No file sent"}\n')

    def test_wrong_extension(self):
        # wrong extension
        r = requests.post(self.ADDRESS_FILE, data=self.en_cs, files={
            'input_file': ('empty.zip', b"asdfasdaf", 'application/zip')
        })
        self.assertEqual(r.status_code, 415)
        self.assertEqual(r.text, '{"message": "Unsupported file type for translation"}\n')


    def test_srctgt(self):
        # the default language pair is en-cs
        # missing tgt
        r = requests.post(self.ADDRESS_BASE, data={
            "src": "en",
            "input_text": "this is a sample text"
        })
        self.assertEqual(r.status_code, 200)
        # missing src
        r = requests.post(self.ADDRESS_BASE, data={
            "tgt": "cs",
            "input_text": "this is a sample text"
        })
        self.assertEqual(r.status_code, 200)
        # missing both
        r = requests.post(self.ADDRESS_BASE, data={
            "input_text": "this is a sample text"
        })
        self.assertEqual(r.status_code, 200)

    def test_nonexistent_srctgt(self):
        # src+tgt in formdata
        r = requests.post(self.ADDRESS_BASE, data={
            "src": "NONEXISTENT_LANG",
            "tgt": "NONEXISTENT_LANG",
            "input_text": "this is a sample text"
        })
        self.assertEqual(r.status_code, 404)
        self.assertIn("message", r.json())
        self.assertIn("Can\'t translate from NONEXISTENT_LANG to NONEXISTENT_LANG", r.json()["message"])
        # src+tgt in query
        r = requests.post(self.ADDRESS_BASE+"?src=NONEXISTENT_LANG&tgt=NONEXISTENT_LANG", data={
            "input_text": "this is a sample text"
        })
        self.assertEqual(r.status_code, 404)
        self.assertIn("message", r.json())
        self.assertIn("Can\'t translate from NONEXISTENT_LANG to NONEXISTENT_LANG", r.json()["message"])


    def test_document_html(self):
        # Test successful translation request, file upload
        r = requests.post(self.ADDRESS_FILE, data=self.en_cs, files={
            'input_file': ('hello.html', '<p>This is <i>a <b>sample</b> text</i></p><p><p><p></p></p></p>', 'text/html')
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text.replace(" ", ""), '<p>Totoje<i><b>ukázkový</b>text</i></p><p><p><p></p></p></p>')

    def test_document_xml(self):
        # Test successful translation request, file upload
        r = requests.post(self.ADDRESS_FILE, data=self.en_cs, files={
            'input_file': ('hello.xml', '<p>This is <i>a <b>sample</b> text</i></p>', 'text/xml')
        })
        self.assertEqual(r.status_code, 200)
        expected = '<?xml version="1.0" encoding="UTF-8"?>\n'
        expected += '<p>Toto je <i>a <b>ukázka</b> text</i></p>'
        self.assertEqual(r.text, expected)


    def test_document_odt(self):
        # Test successful translation request, file upload
        r = _upload_binary_file(self.ADDRESS_FILE, "test_libreoffice.odt", "cs-en")
        self.assertEqual(r.status_code, 200)

    def test_too_long_text(self):
        # too long text
        r = requests.post(self.ADDRESS_BASE, data={
            "input_text": "This is a "*(1024*10) # 100kB
        })
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.text, '{"message": "The total text length in the request exceeds the translation limit."}\n')

        r = requests.post(self.ADDRESS_FILE, files={
            'input_file': ('hello.txt', "This is a "*(1024*10), 'text/plain') # 100kB
        })
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.text, '{"message": "The total text length in the document exceeds the translation limit."}\n')

    def test_too_long_doc(self):
        text = "<p><p><p><p>How are you?</p></p></p></p>"
        without_tags = text.replace("<p>", "").replace("</p>", "")
        repeats = ceil(102400/len(without_tags)) + 1
        final = text*repeats
        r = requests.post(self.ADDRESS_FILE, files={
            'input_file': ('hello.html', final, 'text/html')
        })
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.text, '{"message": "The total text length in the document exceeds the translation limit."}\n')

    def test_translate_batch(self):
        r = requests.post(self.ADDRESS_BATCH, headers={
            "Content-Type": "application/json",
            "accept": "application/json",
        }, json={
            "input_texts": ["Apple", "Banana", "Pineapple"],
            "src": "en",
            "tgt": "cs"
        })
        r.encoding = 'utf-8'
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(),  {"translations": ["Jablko\n", "Banán\n", "Ananas\n"]})

        r = requests.post(self.ADDRESS_BATCH, headers={
            "accept": "application/json",
        }, json={
            "input_texts": [
                "Text about beautiful river banks, where one can swim in or chill out.",
                "I repeat, this text is about these banks."
            ]
        })
        r.encoding = 'utf-8'
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(),  {"translations": [
            "Text o krásných březích řek, kde si člověk může zaplavat nebo se odreagovat.\n", 
            "Opakuji, tento text je o těchto bankách.\n"
        ]})


if __name__ == "__main__":
    unittest.main()
