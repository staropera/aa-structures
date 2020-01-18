from unittest.mock import Mock, patch

from django.test import TestCase

from allianceauth.eveonline.models \
    import EveCharacter, EveCorporationInfo, EveAllianceInfo

from . import set_logger
from ..models import *


logger = set_logger('structures.views', __file__)

# tbd