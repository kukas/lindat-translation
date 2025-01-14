import datetime
from flask import request
from flask.helpers import make_response
from flask_restx import Resource
from flask_restx.api import output_json

from app.main.api.restplus import api
from app.main.api.translation.parsers import text_input_with_src_tgt
from app.db import log_translation, log_access
from app.text_utils import extract_text
from app.main.text import Text
from app.main.document import Document
from app.model_settings import models

class MyAbstractResource(Resource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._start_time = None

    @classmethod
    def to_text(cls, data, code, headers):
        return make_response(extract_text(data), code, headers)
    
    def set_media_type_representations(self):
        self.representations = self.representations if self.representations else {}
        if 'text/plain' not in self.representations:
            self.representations['text/plain'] = MyAbstractResource.to_text
        if 'application/json' not in self.representations:
            self.representations['application/json'] = output_json

    def start_time_request(self):
        self._start_time = datetime.datetime.now()

    def get_text_from_request(self):
        """
        Extracts text to translate from a http request.

        There are two ways to send the text:
        1) as plain text file sent as "multipart/form-data"
        2) as text form field sent as "application/x-www-form-urlencoded"
        """
        # if the request contains uploaded files
        if request.files and 'input_text' in request.files:
            input_file = request.files.get('input_text')
            if input_file.filename == '':
                api.abort(code=400, message='Empty filename')
            if input_file.content_type == 'text/plain':
                return Text.from_file(input_file)
        # if contains direct text
        if request.form and 'input_text' in request.form:
            return Text(request.form.get('input_text'))

        # if we didn't return anything, abort:
        api.abort(code=400, message='No text found in the input_text form/field or in request files')

    def get_file_from_request(self):
        """
        Extracts an uploaded file to translate from a http request
        """
        # if the request contains uploaded files
        if request.files and 'input_file' in request.files:
            input_file = request.files.get('input_file')
            return Document.from_file(input_file)
        else:
            api.abort(code=400, message='No file sent')


    def process_translatable_languages_endpoint(self, translatable, ns, log):
        """
        Translate the uploaded translatable
        in /languages/ and /languages/file endpoints.
        """
        args = text_input_with_src_tgt.parse_args(request)
        src = args.get('src') or 'en'
        tgt = args.get('tgt') or 'cs'
        try:
            translatable.translate_from_to(src, tgt)
            extra_msg = 'src={};tgt={}'.format(src, tgt)
            return translatable.create_response(self.extra_headers(extra_msg))
        except ValueError as e:
            log.exception(e)
            ns.abort(code=404, message='Can\'t translate from {} to {}'.format(src, tgt))
        finally:
            try:
                self.log_request(src, tgt, translatable)
            except Exception as ex:
                log.exception(ex)
    
    def process_translatable_models_endpoint(self, model, translatable, ns, log, src, tgt):
        # map model name to model obj
        model = models.get_model(model)
        src_default = list(model.supports.keys())[0]
        src = src or src_default # NOTE: replaces falsy values in request to default language
        if src not in model.supports.keys():
            ns.abort(code=404,
                      message='This model does not support translation from {}'
                      .format(src))
        tgt_default = list(model.supports[src])[0]
        tgt = tgt or tgt_default # NOTE: replaces falsy values in request to default language
        if tgt not in model.supports[src]:
            ns.abort(code=404,
                      message='This model does not support translation from {} to {}'
                      .format(src, tgt))
        try:
            translatable.translate_with_model(model, src, tgt)
            extra_msg = 'src={};tgt={};model={}'.format(src, tgt, model.name)
            return translatable.create_response(self.extra_headers(extra_msg))
        finally:
            try:
                self.log_request(src, tgt, translatable)
            except Exception as ex:
                log.exception(ex)

    def get_additional_args_from_request(self):
        args = text_input_with_src_tgt.parse_args(request)
        return {
            'author': args.get('author') or 'unknown',
            'frontend': args.get('frontend') or args.get('X-Frontend') or 'unknown',
            'app_version': args.get('X-App-Version') or 'unknown',
            'user_lang': args.get('X-User-Language') or 'unknown',
            'input_type': args.get('inputType') or 'keyboard',
            'log_input': args.get('logInput', False),
            'ip_address': request.headers.get('X-Real-IP', 'unknown')
        }

    def extra_headers(self, extra_msg):
        end = datetime.datetime.now()
        assert self._start_time, "You did not run start_time_request()"
        return {
            'X-Billing-Start-Time': self._start_time,
            'X-Billing-End-Time': end,
            'X-Billing-Duration': str(end - self._start_time),
            'X-Billing-Extra': extra_msg
        }

    def log_request(self, src, tgt, translatable):
        self.log_request_with_additional_args(src=src, tgt=tgt, translatable=translatable, **self.get_additional_args_from_request())

    def log_request_with_additional_args(self, src, tgt, author, frontend, input_type, log_input, ip_address, translatable, app_version, user_lang):
        duration_us = int((datetime.datetime.now() - self._start_time) / datetime.timedelta(microseconds=1))
        log_access(src_lang=src, tgt_lang=tgt, author=author, frontend=frontend,
                   input_nfc_len=translatable._input_nfc_len, duration_us=duration_us, input_type=input_type,
                   app_version=app_version, user_lang=user_lang)
        if log_input:
            log_translation(src_lang=src, tgt_lang=tgt, src=translatable.get_text(), tgt=translatable.get_translation(),
                            author=author, frontend=frontend, ip_address=ip_address, input_type=input_type,
                            app_version=app_version, user_lang=user_lang)
