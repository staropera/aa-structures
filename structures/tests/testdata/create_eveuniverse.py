from django.test import TestCase

from eveuniverse.tools.testdata import create_testdata, ModelSpec

from . import test_data_filename


class CreateEveUniverseTestData(TestCase):
    def test_create_testdata(self):
        testdata_spec = {
            "EveType": ModelSpec(ids=[35835, 35832], include_children=False,),
            "EveSolarSystem": ModelSpec(
                ids=[30002537, 30000474], include_children=False,
            ),
            "EveMoon": ModelSpec(ids=[40161465], include_children=False,),
        }
        create_testdata(testdata_spec, test_data_filename())
