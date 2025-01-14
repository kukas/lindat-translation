import logging
from flask import request, url_for
from flask_restx import Namespace, Resource, fields

from app.main.api.translation.endpoints.MyAbstractResource import MyAbstractResource
from app.main.api.translation.parsers import upload_parser, text_input_with_src_tgt
from app.model_settings import models
from app.main.textbatch import TextBatch

from app.main.api_examples.model_resource_example import *
from app.main.api_examples.models_resource_example import *

from app.settings import FILE_TRANSLATE_MIMETYPES

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

ns = Namespace('models', description='Operations related to translation models')

_models_item_relation = 'item'

link = ns.model('Link', {
        'href': fields.String,
        'name': fields.String,
        'title': fields.String,
        'type': fields.String,
        'deprecation': fields.String,
        'profile': fields.String,
        'templated': fields.Boolean,
        'hreflang': fields.String
})

# resource = ns.model('Resource', {
#    '_links': fields.List(fields.Nested(link, skip_none=True)),
#    '_embedded': fields.List(fields.Nested(resource))
#})


def identity(x):
    return x


def add_href(model):
    model.add_href(url_for('.models_model_item', model=model.model))
    return model


def get_templated_translate_link(model):
    params = ['src', 'tgt']
    url = url_for('.models_model_item', model=model).rstrip('/')
    query_template = '{?' + ','.join(params) + '}'
    return {'href': url + query_template, 'templated': True}


# TODO refactor with @api.model? https://flask-restplus.readthedocs.io/en/stable/swagger.html
model_resource = ns.model('ModelResource', {
    '_links': fields.Nested(ns.model('ModelResourceLinks', {
        'self': fields.Nested(link, attribute=lambda x: {'href': url_for(
            '.models_model_item', model=x.model)}, skip_none=True),
        'translate': fields.Nested(link, attribute=lambda x: get_templated_translate_link(x.model),
                                   skip_none=True)
    }), attribute=identity, example=model_resource_links_example),
    'default': fields.Boolean(example=True),
    'domain': fields.String(example="Domain name is usually empty"),
    'model': fields.String(required=True, example='en-cs'),
    'supports': fields.Raw(required=True, example={'en': ['cs']}),
    'title': fields.String(example="en-cs (English->Czech (CUBBITT))"),
})

models_links = ns.model('ModelLinks', {
    _models_item_relation: fields.List(fields.Nested(link, skip_none=True), attribute='models'),
    'self': fields.Nested(link, skip_none=True)
})

models_resources = ns.model('ModelsResource', {
    '_links': fields.Nested(models_links,
                            attribute=lambda x: {'self':
                                                 {'href': url_for('.models_model_collection')},
                                                 'models': list(map(add_href, x['models']))},
                            example=models_resource_links_example
                            ),
    '_embedded': fields.Nested(ns.model('EmbeddedModels', {
        _models_item_relation: fields.List(fields.Nested(model_resource, skip_none=True),
                                        attribute='models')
    }), attribute=identity, example=models_resource_embedded_example)
})


@ns.route('/')
class ModelCollection(Resource):

    @ns.marshal_with(models_resources, skip_none=True, code=200, description='Success')
    def get(self):
        """
        Returns a list of available models
        """
        return {'models': models.get_models()}

model_names = str(tuple(models.get_model_names()))
# TODO should expose templated urls in hal?
@ns.route(f'/<any{model_names}:model>')
@ns.param(**{'name': 'model', 'description': 'model name', 'x-example': 'en-cs', '_in': 'path'})
class ModelItem(MyAbstractResource):
    @ns.produces(['application/json', 'text/plain'])
    @ns.response(code=200, description="Success", model=str)
    @ns.response(code=415, description="You sent a file but it was not text/plain")
    @ns.param(**{'name': 'tgt', 'description': 'Target language (e.g., `cs` for Czech)', 'x-example': 'cs'})
    @ns.param(**{'name': 'src', 'description': 'Source language (e.g., `en` for English)', 'x-example': 'en'})
    @ns.param(**{'name': 'input_text', 'description': 'text to translate',
                 'x-example': 'this is a sample text', '_in': 'formData'})
    def post(self, model):
        """
        Send text to be processed by the selected model.
        It expects the text in variable called `input_text` and handles both "application/x-www-form-urlencoded" and "multipart/form-data" (for uploading files)
        If you don't provide src or tgt some will be chosen for you!
        """
        self.set_media_type_representations() # ensures correct output Content-Type according to the requests Accept header
        self.start_time_request()
        translatable = self.get_text_from_request()
        return self.process_translatable_models_endpoint(model, translatable, ns, log)

    @ns.marshal_with(model_resource, skip_none=True)
    def get(self, model):
        """
        Get model's details
        """
        return models.get_model(model)

@ns.route(f'/<any{model_names}:model>/batch')
class BatchTranslation(MyAbstractResource):
    @ns.param(**{'name': 'tgt', 'description': 'Target language (e.g., `cs` for Czech)', 'x-example': 'cs'})
    @ns.param(**{'name': 'src', 'description': 'Source language (e.g., `en` for English)', 'x-example': 'en'})
    @ns.expect(ns.model('BatchTranslationRequest', {
        'input_texts': fields.List(fields.String, required=True, description='List of sentences to translate'),
    }))
    @ns.marshal_with(ns.model('BatchTranslationResponse', {
        'translations': fields.List(fields.String, description='List of translated texts'),
    }))
    def post(self, model):
        """
        Translate a batch of texts from the source language to the target language.
        The source and target languages are specified as query parameters `src` and `tgt`.
        The request body must include:
        - `input_texts`: A list of strings to translate.

        Example payload:
        ```
        {
            "input_texts": ["Hello, world!", "How are you?"],
        }
        ```
        """
        self.start_time_request()
        payload = ns.payload
        texts = payload['input_texts']
        translatable = TextBatch(texts)
        return self.process_translatable_models_endpoint(model, translatable, ns, log)

@ns.route(f'/<any{model_names}:model>/file')
@ns.param(**{'name': 'model', 'description': 'model name', 'x-example': 'en-cs', '_in': 'path'})
class ModelTranslateFile(MyAbstractResource):
    @ns.produces(FILE_TRANSLATE_MIMETYPES)
    @ns.response(code=200, description="Success")
    @ns.response(code=415, description="Unsupported file type for translation")
    @ns.param(**{'name': 'tgt', 'description': 'Target language (e.g., `cs` for Czech)', 'x-example': 'cs'})
    @ns.param(**{'name': 'src', 'description': 'Source language (e.g., `en` for English)', 'x-example': 'en'})
    @ns.expect(upload_parser)
    def post(self, model):
        """
        Send a file to be translated by the selected model.
        It expects the file in a variable called `input_file` sent using "multipart/form-data"
        If you don't provide src or tgt some will be chosen for you!
        """
        self.start_time_request()
        translatable = self.get_file_from_request()
        return self.process_translatable_models_endpoint(model, translatable, ns, log)
