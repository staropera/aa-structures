"""Eve Universe models"""

import logging
import urllib

from django.db import models
from django.utils.translation import gettext_lazy as _, gettext
from django.utils import translation
from django.utils.timezone import now

from .. import __title__
from ..managers import EveUniverseManager
from ..utils import LoggerAddTag

logger = LoggerAddTag(logging.getLogger(__name__), __title__)


class EsiNameLocalization(models.Model):
    """Base class for adding localization support for name field"""

    # language code mappings
    # Django, Eve Universe models, ESI
    LANG_CODES_MAPPING = (
        ('en', 'en', 'en-us'),
        ('de', 'de', 'de'),
        ('ko', 'ko', 'ko'),
        ('ru', 'ru', 'ru'),
        ('zh-hans', 'zh', 'zh'),
    )
    LANG_CODES_DJANGO = 0
    LANG_CODES_MODEL = 1
    LANG_CODES_ESI = 2

    ESI_LANGUAGES = {x[2] for x in LANG_CODES_MAPPING}
    ESI_DEFAULT_LANGUAGE = 'en-us'
    
    name_de = models.CharField(
        max_length=100,        
        blank=True,
        help_text=_('Eve Online name localized for German')
    )   
    name_ko = models.CharField(
        max_length=100,        
        blank=True,
        help_text=_('Eve Online name localized for Korean')
    )    
    name_ru = models.CharField(
        max_length=100,        
        blank=True,
        help_text=_('Eve Online name localized for Russian')
    )    
    name_zh = models.CharField(
        max_length=100,        
        blank=True,
        help_text=_('Eve Online name localized for Chinese')
    )

    @property
    def name_localized(self):
        """returns the localized version of name for the current language

        will return the default if a translation does not exist
        """
        return self.name_localized_for_language(translation.get_language())
        
    def name_localized_for_language(self, language: str):
        """returns the localized version of name for the given language
        
        will return the default if a translation does not exist
        """
        lang_mapping = self._language_code_translation(
            language, self.LANG_CODES_DJANGO
        )
        if lang_mapping and (
            lang_mapping[self.LANG_CODES_ESI] != self.ESI_DEFAULT_LANGUAGE
        ):
            field_ext = lang_mapping[self.LANG_CODES_MODEL]        
            field_name = ('name_%s' % field_ext) if field_ext else 'name'
        else:
            field_name = 'name'
        if not hasattr(self, field_name):
            raise NotImplementedError(
                'field name "%s" not found in %s' % (
                    field_name, type(self).__name__
                )
            )
        name_translation = getattr(self, field_name)
        return name_translation if name_translation else self.name

    def _name_localized_generated(self, lang_code: str) -> str:
        raise NotImplementedError()

    class Meta:
        abstract = True

    @classmethod
    def _language_code_translation(cls, code: str, category_from: int) -> tuple:
        """translates language codes between systems"""
        result = None
        for mapping in cls.LANG_CODES_MAPPING:
            if mapping[category_from] == code:
                result = mapping
        return result


class EveUniverse(EsiNameLocalization, models.Model):
    """Base class for all EveUniverse models
    
    Eve Universe classes need to have a meta class defined: `EveUniverseMeta`

    Properties are:

    esi_pk: Name of the ESI property for the primary key, e.g. 'category_id'

    esi_method: name of the ESI method to be called for fetching objects

    children: dict of mapping between ESI dict and model class for 
    children objects (e.g. planets for solar system), default is None
    
    fk_mappings: mapping of field names from model to ESI for FKs, 
    default is None
    
    field_mappings: mapping of field names from model to ESI for non FKs,
    default is None
    
    has_esi_localization: True/False, whether this model gets translations from ESI, 
    Default is True

    generate_localization: (optional) True/False, whether this model will 
    generate localizations by itself, default is false
    
    """

    id = models.PositiveIntegerField(
        primary_key=True, help_text=_('Eve Online ID')
    )
    name = models.CharField(
        max_length=100, help_text=_('Eve Online name')
    )    
    last_updated = models.DateTimeField(
        default=None,
        null=True,
        blank=True,
        help_text=_('When this object was last updated from ESI'),
        db_index=True
    )    

    objects = EveUniverseManager()

    def __repr__(self):
        return '{}(id={}, name=\'{}\')'.format(
            self.__class__.__name__,
            self.id,
            self.name
        )

    def __str__(self):
        return self.name
    
    def set_generated_translations(self):
        """updates localization fields with generated values if defined
        
        Purpose is to provide localized names for models where ESI does
        not provide localizations and where those names can be generated
        e.g. planets, moons
        
        Will look for _name_localized_generated() defined in the model
        and run it to set all localized names
        Does nothing if that method is not defined
        """
        if self._eve_universe_meta_attr('generate_localization'):            
            for django_lc, field_ext, esi_lc in self.LANG_CODES_MAPPING:
                if esi_lc != self.ESI_DEFAULT_LANGUAGE:
                    field_name = 'name_' + field_ext
                    setattr(
                        self, field_name, 
                        self._name_localized_generated(django_lc)
                    )
    
    class Meta:
        abstract = True

    @classmethod
    def esi_pk(cls) -> str:
        """returns the name of the pk column on ESI that must exist"""
        return cls._eve_universe_meta_attr('esi_pk', is_mandatory=True)
       
    @classmethod
    def esi_method(cls) -> str:        
        return cls._eve_universe_meta_attr('esi_method', is_mandatory=True)

    @classmethod
    def has_esi_localization(cls) -> bool:
        has_esi_localization = cls._eve_universe_meta_attr('has_esi_localization')
        return True if has_esi_localization is None else has_esi_localization
    
    @classmethod
    def child_mappings(cls) -> dict:
        """returns the mapping of children for this class"""
        mappings = cls._eve_universe_meta_attr('children')        
        return mappings if mappings else dict()

    @classmethod
    def _field_names_not_pk(cls) -> set:
        """returns field names excl. PK, localization and auto created fields"""
        return {
            x.name for x in cls._meta.get_fields()
            if not x.auto_created and (
                not hasattr(x, 'primary_key') or x.primary_key is False
            ) and x.name not in {'language_code', 'last_updated'}
            and 'name_' not in x.name
        }
    
    @classmethod
    def _field_mappings(cls) -> dict:
        """returns the mappings for model fields vs. esi fields"""        
        mappings = cls._eve_universe_meta_attr('field_mappings')
        return mappings if mappings else dict()

    @classmethod
    def _fk_mappings(cls) -> dict:
        """returns the foreign key mappings for this class
        
        'model field name': ('Foreign Key name on ESI', 'related model class')
        """
        
        def convert_to_esi_name(name: str, extra_fk_mappings: dict) -> str:            
            if name in extra_fk_mappings:
                esi_name = extra_fk_mappings[name]
            else:
                esi_name = name.replace('eve_', '') + '_id'
            return esi_name
        
        extra_fk_mappings = cls._eve_universe_meta_attr('fk_mappings')
        if not extra_fk_mappings:
            extra_fk_mappings = {}

        mappings = {
            x.name: (
                convert_to_esi_name(x.name, extra_fk_mappings), 
                x.related_model
            )
            for x in cls._meta.get_fields() 
            if isinstance(x, models.ForeignKey)
        }
        return mappings
        
    @classmethod
    def map_esi_fields_to_model(cls, eve_data_objects: dict) -> dict:
        """maps ESi fields to model fields incl. translations if any
        returns the result as defaults dict
        """
        fk_mappings = cls._fk_mappings()
        field_mappings = cls._field_mappings()                        
        defaults = {'last_updated': now()}
        eve_data_obj = eve_data_objects[cls.ESI_DEFAULT_LANGUAGE]
        for key in cls._field_names_not_pk():
            if key in fk_mappings:
                esi_key, ParentClass = fk_mappings[key]                    
                value, _ = ParentClass.objects.get_or_create_esi(
                    eve_data_obj[esi_key]
                )                
            else:
                if key in field_mappings:
                    mapping = field_mappings[key]
                    if len(mapping) != 2:
                        raise ValueError(
                            'Currently only supports mapping to 1-level '
                            'nested dicts'
                        )
                    value = eve_data_obj[mapping[0]][mapping[1]]
                else:
                    value = eve_data_obj[key]

            defaults[key] = value

        # add translations if any
        if cls.has_esi_localization():
            for _, field_ext, esi_lc in cls.LANG_CODES_MAPPING:
                if esi_lc != cls.ESI_DEFAULT_LANGUAGE:
                    field_name = 'name_' + field_ext
                    defaults[field_name] = \
                        eve_data_objects[esi_lc]['name']
        
        return defaults

    @classmethod
    def _eve_universe_meta_attr(
        cls, attr_name: str, is_mandatory: bool = False
    ):
        """returns value of an attribute from EveUniverseMeta or None"""
        if not hasattr(cls, 'EveUniverseMeta'):
            raise ValueError(
                'EveUniverseMeta not defined for class %s' % cls.__name__
            )
    
        if hasattr(cls.EveUniverseMeta, attr_name):
            value = getattr(cls.EveUniverseMeta, attr_name)
        else:
            value = None
            if is_mandatory:
                raise ValueError(
                    'Mandatory attribute EveUniverseMeta.%s not defined '
                    'for class %s' % (attr_name, cls.__name__)
                )
        return value


class EveCategory(EveUniverse):
    """group in Eve Online"""

    # named category IDs
    EVE_CATEGORY_ID_ORBITAL = 46
    EVE_CATEGORY_ID_STARBASE = 23
    EVE_CATEGORY_ID_STRUCTURE = 65

    @property
    def is_starbase(self):
        return self.id == self.EVE_CATEGORY_ID_STARBASE

    @property
    def is_upwell_structure(self):
        return self.id == self.EVE_CATEGORY_ID_STRUCTURE
    
    class EveUniverseMeta:
        esi_pk = 'category_id'
        esi_method = 'get_universe_categories_category_id'


class EveGroup(EveUniverse):
    """group in Eve Online"""
    
    eve_category = models.ForeignKey(
        EveCategory,
        on_delete=models.SET_DEFAULT,
        null=True,
        default=None,
        blank=True
    )

    class EveUniverseMeta:
        esi_pk = 'group_id'
        esi_method = 'get_universe_groups_group_id'


class EveType(EveUniverse):
    """type in Eve Online"""

    # named type IDs
    EVE_TYPE_ID_POCO = 2233
    EVE_TYPE_ID_TCU = 32226
    EVE_TYPE_ID_IHUB = 32458

    EVE_IMAGESERVER_BASE_URL = 'https://images.evetech.net'
    
    eve_group = models.ForeignKey(EveGroup, on_delete=models.CASCADE)

    class EveUniverseMeta:
        esi_pk = 'type_id'
        esi_method = 'get_universe_types_type_id'
    
    @property
    def is_poco(self):
        return self.id == self.EVE_TYPE_ID_POCO

    @property
    def is_starbase(self):
        return self.eve_group.eve_category.is_starbase

    @property
    def is_upwell_structure(self):
        return self.eve_group.eve_category.is_upwell_structure

    @classmethod
    def generic_icon_url(cls, type_id: int, size: int = 64) -> str:
        if size < 32 or size > 1024 or (size % 2 != 0):
            raise ValueError("Invalid size: {}".format(size))

        url = '{}/types/{}/icon'.format(
            cls.EVE_IMAGESERVER_BASE_URL,
            int(type_id)
        )
        if size:
            args = {'size': int(size)}
            url += '?{}'.format(urllib.parse.urlencode(args))

        return url

    def icon_url(self, size=64):
        return self.generic_icon_url(self.id, size)


class EveRegion(EveUniverse):
    """region in Eve Online"""
    
    class EveUniverseMeta:
        esi_pk = 'region_id'
        esi_method = 'get_universe_regions_region_id'
    

class EveConstellation(EveUniverse):
    """constellation in Eve Online"""

    eve_region = models.ForeignKey(EveRegion, on_delete=models.CASCADE)

    class EveUniverseMeta:
        esi_pk = 'constellation_id'
        esi_method = 'get_universe_constellations_constellation_id'


class EveSolarSystem(EveUniverse):
    """solar system in Eve Online"""
    
    eve_constellation = models.ForeignKey(
        EveConstellation,
        on_delete=models.CASCADE
    )
    security_status = models.FloatField()

    class EveUniverseMeta:
        esi_pk = 'system_id'
        esi_method = 'get_universe_systems_system_id'
        children = {
            'planets': 'EvePlanet'
        }


class EvePlanet(EveUniverse):
    """"planet in Eve Online"""
    
    position_x = models.FloatField(
        null=True,
        default=None,
        blank=True,
        help_text=_('x position in the solar system')
    )
    position_y = models.FloatField(
        null=True,
        default=None,
        blank=True,
        help_text=_('y position in the solar system')
    )
    position_z = models.FloatField(
        null=True,
        default=None,
        blank=True,
        help_text=_('z position in the solar system')
    )
    eve_solar_system = models.ForeignKey(
        EveSolarSystem,
        on_delete=models.CASCADE
    )
    eve_type = models.ForeignKey(
        EveType,
        on_delete=models.CASCADE
    )

    def _name_localized_generated(self, language: str) -> str:
        """returns a generated localized planet name for the given language"""
        name_localized = self.name.replace(
            self.eve_solar_system.name, 
            self.eve_solar_system.name_localized_for_language(language)
        )
        return name_localized

    class EveUniverseMeta:
        esi_pk = 'planet_id'
        esi_method = 'get_universe_planets_planet_id'
        fk_mappings = {
            'eve_solar_system': 'system_id'
        }
        field_mappings = {            
            'position_x': ('position', 'x'),
            'position_y': ('position', 'y'),
            'position_z': ('position', 'z')
        }
        has_esi_localization = False
        generate_localization = True


class EveMoon(EveUniverse):  
    """"moon in Eve Online"""

    position_x = models.FloatField(
        null=True,
        default=None,
        blank=True,
        help_text=_('x position in the solar system')
    )
    position_y = models.FloatField(
        null=True,
        default=None,
        blank=True,
        help_text=_('y position in the solar system')
    )
    position_z = models.FloatField(
        null=True,
        default=None,
        blank=True,
        help_text=_('z position in the solar system')
    )
    eve_solar_system = models.ForeignKey(
        EveSolarSystem,
        on_delete=models.CASCADE
    )

    def _name_localized_generated(self, language: str):
        """returns a generated localized moon name for the given language"""
        with translation.override(language):        
            name_localized = self.name.replace(
                self.eve_solar_system.name, 
                self.eve_solar_system.name_localized
            ).replace('Moon', gettext('Moon'))
        return name_localized

    class EveUniverseMeta:
        esi_pk = 'moon_id'
        esi_method = 'get_universe_moons_moon_id'
        fk_mappings = {
            'eve_solar_system': 'system_id'
        }
        field_mappings = {            
            'position_x': ('position', 'x'),
            'position_y': ('position', 'y'),
            'position_z': ('position', 'z')
        }
        has_esi_localization = False
        generate_localization = True
