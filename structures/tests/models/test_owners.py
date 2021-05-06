from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import patch

from bravado.exception import HTTPBadGateway, HTTPInternalServerError

from django.test import override_settings
from django.utils.timezone import now, utc
from esi.errors import TokenExpiredError, TokenInvalidError

from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import (
    EveAllianceInfo,
    EveCharacter,
    EveCorporationInfo,
)
from allianceauth.tests.auth_utils import AuthUtils
from app_utils.django import app_labels
from app_utils.testing import BravadoResponseStub, NoSocketsTestCase, queryset_pks

from ...models import (
    EveCategory,
    EveConstellation,
    EveEntity,
    EveGroup,
    EveMoon,
    EvePlanet,
    EveRegion,
    EveSolarSystem,
    EveSovereigntyMap,
    EveType,
    Notification,
    Owner,
    OwnerAsset,
    Structure,
    StructureService,
    StructureTag,
    Webhook,
)
from ...models.notifications import NotificationType
from .. import to_json
from ..testdata import (
    create_structures,
    create_user,
    entities_testdata,
    esi_corp_structures_data,
    esi_data,
    esi_get_corporations_corporation_id_customs_offices,
    esi_get_corporations_corporation_id_starbases,
    esi_get_corporations_corporation_id_starbases_starbase_id,
    esi_get_corporations_corporation_id_structures,
    esi_get_universe_structures_structure_id,
    esi_mock_client,
    esi_post_corporations_corporation_id_assets_locations,
    esi_post_corporations_corporation_id_assets_names,
    load_entities,
    load_notification_entities,
    set_owner_character,
)
from ..testdata.load_eveuniverse import load_eveuniverse

if "timerboard" in app_labels():
    from allianceauth.timerboard.models import Timer as AuthTimer

    has_auth_timers = True

else:
    has_auth_timers = False


MODULE_PATH = "structures.models.owners"


class TestOwner(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([EveAllianceInfo, EveCorporationInfo, EveCharacter])

        for corporation in EveCorporationInfo.objects.all():
            EveEntity.objects.get_or_create(
                id=corporation.corporation_id,
                defaults={
                    "category": EveEntity.Category.CORPORATION,
                    "name": corporation.corporation_name,
                },
            )
            Owner.objects.create(corporation=corporation)
            if int(corporation.corporation_id) in [2001, 2002]:
                alliance = EveAllianceInfo.objects.get(alliance_id=3001)
                corporation.alliance = alliance
                corporation.save()

        for character in EveCharacter.objects.all():
            EveEntity.objects.get_or_create(
                id=character.character_id,
                defaults={
                    "category": EveEntity.Category.CHARACTER,
                    "name": character.character_name,
                },
            )
            corporation = EveCorporationInfo.objects.get(
                corporation_id=character.corporation_id
            )
            if corporation.alliance:
                character.alliance_id = corporation.alliance.alliance_id
                character.alliance_name = corporation.alliance.alliance_name
                character.save()

        set_owner_character(character_id=1001)

    def test_str(self):
        obj = Owner.objects.get(corporation__corporation_id=2001)
        self.assertEqual(str(obj), "Wayne Technologies")

    def test_repr(self):
        obj = Owner.objects.get(corporation__corporation_id=2001)
        expected = "Owner(pk=%d, corporation='Wayne Technologies')" % obj.pk
        self.assertEqual(repr(obj), expected)

    @patch(MODULE_PATH + ".STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES", 30)
    def test_is_structure_sync_ok(self):
        x = Owner.objects.get(corporation__corporation_id=2001)
        # no errors and recent sync
        x.structures_last_error = Owner.ERROR_NONE
        x.structures_last_sync = now()
        self.assertTrue(x.is_structure_sync_ok)

        # no errors and sync within grace period
        x.structures_last_error = Owner.ERROR_NONE
        x.structures_last_sync = now() - timedelta(minutes=29)
        self.assertTrue(x.is_structure_sync_ok)

        # recent sync error
        x.structures_last_error = Owner.ERROR_INSUFFICIENT_PERMISSIONS
        x.structures_last_sync = now()
        self.assertFalse(x.is_structure_sync_ok)

        # no error, but no sync within grace period
        x.structures_last_error = Owner.ERROR_NONE
        x.structures_last_sync = now() - timedelta(minutes=31)
        self.assertFalse(x.is_structure_sync_ok)

    @patch(MODULE_PATH + ".STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES", 30)
    def test_is_notification_sync_ok(self):
        x = Owner.objects.get(corporation__corporation_id=2001)
        # no errors and recent sync
        x.notifications_last_error = Owner.ERROR_NONE
        x.notifications_last_sync = now()
        self.assertTrue(x.is_notification_sync_ok)

        # no errors and sync within grace period
        x.notifications_last_error = Owner.ERROR_NONE
        x.notifications_last_sync = now() - timedelta(minutes=29)
        self.assertTrue(x.is_notification_sync_ok)

        # recent sync error
        x.notifications_last_error = Owner.ERROR_INSUFFICIENT_PERMISSIONS
        x.notifications_last_sync = now()
        self.assertFalse(x.is_notification_sync_ok)

        # no error, but no sync within grace period
        x.notifications_last_error = Owner.ERROR_NONE
        x.notifications_last_sync = now() - timedelta(minutes=31)
        self.assertFalse(x.is_notification_sync_ok)

    @patch(MODULE_PATH + ".STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES", 30)
    def test_is_forwarding_sync_ok(self):
        x = Owner.objects.get(corporation__corporation_id=2001)
        # no errors and recent sync
        x.forwarding_last_error = Owner.ERROR_NONE
        x.forwarding_last_sync = now()
        self.assertTrue(x.is_forwarding_sync_ok)

        # no errors and sync within grace period
        x.forwarding_last_error = Owner.ERROR_NONE
        x.forwarding_last_sync = now() - timedelta(minutes=29)
        self.assertTrue(x.is_forwarding_sync_ok)

        # recent sync error
        x.forwarding_last_error = Owner.ERROR_INSUFFICIENT_PERMISSIONS
        x.forwarding_last_sync = now()
        self.assertFalse(x.is_forwarding_sync_ok)

        # no error, but no sync within grace period
        x.forwarding_last_error = Owner.ERROR_NONE
        x.forwarding_last_sync = now() - timedelta(minutes=31)
        self.assertFalse(x.is_forwarding_sync_ok)

    @patch(MODULE_PATH + ".STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES", 30)
    @patch(MODULE_PATH + ".STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES", 30)
    @patch(MODULE_PATH + ".STRUCTURES_FORWARDING_SYNC_GRACE_MINUTES", 30)
    def test_is_all_syncs_ok(self):
        x = Owner.objects.get(corporation__corporation_id=2001)
        x.structures_last_error = Owner.ERROR_NONE
        x.structures_last_sync = now()
        x.notifications_last_error = Owner.ERROR_NONE
        x.notifications_last_sync = now()
        x.forwarding_last_error = Owner.ERROR_NONE
        x.forwarding_last_sync = now()
        self.assertTrue(x.are_all_syncs_ok)

    def test_to_friendly_error_message(self):
        # normal error
        self.assertEqual(
            Owner.to_friendly_error_message(Owner.ERROR_NO_CHARACTER),
            "No character set for fetching data from ESI",
        )
        # normal error
        self.assertEqual(Owner.to_friendly_error_message(0), "No error")
        # undefined error
        self.assertEqual(Owner.to_friendly_error_message(9876), "Undefined error")
        # undefined error
        self.assertEqual(Owner.to_friendly_error_message(-1), "Undefined error")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    def test_get_esi_scopes_pocos_off(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                "esi-corporations.read_structures.v1",
                "esi-universe.read_structures.v1",
                "esi-characters.read_notifications.v1",
                "esi-assets.read_corporation_assets.v1",
            },
        )

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    def test_get_esi_scopes_pocos_on(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                "esi-corporations.read_structures.v1",
                "esi-universe.read_structures.v1",
                "esi-characters.read_notifications.v1",
                "esi-planets.read_customs_offices.v1",
                "esi-assets.read_corporation_assets.v1",
            },
        )

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    def test_get_esi_scopes_starbases_on(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                "esi-corporations.read_structures.v1",
                "esi-universe.read_structures.v1",
                "esi-characters.read_notifications.v1",
                "esi-corporations.read_starbases.v1",
                "esi-assets.read_corporation_assets.v1",
            },
        )

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    def test_get_esi_scopes_starbases_and_custom_offices(self):
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            {
                "esi-corporations.read_structures.v1",
                "esi-universe.read_structures.v1",
                "esi-characters.read_notifications.v1",
                "esi-corporations.read_starbases.v1",
                "esi-planets.read_customs_offices.v1",
                "esi-assets.read_corporation_assets.v1",
            },
        )


@patch(MODULE_PATH + ".notify", spec=True)
@patch(MODULE_PATH + ".Token", spec=True)
@patch("structures.helpers.esi_fetch._esi_client")
@patch("structures.helpers.esi_fetch.sleep", lambda x: None)
class TestUpdateStructuresEsi(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # test data
        load_entities(
            [
                EveCategory,
                EveGroup,
                EveType,
                EveRegion,
                EveConstellation,
                EveSolarSystem,
                EveSovereigntyMap,
                EvePlanet,
                EveMoon,
                EveCorporationInfo,
                EveCharacter,
            ]
        )
        load_eveuniverse()
        # 1 user
        cls.character = EveCharacter.objects.get(character_id=1001)

        cls.corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        cls.user = AuthUtils.create_user(cls.character.character_name)
        cls.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", cls.user
        )

        cls.main_ownership = CharacterOwnership.objects.create(
            character=cls.character, owner_hash="x1", user=cls.user
        )
        Structure.objects.all().delete()

        # create StructureTag objects
        StructureTag.objects.all().delete()
        for x in entities_testdata["StructureTag"]:
            StructureTag.objects.create(**x)

    def setUp(self):
        # reset data that might be overridden
        esi_get_corporations_corporation_id_structures.override_data = None
        esi_get_corporations_corporation_id_customs_offices.override_data = None

    def test_returns_error_when_no_sync_char_defined(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        owner = Owner.objects.create(corporation=self.corporation)
        self.assertFalse(owner.update_structures_esi())
        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_NO_CHARACTER)

    def test_returns_error_when_char_has_no_permission(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        user_2 = create_user(1011)
        owner = Owner.objects.create(
            corporation=self.corporation, character=user_2.character_ownerships.first()
        )
        self.assertFalse(owner.update_structures_esi())
        owner.refresh_from_db()
        self.assertEqual(
            owner.structures_last_error, Owner.ERROR_INSUFFICIENT_PERMISSIONS
        )

    def test_returns_error_when_token_is_expired(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        mock_Token.objects.filter.side_effect = TokenExpiredError()
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )

        # run update task
        self.assertFalse(owner.update_structures_esi())

        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_TOKEN_EXPIRED)

    def test_returns_error_when_token_is_invalid(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        mock_Token.objects.filter.side_effect = TokenInvalidError()
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )

        # run update task
        self.assertFalse(owner.update_structures_esi())

        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_TOKEN_INVALID)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_can_sync_upwell_structures(self, mock_esi_client, mock_Token, mock_notify):
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_NONE)

        # must contain all expected structures
        structure_ids = {x["id"] for x in Structure.objects.values("id")}
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(structure_ids, expected)

        # verify attributes for structure
        structure = Structure.objects.get(id=1000000000001)
        self.assertEqual(structure.name, "Test Structure Alpha")
        self.assertEqual(structure.position_x, 55028384780.0)
        self.assertEqual(structure.position_y, 7310316270.0)
        self.assertEqual(structure.position_z, -163686684205.0)
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(structure.eve_type_id, 35832)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.state, Structure.State.SHIELD_VULNERABLE)
        self.assertEqual(structure.reinforce_hour, 18)
        self.assertEqual(
            structure.fuel_expires_at, datetime(2020, 3, 5, 5, 0, 0, tzinfo=utc)
        )
        self.assertEqual(
            structure.state_timer_start, datetime(2020, 4, 5, 6, 30, 0, tzinfo=utc)
        )
        self.assertEqual(
            structure.state_timer_end, datetime(2020, 4, 5, 7, 0, 0, tzinfo=utc)
        )
        self.assertEqual(
            structure.unanchors_at, datetime(2020, 5, 5, 6, 30, 0, tzinfo=utc)
        )

        # must have created services with localizations
        # structure 1000000000001
        expected = {
            to_json(
                {
                    "name": "Clone Bay",
                    "name_de": "Clone Bay_de",
                    "name_ko": "Clone Bay_ko",
                    "name_ru": "Clone Bay_ru",
                    # "name_zh": "Clone Bay_zh",
                    "state": StructureService.State.ONLINE,
                }
            ),
            to_json(
                {
                    "name": "Market Hub",
                    "name_de": "Market Hub_de",
                    "name_ko": "Market Hub_ko",
                    "name_ru": "Market Hub_ru",
                    # "name_zh": "Market Hub_zh",
                    "state": StructureService.State.OFFLINE,
                }
            ),
        }
        structure = Structure.objects.get(id=1000000000001)
        services = {
            to_json(
                {
                    "name": x.name,
                    "name_de": x.name_de,
                    "name_ko": x.name_ko,
                    "name_ru": x.name_ru,
                    # "name_zh": x.name_zh,
                    "state": x.state,
                }
            )
            for x in structure.services.all()
        }
        self.assertEqual(services, expected)

        # must have created services with localizations
        # structure 1000000000002
        expected = {
            to_json(
                {
                    "name": "Reprocessing",
                    "name_de": "Reprocessing_de",
                    "name_ko": "Reprocessing_ko",
                    "name_ru": "Reprocessing_ru",
                    # "name_zh": "Reprocessing_zh",
                    "state": StructureService.State.ONLINE,
                }
            ),
            to_json(
                {
                    "name": "Moon Drilling",
                    "name_de": "Moon Drilling_de",
                    "name_ko": "Moon Drilling_ko",
                    "name_ru": "Moon Drilling_ru",
                    # "name_zh": "Moon Drilling_zh",
                    "state": StructureService.State.ONLINE,
                }
            ),
        }
        structure = Structure.objects.get(id=1000000000002)
        services = {
            to_json(
                {
                    "name": x.name,
                    "name_de": x.name_de,
                    "name_ko": x.name_ko,
                    "name_ru": x.name_ru,
                    # "name_zh": x.name_zh,
                    "state": x.state,
                }
            )
            for x in structure.services.all()
        }
        self.assertEqual(services, expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_can_sync_pocos(self, mock_esi_client, mock_Token, mock_notify):
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_NONE)

        # must contain all expected structures
        structure_ids = {x["id"] for x in Structure.objects.values("id")}
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
        }
        self.assertSetEqual(structure_ids, expected)

        # verify attributes for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.name, "Planet (Barren)")
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 2233)
        self.assertEqual(structure.reinforce_hour, 20)
        self.assertEqual(structure.state, Structure.State.UNKNOWN)
        self.assertEqual(structure.eve_planet_id, 40161472)

        # structure = Structure.objects.get(id=1200000000006)
        # self.assertEqual(structure.name, "Planet (Barren)")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_can_sync_starbases(self, mock_esi_client, mock_Token, mock_notify):
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_NONE)

        # must contain all expected structures
        structure_ids = {x["id"] for x in Structure.objects.values("id")}
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(structure_ids, expected)

        # verify attributes for POS
        structure = Structure.objects.get(id=1300000000001)
        self.assertEqual(structure.name, "Home Sweat Home")
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 16213)
        self.assertEqual(structure.state, Structure.State.POS_ONLINE)
        self.assertEqual(structure.eve_moon_id, 40161465)
        self.assertEqual(
            structure.state_timer_end, datetime(2020, 4, 5, 7, 0, 0, tzinfo=utc)
        )
        self.assertGreaterEqual(
            structure.fuel_expires_at,
            now() + timedelta(hours=24) - timedelta(seconds=10),
        )
        self.assertLessEqual(
            structure.fuel_expires_at,
            now() + timedelta(hours=24) + timedelta(seconds=10),
        )

        structure = Structure.objects.get(id=1300000000002)
        self.assertEqual(structure.name, "Bat cave")
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 20061)
        self.assertEqual(structure.state, Structure.State.POS_OFFLINE)
        self.assertEqual(structure.eve_moon_id, 40161466)
        self.assertEqual(
            structure.unanchors_at, datetime(2020, 5, 5, 7, 0, 0, tzinfo=utc)
        )
        self.assertIsNone(structure.fuel_expires_at)

        structure = Structure.objects.get(id=1300000000003)
        self.assertEqual(structure.name, "Panic Room")
        self.assertEqual(structure.eve_solar_system_id, 30000474)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 20062)
        self.assertEqual(structure.state, Structure.State.POS_ONLINE)
        self.assertEqual(structure.eve_moon_id, 40029527)
        self.assertGreaterEqual(
            structure.fuel_expires_at,
            now() + timedelta(hours=133) - timedelta(seconds=10),
        )
        self.assertLessEqual(
            structure.fuel_expires_at,
            now() + timedelta(hours=133) + timedelta(seconds=10),
        )

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_can_sync_all_structures(self, mock_esi_client, mock_Token, mock_notify):
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_NONE)

        # must contain all expected structures
        structure_ids = {x["id"] for x in Structure.objects.values("id")}
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(structure_ids, expected)

        # user report has been sent
        self.assertTrue(mock_notify.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_can_handle_owner_without_structures(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        mock_esi_client.side_effect = esi_mock_client

        my_character = EveCharacter.objects.get(character_id=1005)
        my_corporation = EveCorporationInfo.objects.get(corporation_id=2005)
        my_user = AuthUtils.create_user(my_character.character_name)
        AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", my_user
        )
        my_main_ownership = CharacterOwnership.objects.create(
            character=my_character, owner_hash="x1123456", user=my_user
        )
        owner = Owner.objects.create(
            corporation=my_corporation, character=my_main_ownership
        )
        # run update task
        self.assertTrue(owner.update_structures_esi(user=my_user))
        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_NONE)

        # must contain all expected structures
        structure_ids = {x["id"] for x in Structure.objects.values("id")}
        expected = set()
        self.assertSetEqual(structure_ids, expected)

        # user report has been sent
        self.assertTrue(mock_notify.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_will_not_break_on_http_error_when_fetching_upwell_structures(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        # create our own esi_client
        mock_esi_client.return_value.Assets.post_corporations_corporation_id_assets_locations = (
            esi_post_corporations_corporation_id_assets_locations
        )
        mock_esi_client.return_value.Assets.post_corporations_corporation_id_assets_names = (
            esi_post_corporations_corporation_id_assets_names
        )
        mock_esi_client.return_value.Planetary_Interaction.get_corporations_corporation_id_customs_offices = (
            esi_get_corporations_corporation_id_customs_offices
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_structures.side_effect = HTTPInternalServerError(
            BravadoResponseStub(status_code=500, reason="Test")
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_starbases.side_effect = (
            esi_get_corporations_corporation_id_starbases
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_starbases_starbase_id.side_effect = (
            esi_get_corporations_corporation_id_starbases_starbase_id
        )
        mock_esi_client.return_value.Universe.get_universe_structures_structure_id.side_effect = (
            esi_get_universe_structures_structure_id
        )

        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_NONE)

        # must contain all expected structures
        structure_ids = {x["id"] for x in Structure.objects.values("id")}
        expected = {
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(structure_ids, expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_will_not_break_on_http_error_when_fetching_custom_offices(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        # create our own esi_client
        mock_esi_client.return_value.Assets.post_corporations_corporation_id_assets_locations = (
            esi_post_corporations_corporation_id_assets_locations
        )
        mock_esi_client.return_value.Assets.post_corporations_corporation_id_assets_names = (
            esi_post_corporations_corporation_id_assets_names
        )
        mock_esi_client.return_value.Planetary_Interaction.get_corporations_corporation_id_customs_offices.side_effect = HTTPInternalServerError(
            BravadoResponseStub(status_code=500, reason="Test")
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_structures.side_effect = (
            esi_get_corporations_corporation_id_structures
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_starbases.side_effect = (
            esi_get_corporations_corporation_id_starbases
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_starbases_starbase_id.side_effect = (
            esi_get_corporations_corporation_id_starbases_starbase_id
        )
        mock_esi_client.return_value.Universe.get_universe_structures_structure_id.side_effect = (
            esi_get_universe_structures_structure_id
        )

        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_NONE)

        # must contain all expected structures
        structure_ids = {x["id"] for x in Structure.objects.values("id")}
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(structure_ids, expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_will_not_break_on_http_error_when_fetching_star_bases(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        # create our own esi_client
        mock_esi_client.return_value.Assets.post_corporations_corporation_id_assets_locations = (
            esi_post_corporations_corporation_id_assets_locations
        )
        mock_esi_client.return_value.Assets.post_corporations_corporation_id_assets_names = (
            esi_post_corporations_corporation_id_assets_names
        )
        mock_esi_client.return_value.Planetary_Interaction.get_corporations_corporation_id_customs_offices = (
            esi_get_corporations_corporation_id_customs_offices
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_structures.side_effect = (
            esi_get_corporations_corporation_id_structures
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_starbases.side_effect = HTTPInternalServerError(
            BravadoResponseStub(status_code=500, reason="Test")
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_starbases_starbase_id.side_effect = (
            esi_get_corporations_corporation_id_starbases_starbase_id
        )
        mock_esi_client.return_value.Universe.get_universe_structures_structure_id.side_effect = (
            esi_get_universe_structures_structure_id
        )

        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_NONE)

        # must contain all expected structures
        structure_ids = {x["id"] for x in Structure.objects.values("id")}
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
        }
        self.assertSetEqual(structure_ids, expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_update_will_not_break_on_http_error_from_structure_info(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        mock_esi_client.side_effect = esi_mock_client
        # remove info data for structure with ID 1000000000002
        data = deepcopy(esi_data["Universe"]["get_universe_structures_structure_id"])
        del data["1000000000002"]
        esi_get_universe_structures_structure_id.override_data = data
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        self.assertTrue(owner.update_structures_esi())
        esi_get_universe_structures_structure_id.override_data = None

        structure = Structure.objects.get(id=1000000000002)
        self.assertEqual(structure.name, "(no data)")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_removes_old_structures(self, mock_esi_client, mock_Token, mock_notify):
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )

        # run update task with all structures
        owner.update_structures_esi()

        # should contain the right structures
        structure_ids = {x["id"] for x in Structure.objects.values("id")}
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(structure_ids, expected)

        # run update task 2nd time with one less structure
        my_corp_structures_data = deepcopy(esi_corp_structures_data)
        del my_corp_structures_data["2001"][1]
        esi_get_corporations_corporation_id_structures.override_data = (
            my_corp_structures_data
        )
        owner.update_structures_esi()

        # should contain only the remaining structures
        structure_ids = {x["id"] for x in Structure.objects.values("id")}
        expected = {1000000000002, 1000000000003}
        self.assertSetEqual(structure_ids, expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_tags_are_not_modified_by_update(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )

        # run update task with all structures
        owner.update_structures_esi()
        # should contain the right structures
        structure_ids = {x["id"] for x in Structure.objects.values("id")}
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(structure_ids, expected)

        # adding tags
        tag_a = StructureTag.objects.get(name="tag_a")
        s = Structure.objects.get(id=1000000000001)
        s.tags.add(tag_a)
        s.save()

        # run update task 2nd time
        owner.update_structures_esi()

        # should still contain alls structures
        structure_ids = {x["id"] for x in Structure.objects.values("id")}
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(structure_ids, expected)

        # should still contain the tag
        s_new = Structure.objects.get(id=1000000000001)
        self.assertEqual(s_new.tags.get(name="tag_a"), tag_a)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_only_remove_structures_not_returned_from_esi(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        esi_get_corporations_corporation_id_structures.override_data = {"2001": []}
        mock_esi_client.side_effect = esi_mock_client
        create_structures(dont_load_entities=True)
        owner = Owner.objects.get(corporation__corporation_id=2001)
        owner.character = self.main_ownership
        self.assertGreater(owner.structures.count(), 0)

        # run update task
        self.assertTrue(owner.update_structures_esi())
        owner.refresh_from_db()
        self.assertEqual(owner.structures_last_error, Owner.ERROR_NONE)
        # must be empty
        self.assertEqual(owner.structures.count(), 0)

    @patch(MODULE_PATH + ".settings.DEBUG", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_reports_error_to_user_when_update_fails(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        esi_get_corporations_corporation_id_structures.override_data = {"2001": []}
        esi_get_corporations_corporation_id_customs_offices.override_data = {"2001": []}
        mock_esi_client.side_effect = esi_mock_client
        mock_notify.side_effect = RuntimeError
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )

        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_removes_outdated_services(self, mock_esi_client, mock_Token, mock_notify):
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )

        # run update task with all structures
        owner.update_structures_esi(user=self.user)
        structure = Structure.objects.get(id=1000000000002)
        self.assertEqual(
            {x.name for x in StructureService.objects.filter(structure=structure)},
            {"Reprocessing", "Moon Drilling"},
        )

        # run update task 2nd time after removing a service
        my_corp_structures_data = deepcopy(esi_corp_structures_data)
        del my_corp_structures_data["2001"][0]["services"][0]
        esi_get_corporations_corporation_id_structures.override_data = (
            my_corp_structures_data
        )
        owner.update_structures_esi(user=self.user)
        # should contain only the remaining service
        structure.refresh_from_db()
        self.assertEqual(
            {x.name for x in StructureService.objects.filter(structure=structure)},
            {"Moon Drilling"},
        )

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_have_empty_name_if_not_match_with_planets(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        EvePlanet.objects.all().delete()
        # when
        result = owner.update_structures_esi(user=self.user)
        # then
        self.assertTrue(result)
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.name, "")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_define_poco_name_from_planet_type_if_found(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))

        # check name for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.eve_planet_id, 40161472)
        self.assertEqual(structure.name, "Planet (Barren)")

    @patch(MODULE_PATH + ".STRUCTURES_DEFAULT_LANGUAGE", "de")
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_define_poco_name_from_planet_type_localized(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))

        # check name for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.eve_planet_id, 40161472)
        self.assertEqual(structure.name, "Planet (Barren)_de")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_update_pocos_no_asset_name_match(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        esi_post_corporations_corporation_id_assets_names.override_data = {"2001": []}
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )
        EvePlanet.objects.all().delete()

        # run update task
        self.assertTrue(owner.update_structures_esi(user=self.user))
        # check name for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.name, "")
        esi_post_corporations_corporation_id_assets_names.override_data = None

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    @patch(MODULE_PATH + ".Structure.objects.update_or_create_from_dict")
    def test_reports_error_during_storing(
        self, mock_update_or_create_from_dict, mock_esi_client, mock_Token, mock_notify
    ):
        mock_esi_client.side_effect = esi_mock_client
        mock_update_or_create_from_dict.side_effect = RuntimeError

        # create test data
        owner = Owner.objects.create(
            corporation=self.corporation, character=self.main_ownership
        )

        # run update task with all structures
        self.assertFalse(owner.update_structures_esi())


class TestUpdateStructuresEsiWithLocalization(NoSocketsTestCase):
    def setUp(self):
        self.default_lang = "en-us"
        self.structures_w_lang = {
            "en-us": [
                {
                    "structure_id": 1001,
                    "services": [
                        {"name": "alpha", "state": "online"},
                        {"name": "bravo", "state": "online"},
                    ],
                },
                {
                    "structure_id": 1002,
                    "services": [{"name": "bravo", "state": "offline"}],
                },
            ],
            "ko": [
                {
                    "structure_id": 1001,
                    "services": [
                        {"name": "alpha_ko", "state": "online"},
                        {"name": "bravo_ko", "state": "online"},
                    ],
                },
                {
                    "structure_id": 1002,
                    "services": [{"name": "bravo_ko", "state": "offline"}],
                },
            ],
            "de": [
                {
                    "structure_id": 1001,
                    "services": [
                        {"name": "alpha_de", "state": "online"},
                        {"name": "bravo_de", "state": "online"},
                    ],
                },
                {
                    "structure_id": 1002,
                    "services": [{"name": "bravo_de", "state": "offline"}],
                },
            ],
        }

    def test_collect_services_with_localizations(self):
        structures_services = Owner._collect_services_with_localizations(
            self.structures_w_lang, self.default_lang
        )
        expected = {
            1001: {"de": ["alpha_de", "bravo_de"], "ko": ["alpha_ko", "bravo_ko"]},
            1002: {"de": ["bravo_de"], "ko": ["bravo_ko"]},
        }
        self.maxDiff = None
        self.assertEqual(to_json(structures_services), to_json(expected))

    def test_condense_services_localizations_into_structures(self):
        structures_services = {
            1001: {"de": ["alpha_de", "bravo_de"], "ko": ["alpha_ko", "bravo_ko"]},
            1002: {"de": ["bravo_de"], "ko": ["bravo_ko"]},
        }
        structures = Owner._condense_services_localizations_into_structures(
            self.structures_w_lang, self.default_lang, structures_services
        )
        excepted = [
            {
                "structure_id": 1001,
                "services": [
                    {
                        "name": "alpha",
                        "name_de": "alpha_de",
                        "name_ko": "alpha_ko",
                        "state": "online",
                    },
                    {
                        "name": "bravo",
                        "name_de": "bravo_de",
                        "name_ko": "bravo_ko",
                        "state": "online",
                    },
                ],
            },
            {
                "structure_id": 1002,
                "services": [
                    {
                        "name": "bravo",
                        "name_de": "bravo_de",
                        "name_ko": "bravo_ko",
                        "state": "offline",
                    }
                ],
            },
        ]
        self.maxDiff = None
        self.assertEqual(to_json(structures), to_json(excepted))

    def test_condense_services_localizations_into_structures_2(self):
        structures_services = {
            1001: {"de": ["alpha_de", "bravo_de"]},
            1002: {"de": ["bravo_de"]},
        }
        structures = Owner._condense_services_localizations_into_structures(
            self.structures_w_lang, self.default_lang, structures_services
        )
        excepted = [
            {
                "structure_id": 1001,
                "services": [
                    {"name": "alpha", "name_de": "alpha_de", "state": "online"},
                    {"name": "bravo", "name_de": "bravo_de", "state": "online"},
                ],
            },
            {
                "structure_id": 1002,
                "services": [
                    {"name": "bravo", "name_de": "bravo_de", "state": "offline"}
                ],
            },
        ]
        self.maxDiff = None
        self.assertEqual(to_json(structures), to_json(excepted))


class TestFetchNotificationsEsi(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        cls.owner.is_alliance_main = True
        cls.owner.save()

    def setUp(self) -> None:
        if has_auth_timers:
            AuthTimer.objects.all().delete()

    def test_report_error_when_run_without_char(self):
        my_owner = Owner.objects.get(corporation__corporation_id=2002)
        self.assertFalse(my_owner.fetch_notifications_esi())
        my_owner.refresh_from_db()
        self.assertEqual(my_owner.notifications_last_error, Owner.ERROR_NO_CHARACTER)

    @patch(MODULE_PATH + ".Token")
    def test_report_error_when_run_with_expired_token(self, mock_Token):
        # given
        mock_Token.objects.filter.side_effect = TokenExpiredError()
        AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        # when
        result = self.owner.fetch_notifications_esi()
        # then
        self.assertFalse(result)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.notifications_last_error, Owner.ERROR_TOKEN_EXPIRED)

    # test invalid token
    @patch(MODULE_PATH + ".Token")
    def test_report_error_when_run_with_invalid_token(self, mock_Token):
        # given
        mock_Token.objects.filter.side_effect = TokenInvalidError()
        AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        # when
        result = self.owner.fetch_notifications_esi()
        # then
        self.assertFalse(result)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.notifications_last_error, Owner.ERROR_TOKEN_INVALID)

    @patch(
        "structures.models.notifications.STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED",
        False,
    )
    @patch(MODULE_PATH + ".STRUCTURES_ADD_TIMERS", True)
    @patch(MODULE_PATH + ".notify", spec=True)
    @patch(MODULE_PATH + ".Token", spec=True)
    @patch("structures.helpers.esi_fetch._esi_client")
    def test_should_create_notifications_and_timers_from_scratch(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        self.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        # when
        if "structuretimers" in app_labels():
            from ..testdata.load_eveuniverse import load_eveuniverse

            load_eveuniverse()
            with patch(
                "structuretimers.models.STRUCTURETIMERS_NOTIFICATIONS_ENABLED", False
            ):
                result = self.owner.fetch_notifications_esi(user=self.user)
        else:
            result = self.owner.fetch_notifications_esi(user=self.user)

        # then
        self.assertTrue(result)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.notifications_last_error, Owner.ERROR_NONE)
        # should only contain the right notifications
        notif_ids_current = set(
            Notification.objects.values_list("notification_id", flat=True)
        )
        notif_ids_testdata = {
            x["notification_id"] for x in entities_testdata["Notification"]
        }
        self.assertSetEqual(notif_ids_current, notif_ids_testdata)
        # user report has been sent
        self.assertTrue(mock_notify.called)

        if has_auth_timers:
            # should have added timers
            self.assertEqual(AuthTimer.objects.count(), 4)

            # run sync again
            self.assertTrue(self.owner.fetch_notifications_esi())

            # should not have more timers
            self.assertEqual(AuthTimer.objects.count(), 4)

    @patch(
        "structures.models.notifications.STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED",
        False,
    )
    @patch(MODULE_PATH + ".STRUCTURES_ADD_TIMERS", True)
    @patch(MODULE_PATH + ".notify", spec=True)
    @patch(MODULE_PATH + ".Token", spec=True)
    @patch("structures.helpers.esi_fetch._esi_client")
    def test_should_create_new_notifications_only(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        self.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        load_notification_entities(self.owner)
        Notification.objects.get(notification_id=1000000803).delete()
        Notification.objects.all().update(created=None)
        # when
        if "structuretimers" in app_labels():
            from ..testdata.load_eveuniverse import load_eveuniverse

            load_eveuniverse()
            with patch(
                "structuretimers.models.STRUCTURETIMERS_NOTIFICATIONS_ENABLED", False
            ):
                result = self.owner.fetch_notifications_esi(user=self.user)
        else:
            result = self.owner.fetch_notifications_esi(user=self.user)
        # then
        self.assertTrue(result)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.notifications_last_error, Owner.ERROR_NONE)
        # should only contain the right notifications
        notif_ids_current = set(
            Notification.objects.values_list("notification_id", flat=True)
        )
        notif_ids_testdata = {
            x["notification_id"] for x in entities_testdata["Notification"]
        }
        self.assertSetEqual(notif_ids_current, notif_ids_testdata)
        # should only have created one notification
        created_ids = set(
            Notification.objects.filter(created__isnull=False).values_list(
                "notification_id", flat=True
            )
        )
        self.assertSetEqual(created_ids, {1000000803})

    @patch(
        "structures.models.notifications.STRUCTURES_MOON_EXTRACTION_TIMERS_ENABLED",
        False,
    )
    @patch(MODULE_PATH + ".STRUCTURES_ADD_TIMERS", False)
    @patch(MODULE_PATH + ".notify", spec=True)
    @patch(MODULE_PATH + ".Token", spec=True)
    @patch("structures.helpers.esi_fetch._esi_client")
    def test_should_set_moon_for_structure_if_missing(
        self, mock_esi_client, mock_Token, mock_notify
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        self.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        load_notification_entities(self.owner)
        Notification.objects.get(notification_id=1000000803).delete()
        Notification.objects.all().update(created=None)
        # when
        if "structuretimers" in app_labels():
            from ..testdata.load_eveuniverse import load_eveuniverse

            load_eveuniverse()
            with patch(
                "structuretimers.models.STRUCTURETIMERS_NOTIFICATIONS_ENABLED", False
            ):
                result = self.owner.fetch_notifications_esi(user=self.user)
        else:
            result = self.owner.fetch_notifications_esi(user=self.user)
        # then
        self.assertTrue(result)
        structure = Structure.objects.get(id=1000000000002)
        self.assertEqual(structure.eve_moon, EveMoon.objects.get(id=40161465))

    @patch("structures.helpers.esi_fetch.ESI_RETRY_SLEEP_SECS", 0)
    @patch(MODULE_PATH + ".STRUCTURES_ADD_TIMERS", False)
    @patch(MODULE_PATH + ".Token", spec=True)
    @patch("structures.helpers.esi_fetch._esi_client")
    def test_report_error_when_esi_returns_error_during_sync(
        self, mock_esi_client, mock_Token
    ):
        # given
        def get_characters_character_id_notifications_error(*args, **kwargs):
            raise HTTPBadGateway(
                BravadoResponseStub(status_code=502, reason="Test Exception")
            )

        mock_esi_client.return_value.Character.get_characters_character_id_notifications.side_effect = (
            get_characters_character_id_notifications_error
        )
        AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        # when
        result = self.owner.fetch_notifications_esi()
        # then
        self.assertFalse(result)
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.notifications_last_error, Owner.ERROR_UNKNOWN)


@override_settings(DEBUG=True)
@patch("structures.models.notifications.Webhook.send_message", spec=True)
@patch(MODULE_PATH + ".Token", spec=True)
@patch("structures.helpers.esi_fetch._esi_client")
class TestSendNewNotifications1(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        cls.owner.is_alliance_main = True
        cls.owner.save()
        load_notification_entities(cls.owner)
        my_webhook = Webhook.objects.create(
            name="Dummy",
            url="dummy-url",
            is_active=True,
            notification_types=NotificationType.values,
        )
        cls.owner.webhooks.add(my_webhook)

    def test_should_send_all_notifications(
        self, mock_esi_client_factory, mock_token, mock_send_message
    ):
        # given
        mock_send_message.return_value = True
        self.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        # when
        result = self.owner.send_new_notifications()
        # then
        self.assertTrue(result)
        notifications_processed = {
            int(args[1]["embeds"][0].footer.text[-10:])
            for args in mock_send_message.call_args_list
        }
        notifications_expected = set(
            self.owner.notifications.filter(
                notif_type__in=NotificationType.values
            ).values_list("notification_id", flat=True)
        )
        self.assertSetEqual(notifications_processed, notifications_expected)

    def test_should_send_all_notifications_corp(
        self, mock_esi_client_factory, mock_token, mock_send_message
    ):
        # given
        mock_send_message.return_value = True
        user, owner = set_owner_character(character_id=1011)
        load_notification_entities(owner)
        owner.is_alliance_main = True
        owner.save()
        user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", user
        )
        # when
        result = owner.send_new_notifications()
        # then
        self.assertTrue(result)
        notifications_processed = {
            int(args[1]["embeds"][0].footer.text[-10:])
            for args in mock_send_message.call_args_list
        }
        notifications_expected = set(
            owner.notifications.filter(
                notif_type__in=NotificationType.values
            ).values_list("notification_id", flat=True)
        )
        self.assertSetEqual(notifications_processed, notifications_expected)

    def test_should_only_send_selected_notification_types(
        self, mock_esi_client_factory, mock_token, mock_send_message
    ):
        # given
        mock_send_message.return_value = True
        self.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        webhook = Webhook.objects.create(
            name="Webhook 1",
            url="dummy-url-1",
            notification_types=[
                NotificationType.ORBITAL_ATTACKED,
                NotificationType.STRUCTURE_DESTROYED,
            ],
            is_active=True,
        )
        self.owner.webhooks.clear()
        self.owner.webhooks.add(webhook)
        # when
        result = self.owner.send_new_notifications()
        # then
        self.assertTrue(result)
        notifications_processed = {
            int(args[1]["embeds"][0].footer.text[-10:])
            for args in mock_send_message.call_args_list
        }
        notifications_expected = set(
            Notification.objects.filter(
                notif_type__in=[
                    NotificationType.ORBITAL_ATTACKED,
                    NotificationType.STRUCTURE_DESTROYED,
                ]
            ).values_list("notification_id", flat=True)
        )
        self.assertSetEqual(notifications_processed, notifications_expected)


class TestSendNewNotifications2(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        cls.owner.is_alliance_main = True
        cls.owner.save()
        load_notification_entities(cls.owner)
        my_webhook = Webhook.objects.create(
            name="Dummy",
            url="dummy-url",
            is_active=True,
            notification_types=NotificationType.values,
        )
        cls.owner.webhooks.add(my_webhook)

    @staticmethod
    def my_send_to_webhook_success(self, webhook):
        """simulates successful sending of a notification"""
        self.is_sent = True
        self.save()
        return True

    @patch(MODULE_PATH + ".Token", spec=True)
    @patch("structures.helpers.esi_fetch._esi_client")
    @patch(
        "structures.models.notifications.Notification.send_to_webhook", autospec=True
    )
    def test_should_send_notifications_to_multiple_webhooks_but_same_owner(
        self, mock_send_to_webhook, mock_esi_client_factory, mock_token
    ):
        # given
        mock_send_to_webhook.side_effect = self.my_send_to_webhook_success
        self.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", self.user
        )
        webhook_1 = Webhook.objects.create(
            name="Webhook 1",
            url="dummy-url-1",
            notification_types=[
                NotificationType.ORBITAL_ATTACKED,
                NotificationType.ORBITAL_REINFORCED,
            ],
            is_active=True,
        )
        webhook_2 = Webhook.objects.create(
            name="Webhook 2",
            url="dummy-url-2",
            notification_types=[
                NotificationType.STRUCTURE_DESTROYED,
                NotificationType.STRUCTURE_FUEL_ALERT,
            ],
            is_active=True,
        )
        self.owner.webhooks.clear()
        self.owner.webhooks.add(webhook_1)
        self.owner.webhooks.add(webhook_2)
        # when
        result = self.owner.send_new_notifications()
        # then
        self.assertTrue(result)
        notifications_per_webhook = {webhook_1.pk: set(), webhook_2.pk: set()}
        for x in mock_send_to_webhook.call_args_list:
            first = x[0]
            notification = first[0]
            hook = first[1]
            notifications_per_webhook[hook.pk].add(notification.notification_id)
        expected = {
            webhook_1.pk: set(
                Notification.objects.filter(
                    notif_type__in=[
                        NotificationType.ORBITAL_ATTACKED,
                        NotificationType.ORBITAL_REINFORCED,
                    ]
                ).values_list("notification_id", flat=True)
            ),
            webhook_2.pk: set(
                Notification.objects.filter(
                    notif_type__in=[
                        NotificationType.STRUCTURE_DESTROYED,
                        NotificationType.STRUCTURE_FUEL_ALERT,
                    ]
                ).values_list("notification_id", flat=True)
            ),
        }
        self.assertDictEqual(notifications_per_webhook, expected)

    # @patch(MODULE_PATH + ".Token", spec=True)
    # @patch("structures.helpers.esi_fetch._esi_client")
    # @patch(
    #     "structures.models.notifications.Notification.send_to_webhook", autospec=True
    # )
    # def test_can_send_notifications_to_multiple_owners(
    #     self, mock_send_to_webhook, mock_esi_client_factory, mock_token
    # ):
    #     mock_send_to_webhook.side_effect = self.my_send_to_webhook_success
    #     AuthUtils.add_permission_to_user_by_name(
    #         "structures.add_structure_owner", self.user
    #     )
    #     notification_groups_1 = ",".join(
    #         [str(x) for x in sorted([NotificationGroup.CUSTOMS_OFFICE])]
    #     )
    #     wh_structures = Webhook.objects.create(
    #         name="Structures",
    #         url="dummy-url-1",
    #         notification_types=notification_groups_1,
    #         is_active=True,
    #     )
    #     notification_groups_2 = ",".join(
    #         [str(x) for x in sorted([NotificationGroup.STARBASE])]
    #     )
    #     wh_mining = Webhook.objects.create(
    #         name="Mining",
    #         url="dummy-url-2",
    #         notification_types=notification_groups_2,
    #         is_default=True,
    #         is_active=True,
    #     )

    #     self.owner.webhooks.clear()
    #     self.owner.webhooks.add(wh_structures)
    #     self.owner.webhooks.add(wh_mining)

    #     owner2 = Owner.objects.get(corporation__corporation_id=2002)
    #     owner2.webhooks.add(wh_structures)
    #     owner2.webhooks.add(wh_mining)

    #     # move most mining notification to 2nd owner
    #     notifications = Notification.objects.filter(
    #         notification_id__in=[1000000401, 1000000403, 1000000404, 1000000405]
    #     )
    #     for x in notifications:
    #         x.owner = owner2
    #         x.save()

    #     # send notifications for 1st owner only
    #     self.assertTrue(self.owner.send_new_notifications())
    #     results = {wh_mining.pk: set(), wh_structures.pk: set()}
    #     for x in mock_send_to_webhook.call_args_list:
    #         first = x[0]
    #         notification = first[0]
    #         hook = first[1]
    #         results[hook.pk].add(notification.notification_id)

    #     # structure notifications should have been sent
    #     self.assertSetEqual(
    #         results[wh_structures.pk],
    #         {1000000402, 1000000502, 1000000504, 1000000505, 1000000509, 1000010509},
    #     )
    #     # but mining notifications should NOT have been sent
    #     self.assertSetEqual(results[wh_mining.pk], {1000000402})

    @patch(MODULE_PATH + ".Owner._send_notifications_to_webhook", spec=True)
    def test_reports_unexpected_error(self, mock_send):
        mock_send.side_effect = RuntimeError()
        self.assertFalse(self.owner.send_new_notifications())
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.forwarding_last_error, Owner.ERROR_UNKNOWN)


@patch(MODULE_PATH + ".notify", spec=True)
@patch(MODULE_PATH + ".Token", spec=True)
@patch("structures.helpers.esi_fetch._esi_client")
@patch("structures.helpers.esi_fetch.sleep", lambda x: None)
class TestOwnerUpdateAssetEsi(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_structures()
        cls.user, cls.owner = set_owner_character(character_id=1001)
        cls.user = AuthUtils.add_permission_to_user_by_name(
            "structures.add_structure_owner", cls.user
        )

    def test_should_assets_for_owner(self, mock_esi_client, mock_Token, mock_notify):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.get(corporation__corporation_id=2001)
        # when
        owner.update_asset_esi()
        # then
        self.assertSetEqual(
            queryset_pks(OwnerAsset.objects.all()),
            {1300000001001, 1300000001002, 1300000002001},
        )
        self.assertEqual(owner.assets_last_error, Owner.ERROR_NONE)
        self.assertTrue(owner.assets_last_sync)

    # TODO: Add tests for error cases
