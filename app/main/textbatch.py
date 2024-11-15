from unicodedata import normalize
from flask_restx._http import HTTPStatus

from app.text_utils import count_words, extract_text
from app.main.translate import translate_from_to, translate_with_model

from app.main.translatable import Translatable
from app.main.text import Text

class TextBatch(Text):
    def __init__(self, texts):
        self.texts = texts
        self.translation = []
        self._input_file_name = '_DIRECT_INPUT'
        self._input_word_count = sum(map(count_words, texts))
        self._input_nfc_len = sum(map(lambda x: len(normalize('NFC', x)), texts))
        self.check_text_length()

    def translate_from_to(self, src, tgt):
        self.translation = [translate_from_to(src, tgt, t) for t in self.texts]
    
    def translate_with_model(self, model, src, tgt):
        self.translation = [translate_with_model(model, t, src, tgt) for t in self.texts]

    def get_text(self):
        return str(self.texts)

    def get_translation(self):
        return str(self.translation)

    def create_response(self, extra_headers):
        self.translation = [extract_text(t) for t in self.translation]
        self._output_word_count = sum(map(count_words, self.translation))
        headers = {
            **self.prep_billing_headers(),
            **extra_headers
        }
        print(self.translation)
        return {"translations": self.translation}, HTTPStatus.OK, headers
