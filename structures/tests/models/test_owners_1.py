from copy import deepcopy
from datetime import datetime, timedelta
from unittest.mock import patch

from bravado.exception import HTTPInternalServerError

from django.utils.timezone import now, utc
from esi.errors import TokenError
from esi.models import Token

from allianceauth.eveonline.models import (
    EveAllianceInfo,
    EveCharacter,
    EveCorporationInfo,
)
from app_utils.testing import (
    BravadoResponseStub,
    NoSocketsTestCase,
    create_user_from_evecharacter,
)

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
    Owner,
    PocoDetails,
    Structure,
    StructureService,
    StructureTag,
)
from .. import to_json
from ..testdata import (
    create_structures,
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
    set_owner_character,
)
from ..testdata.load_eveuniverse import load_eveuniverse

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
        x.structures_last_update_ok = True
        x.structures_last_update_at = now()
        self.assertTrue(x.is_structure_sync_ok)

        # no errors and sync within grace period
        x.structures_last_update_ok = True
        x.structures_last_update_at = now() - timedelta(minutes=29)
        self.assertTrue(x.is_structure_sync_ok)

        # recent sync error
        x.structures_last_update_ok = None
        x.structures_last_update_at = now()
        self.assertFalse(x.is_structure_sync_ok)

        # recent sync error
        x.structures_last_update_ok = False
        x.structures_last_update_at = now()
        self.assertFalse(x.is_structure_sync_ok)

        # no error, but no sync within grace period
        x.structures_last_update_ok = True
        x.structures_last_update_at = now() - timedelta(minutes=31)
        self.assertFalse(x.is_structure_sync_ok)

    @patch(MODULE_PATH + ".STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES", 30)
    def test_is_notification_sync_ok(self):
        x = Owner.objects.get(corporation__corporation_id=2001)
        # no errors and recent sync
        x.notifications_last_update_ok = True
        x.notifications_last_update_at = now()
        self.assertTrue(x.is_notification_sync_ok)

        # no errors and sync within grace period
        x.notifications_last_update_ok = True
        x.notifications_last_update_at = now() - timedelta(minutes=29)
        self.assertTrue(x.is_notification_sync_ok)

        # recent sync error
        x.notifications_last_update_ok = None
        x.notifications_last_update_at = now()
        self.assertFalse(x.is_notification_sync_ok)

        # recent sync error
        x.notifications_last_update_ok = False
        x.notifications_last_update_at = now()
        self.assertFalse(x.is_notification_sync_ok)

        # no error, but no sync within grace period
        x.notifications_last_update_ok = True
        x.notifications_last_update_at = now() - timedelta(minutes=31)
        self.assertFalse(x.is_notification_sync_ok)

    @patch(MODULE_PATH + ".STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES", 30)
    def test_is_forwarding_sync_ok(self):
        x = Owner.objects.get(corporation__corporation_id=2001)
        # no errors and recent sync
        x.forwarding_last_update_ok = True
        x.forwarding_last_update_at = now()
        self.assertTrue(x.is_forwarding_sync_ok)

        # no errors and sync within grace period
        x.forwarding_last_update_ok = True
        x.forwarding_last_update_at = now() - timedelta(minutes=29)
        self.assertTrue(x.is_forwarding_sync_ok)

        # recent sync error
        x.forwarding_last_update_ok = None
        x.forwarding_last_update_at = now()
        self.assertFalse(x.is_forwarding_sync_ok)

        # recent sync error
        x.forwarding_last_update_ok = False
        x.forwarding_last_update_at = now()
        self.assertFalse(x.is_forwarding_sync_ok)

        # no error, but no sync within grace period
        x.forwarding_last_update_ok = True
        x.forwarding_last_update_at = now() - timedelta(minutes=31)
        self.assertFalse(x.is_forwarding_sync_ok)

    @patch(MODULE_PATH + ".STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES", 30)
    def test_is_asset_sync_ok(self):
        x = Owner.objects.get(corporation__corporation_id=2001)
        # no errors and recent sync
        x.assets_last_update_ok = True
        x.assets_last_update_at = now()
        self.assertTrue(x.is_assets_sync_ok)

        # no errors and sync within grace period
        x.assets_last_update_ok = True
        x.assets_last_update_at = now() - timedelta(minutes=29)
        self.assertTrue(x.is_assets_sync_ok)

        # recent sync error
        x.assets_last_update_ok = None
        x.assets_last_update_at = now()
        self.assertFalse(x.is_assets_sync_ok)

        # recent sync error
        x.assets_last_update_ok = False
        x.assets_last_update_at = now()
        self.assertFalse(x.is_assets_sync_ok)

        # no error, but no sync within grace period
        x.assets_last_update_ok = True
        x.assets_last_update_at = now() - timedelta(minutes=31)
        self.assertFalse(x.is_assets_sync_ok)

    @patch(MODULE_PATH + ".STRUCTURES_STRUCTURE_SYNC_GRACE_MINUTES", 30)
    @patch(MODULE_PATH + ".STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES", 30)
    @patch(MODULE_PATH + ".STRUCTURES_NOTIFICATION_SYNC_GRACE_MINUTES", 30)
    def test_is_all_syncs_ok(self):
        x = Owner.objects.get(corporation__corporation_id=2001)
        x.structures_last_update_ok = True
        x.structures_last_update_at = now()
        x.notifications_last_update_ok = True
        x.notifications_last_update_at = now()
        x.forwarding_last_update_ok = True
        x.forwarding_last_update_at = now()
        x.assets_last_update_ok = True
        x.assets_last_update_at = now()
        self.assertTrue(x.are_all_syncs_ok)

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


@patch(MODULE_PATH + ".notify_throttled")
@patch(MODULE_PATH + ".notify_admins_throttled")
class TestOwnerFetchToken(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_entities([EveCorporationInfo, EveCharacter])
        load_eveuniverse()
        cls.character = EveCharacter.objects.get(character_id=1001)
        cls.corporation = EveCorporationInfo.objects.get(corporation_id=2001)

    def test_should_return_correct_token(
        self, mock_notify_admins_throttled, mock_notify_throttled
    ):
        # given
        user, character_ownership = create_user_from_evecharacter(
            1001,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=character_ownership
        )
        # when
        token = owner.fetch_token()
        # then
        self.assertIsInstance(token, Token)
        self.assertEqual(token.user, user)
        self.assertEqual(token.character_id, 1001)
        self.assertSetEqual(
            set(Owner.get_esi_scopes()),
            set(token.scopes.values_list("name", flat=True)),
        )
        self.assertFalse(mock_notify_admins_throttled.called)
        self.assertFalse(mock_notify_throttled.called)

    def test_raise_error_when_no_sync_char_defined(
        self, mock_notify_admins_throttled, mock_notify_throttled
    ):
        # given
        owner = Owner.objects.create(corporation=self.corporation)
        # when/then
        with self.assertRaises(TokenError):
            owner.fetch_token()
        self.assertTrue(mock_notify_admins_throttled.called)
        self.assertFalse(mock_notify_throttled.called)

    def test_raise_error_when_user_has_no_permission(
        self, mock_notify_admins_throttled, mock_notify_throttled
    ):
        # given
        user, character_ownership = create_user_from_evecharacter(
            1001, scopes=Owner.get_esi_scopes()
        )
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=character_ownership
        )
        # when/then
        with self.assertRaises(TokenError):
            owner.fetch_token()
        self.assertTrue(mock_notify_admins_throttled.called)
        self.assertTrue(mock_notify_throttled.called)
        _, kwargs = mock_notify_throttled.call_args
        self.assertEqual(kwargs["user"], user)

    def test_raise_error_when_token_not_found(
        self, mock_notify_admins_throttled, mock_notify_throttled
    ):
        # given
        with patch(MODULE_PATH + ".Token.objects.filter") as my_mock:
            my_mock.return_value = None
            user, character_ownership = create_user_from_evecharacter(
                1001,
                permissions=["structures.add_structure_owner"],
                scopes=Owner.get_esi_scopes(),
            )
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=character_ownership
        )
        user.token_set.all().delete()
        # when/then
        with self.assertRaises(TokenError):
            owner.fetch_token()
        self.assertTrue(mock_notify_admins_throttled.called)
        self.assertTrue(mock_notify_throttled.called)


@patch(MODULE_PATH + ".notify_admins_throttled")
@patch("structures.helpers.esi_fetch._esi_client")
@patch("structures.helpers.esi_fetch.sleep", lambda x: None)
class TestUpdateStructuresEsi(NoSocketsTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # given (global)
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
        cls.corporation = EveCorporationInfo.objects.get(corporation_id=2001)
        cls.user, cls.main_ownership = create_user_from_evecharacter(
            1001,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        for x in entities_testdata["StructureTag"]:
            StructureTag.objects.create(**x)

    def setUp(self):
        # reset data that might be overridden
        esi_get_corporations_corporation_id_structures.override_data = None
        esi_get_corporations_corporation_id_starbases.override_data = None
        esi_get_corporations_corporation_id_customs_offices.override_data = None

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_can_sync_upwell_structures(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=self.main_ownership
        )
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.structures_last_update_ok)
        self.assertAlmostEqual(
            owner.structures_last_update_at, now(), delta=timedelta(seconds=30)
        )

        # must contain all expected structures
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

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

        # did not notify admins
        self.assertFalse(mock_notify_admins_throttled.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_can_sync_pocos(self, mock_esi_client, mock_notify_admins_throttled):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=self.main_ownership
        )
        # when
        owner.update_structures_esi()

        # then
        owner.refresh_from_db()
        self.assertTrue(owner.structures_last_update_ok)

        # must contain all expected structures
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
        }
        self.assertSetEqual(owner.structures.ids(), expected)
        self.assertSetEqual(
            set(PocoDetails.objects.values_list("structure_id", flat=True)),
            {
                1200000000003,
                1200000000004,
                1200000000005,
                1200000000006,
            },
        )

        # verify attributes for POCO
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.name, "Planet (Barren)")
        self.assertEqual(structure.eve_solar_system_id, 30002537)
        self.assertEqual(int(structure.owner.corporation.corporation_id), 2001)
        self.assertEqual(structure.eve_type_id, 2233)
        self.assertEqual(structure.reinforce_hour, 20)
        self.assertEqual(structure.state, Structure.State.UNKNOWN)
        self.assertEqual(structure.eve_planet_id, 40161472)

        # verify attributes for POCO details
        details = structure.poco_details
        self.assertEqual(details.alliance_tax_rate, 0.02)
        self.assertTrue(details.allow_access_with_standings)
        self.assertTrue(details.allow_alliance_access)
        self.assertEqual(details.bad_standing_tax_rate, 0.3)
        self.assertEqual(details.corporation_tax_rate, 0.02)
        self.assertEqual(details.excellent_standing_tax_rate, 0.02)
        self.assertEqual(details.good_standing_tax_rate, 0.02)
        self.assertEqual(details.neutral_standing_tax_rate, 0.02)
        self.assertEqual(details.reinforce_exit_end, 21)
        self.assertEqual(details.reinforce_exit_start, 19)
        self.assertEqual(details.standing_level, PocoDetails.StandingLevel.TERRIBLE)
        self.assertEqual(details.terrible_standing_tax_rate, 0.5)

        # did not notify admins
        self.assertFalse(mock_notify_admins_throttled.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_can_sync_starbases(self, mock_esi_client, mock_notify_admins_throttled):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=self.main_ownership
        )

        # when
        owner.update_structures_esi()

        # then
        owner.refresh_from_db()
        self.assertTrue(owner.structures_last_update_ok)

        # must contain all expected structures
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

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
        # did not notify admins
        self.assertFalse(mock_notify_admins_throttled.called)

    @patch(MODULE_PATH + ".notify", spec=True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_can_sync_all_structures_and_notify_user(
        self, mock_notify, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=self.main_ownership
        )

        # when
        owner.update_structures_esi(user=self.user)

        # then
        owner.refresh_from_db()
        self.assertTrue(owner.structures_last_update_ok)

        # must contain all expected structures
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
        self.assertSetEqual(owner.structures.ids(), expected)

        # user report has been sent
        self.assertTrue(mock_notify.called)

        # did not notify admins
        self.assertFalse(mock_notify_admins_throttled.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_can_handle_owner_without_structures(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        _, my_main_ownership = create_user_from_evecharacter(
            1005,
            permissions=["structures.add_structure_owner"],
            scopes=Owner.get_esi_scopes(),
        )
        my_corporation = EveCorporationInfo.objects.get(corporation_id=2005)
        owner = Owner.objects.create(
            corporation=my_corporation, character_ownership=my_main_ownership
        )
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.structures_last_update_ok)
        self.assertSetEqual(owner.structures.ids(), set())
        self.assertFalse(mock_notify_admins_throttled.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_not_break_on_http_error_when_fetching_upwell_structures(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
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
            corporation=self.corporation, character_ownership=self.main_ownership
        )
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.structures_last_update_ok)
        expected = {
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(owner.structures.ids(), expected)
        self.assertTrue(mock_notify_admins_throttled.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_not_break_on_http_error_when_fetching_custom_offices(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
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
            corporation=self.corporation, character_ownership=self.main_ownership
        )
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.structures_last_update_ok)
        structure_ids = {x["id"] for x in owner.structures.values("id")}
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(structure_ids, expected)
        self.assertTrue(mock_notify_admins_throttled.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_not_break_on_http_error_when_fetching_star_bases(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
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
            corporation=self.corporation, character_ownership=self.main_ownership
        )
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertFalse(owner.structures_last_update_ok)
        expected = {
            1000000000001,
            1000000000002,
            1000000000003,
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
        }
        self.assertSetEqual(owner.structures.ids(), expected)
        self.assertTrue(mock_notify_admins_throttled.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_update_will_not_break_on_http_error_from_structure_info(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        # remove info data for structure with ID 1000000000002
        data = deepcopy(esi_data["Universe"]["get_universe_structures_structure_id"])
        del data["1000000000002"]
        esi_get_universe_structures_structure_id.override_data = data
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=self.main_ownership
        )
        # when
        owner.update_structures_esi()
        # then
        self.assertFalse(owner.structures_last_update_ok)
        esi_get_universe_structures_structure_id.override_data = None
        structure = Structure.objects.get(id=1000000000002)
        self.assertEqual(structure.name, "(no data)")
        self.assertTrue(mock_notify_admins_throttled.called)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_removes_old_structures(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=self.main_ownership
        )

        # run update task with all structures
        owner.update_structures_esi()

        # should contain the right structures
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

        # run update task 2nd time with one less structure
        my_corp_structures_data = deepcopy(esi_corp_structures_data)
        del my_corp_structures_data["2001"][1]
        esi_get_corporations_corporation_id_structures.override_data = (
            my_corp_structures_data
        )
        owner.update_structures_esi()

        # should contain only the remaining structures
        expected = {1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_tags_are_not_modified_by_update(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=self.main_ownership
        )

        # run update task with all structures
        owner.update_structures_esi()
        # should contain the right structures
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

        # adding tags
        tag_a = StructureTag.objects.get(name="tag_a")
        s = Structure.objects.get(id=1000000000001)
        s.tags.add(tag_a)
        s.save()

        # run update task 2nd time
        owner.update_structures_esi()

        # should still contain alls structures
        expected = {1000000000001, 1000000000002, 1000000000003}
        self.assertSetEqual(owner.structures.ids(), expected)

        # should still contain the tag
        s_new = Structure.objects.get(id=1000000000001)
        self.assertEqual(s_new.tags.get(name="tag_a"), tag_a)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_remove_structures_not_returned_from_esi(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
        esi_get_corporations_corporation_id_structures.override_data = {"2001": []}
        esi_get_corporations_corporation_id_starbases.override_data = {"2001": []}
        esi_get_corporations_corporation_id_customs_offices.override_data = {"2001": []}
        mock_esi_client.side_effect = esi_mock_client
        create_structures(dont_load_entities=True)
        owner = Owner.objects.get(corporation__corporation_id=2001)
        owner.character_ownership = self.main_ownership
        owner.save()
        self.assertGreater(owner.structures.count(), 0)
        # when
        owner.update_structures_esi()
        # then
        owner.refresh_from_db()
        self.assertTrue(owner.structures_last_update_ok)
        self.assertEqual(owner.structures.count(), 0)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", True)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_not_delete_existing_structures_when_update_failed_with_http_error(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_structures.side_effect = HTTPInternalServerError(
            BravadoResponseStub(status_code=500, reason="Test")
        )
        mock_esi_client.return_value.Corporation.get_corporations_corporation_id_starbases.side_effect = HTTPInternalServerError(
            BravadoResponseStub(status_code=500, reason="Test")
        )
        mock_esi_client.return_value.Planetary_Interaction.get_corporations_corporation_id_customs_offices.side_effect = HTTPInternalServerError(
            BravadoResponseStub(status_code=500, reason="Test")
        )
        create_structures(dont_load_entities=True)
        owner = Owner.objects.get(corporation__corporation_id=2001)
        owner.character_ownership = self.main_ownership
        owner.save()
        # when
        owner.update_structures_esi()
        # then
        self.assertFalse(owner.structures_last_update_ok)
        expected = expected = {
            1000000000001,
            1000000000002,
            1200000000003,
            1200000000004,
            1200000000005,
            1200000000006,
            1300000000001,
            1300000000002,
            1300000000003,
        }
        self.assertSetEqual(owner.structures.ids(), expected)

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", False)
    def test_removes_outdated_services(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=self.main_ownership
        )

        # run update task with all structures
        owner.update_structures_esi()
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
        owner.update_structures_esi()
        # should contain only the remaining service
        structure.refresh_from_db()
        self.assertEqual(
            {x.name for x in StructureService.objects.filter(structure=structure)},
            {"Moon Drilling"},
        )

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_should_have_empty_name_if_not_match_with_planets(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=self.main_ownership
        )
        EvePlanet.objects.all().delete()
        # when
        owner.update_structures_esi()
        # then
        self.assertTrue(owner.structures_last_update_ok)
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.name, "")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_define_poco_name_from_planet_type_if_found(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=self.main_ownership
        )
        # when
        owner.update_structures_esi()
        # then
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.eve_planet_id, 40161472)
        self.assertEqual(structure.name, "Planet (Barren)")

    @patch(MODULE_PATH + ".STRUCTURES_DEFAULT_LANGUAGE", "de")
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_define_poco_name_from_planet_type_localized(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=self.main_ownership
        )
        # when
        owner.update_structures_esi()
        # then
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.eve_planet_id, 40161472)
        self.assertEqual(structure.name, "Planet (Barren)_de")

    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_STARBASES", False)
    @patch(MODULE_PATH + ".STRUCTURES_FEATURE_CUSTOMS_OFFICES", True)
    def test_update_pocos_no_asset_name_match(
        self, mock_esi_client, mock_notify_admins_throttled
    ):
        # given
        esi_post_corporations_corporation_id_assets_names.override_data = {"2001": []}
        mock_esi_client.side_effect = esi_mock_client
        owner = Owner.objects.create(
            corporation=self.corporation, character_ownership=self.main_ownership
        )
        EvePlanet.objects.all().delete()
        # when
        owner.update_structures_esi()
        # then
        structure = Structure.objects.get(id=1200000000003)
        self.assertEqual(structure.name, "")
        esi_post_corporations_corporation_id_assets_names.override_data = None
