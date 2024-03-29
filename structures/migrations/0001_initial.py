# Generated by Django 2.2.5 on 2019-11-21 03:27

import multiselectfield.db.fields

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

import structures.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("eveonline", "0010_alliance_ticker"),
        ("authentication", "0016_ownershiprecord"),
    ]

    operations = [
        migrations.CreateModel(
            name="General",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
            ],
            options={
                "permissions": (
                    ("basic_access", "Can access this app and view"),
                    ("view_alliance_structures", "Can view alliance structures"),
                    ("view_all_structures", "Can view all structures"),
                    ("add_structure_owner", "Can add new structure owner"),
                ),
                "default_permissions": (),
                "managed": False,
            },
        ),
        migrations.CreateModel(
            name="EveConstellation",
            fields=[
                (
                    "id",
                    models.IntegerField(
                        help_text="Eve Online region ID",
                        primary_key=True,
                        serialize=False,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("name", models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="EveEntity",
            fields=[
                (
                    "id",
                    models.IntegerField(
                        primary_key=True,
                        serialize=False,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "category",
                    models.IntegerField(
                        choices=[
                            (1, "character"),
                            (2, "corporation"),
                            (3, "alliance"),
                            (4, "faction"),
                            (5, "other"),
                        ]
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        blank=True, default=None, max_length=255, null=True
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="EveGroup",
            fields=[
                (
                    "id",
                    models.IntegerField(
                        help_text="Eve Online group ID",
                        primary_key=True,
                        serialize=False,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("name", models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="EveRegion",
            fields=[
                (
                    "id",
                    models.IntegerField(
                        help_text="Eve Online region ID",
                        primary_key=True,
                        serialize=False,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("name", models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="EveSolarSystem",
            fields=[
                (
                    "id",
                    models.IntegerField(
                        help_text="Eve Online solar system ID",
                        primary_key=True,
                        serialize=False,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("security_status", models.FloatField()),
                (
                    "eve_constellation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="structures.EveConstellation",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="EveType",
            fields=[
                (
                    "id",
                    models.IntegerField(
                        help_text="Eve Online type ID",
                        primary_key=True,
                        serialize=False,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                (
                    "eve_group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="structures.EveGroup",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Owner",
            fields=[
                (
                    "corporation",
                    models.OneToOneField(
                        help_text="Corporation owning structures",
                        on_delete=django.db.models.deletion.CASCADE,
                        primary_key=True,
                        serialize=False,
                        to="eveonline.EveCorporationInfo",
                    ),
                ),
                (
                    "structures_last_sync",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="when the last sync happened",
                        null=True,
                    ),
                ),
                (
                    "structures_last_error",
                    models.IntegerField(
                        choices=[
                            (0, "No error"),
                            (1, "Invalid token"),
                            (2, "Expired token"),
                            (3, "Insufficient permissions"),
                            (4, "No character set for fetching alliance contacts"),
                            (5, "ESI API is currently unavailable"),
                            (6, "Operaton mode does not match with current setting"),
                            (99, "Unknown error"),
                        ],
                        default=0,
                        help_text="error that occurred at the last sync atttempt (if any)",
                    ),
                ),
                (
                    "notifications_last_sync",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="when the last sync happened",
                        null=True,
                    ),
                ),
                (
                    "notifications_last_error",
                    models.IntegerField(
                        choices=[
                            (0, "No error"),
                            (1, "Invalid token"),
                            (2, "Expired token"),
                            (3, "Insufficient permissions"),
                            (4, "No character set for fetching alliance contacts"),
                            (5, "ESI API is currently unavailable"),
                            (6, "Operaton mode does not match with current setting"),
                            (99, "Unknown error"),
                        ],
                        default=0,
                        help_text="error that occurred at the last sync atttempt (if any)",
                    ),
                ),
                (
                    "character",
                    models.ForeignKey(
                        blank=True,
                        default=None,
                        help_text="character used for syncing structures",
                        null=True,
                        on_delete=django.db.models.deletion.SET_DEFAULT,
                        to="authentication.CharacterOwnership",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Structure",
            fields=[
                (
                    "id",
                    models.BigIntegerField(
                        help_text="The Item ID of the structure",
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="The full name of the structure", max_length=255
                    ),
                ),
                (
                    "position_x",
                    models.FloatField(
                        blank=True,
                        default=None,
                        help_text="x position of the structure in the solar system",
                        null=True,
                    ),
                ),
                (
                    "position_y",
                    models.FloatField(
                        blank=True,
                        default=None,
                        help_text="y position of the structure in the solar system",
                        null=True,
                    ),
                ),
                (
                    "position_z",
                    models.FloatField(
                        blank=True,
                        default=None,
                        help_text="z position of the structure in the solar system",
                        null=True,
                    ),
                ),
                (
                    "fuel_expires",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="Date on which the structure will run out of fuel",
                        null=True,
                    ),
                ),
                (
                    "next_reinforce_hour",
                    models.IntegerField(
                        blank=True,
                        default=None,
                        help_text="The requested change to reinforce_hour that will take effect at the time shown by next_reinforce_apply",
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(23),
                        ],
                    ),
                ),
                (
                    "next_reinforce_weekday",
                    models.IntegerField(
                        blank=True,
                        default=None,
                        help_text="The date and time when the structure’s newly requested reinforcement times (e.g. next_reinforce_hour and next_reinforce_day) will take effect",
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(6),
                        ],
                    ),
                ),
                (
                    "next_reinforce_apply",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="The requested change to reinforce_weekday that will take effect at the time shown by next_reinforce_apply",
                        null=True,
                    ),
                ),
                (
                    "reinforce_hour",
                    models.IntegerField(
                        help_text="The hour of day that determines the four hour window when the structure will randomly exit its reinforcement periods and become vulnerable to attack against its armor and/or hull. The structure will become vulnerable at a random time that is +/- 2 hours centered on the value of this property",
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(23),
                        ],
                    ),
                ),
                (
                    "reinforce_weekday",
                    models.IntegerField(
                        blank=True,
                        default=None,
                        help_text="The day of the week when the structure exits its final reinforcement period and becomes vulnerable to attack against its hull. Monday is 0 and Sunday is 6",
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(6),
                        ],
                    ),
                ),
                (
                    "state",
                    models.IntegerField(
                        choices=[
                            (0, "N/A"),
                            (1, "anchor_vulnerable"),
                            (2, "anchoring"),
                            (3, "armor_reinforce"),
                            (4, "armor_vulnerable"),
                            (5, "deploy_vulnerable"),
                            (6, "fitting_invulnerable"),
                            (7, "hull_reinforce"),
                            (8, "hull_vulnerable"),
                            (9, "online_deprecated"),
                            (10, "onlining_vulnerable"),
                            (11, "shield_vulnerable"),
                            (12, "unanchored"),
                            (13, "unknown"),
                        ],
                        help_text="Current state of the structure",
                    ),
                ),
                (
                    "state_timer_start",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="Date at which the structure will move to it’s next state",
                        null=True,
                    ),
                ),
                (
                    "state_timer_end",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="Date at which the structure entered it’s current state",
                        null=True,
                    ),
                ),
                (
                    "unanchors_at",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="Date at which the structure will unanchor",
                        null=True,
                    ),
                ),
                (
                    "last_updated",
                    models.DateTimeField(
                        blank=True,
                        default=None,
                        help_text="date this structure was last updated from the EVE server",
                        null=True,
                    ),
                ),
                (
                    "eve_solar_system",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="structures.EveSolarSystem",
                    ),
                ),
                (
                    "eve_type",
                    models.ForeignKey(
                        help_text="type of the structure",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="structures.EveType",
                    ),
                ),
                (
                    "owner",
                    models.ForeignKey(
                        help_text="Corporation that owns the structure",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="structures.Owner",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Webhook",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="short name to identify this webhook",
                        max_length=64,
                        unique=True,
                    ),
                ),
                (
                    "webhook_type",
                    models.IntegerField(
                        choices=[(1, "Discord Webhook")],
                        default=1,
                        help_text="type of this webhook",
                    ),
                ),
                (
                    "url",
                    models.CharField(
                        help_text="URL of this webhook, e.g. https://discordapp.com/api/webhooks/123456/abcdef",
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        blank=True,
                        default=None,
                        help_text="you can add notes about this webhook here if you want",
                        null=True,
                    ),
                ),
                (
                    "notification_types",
                    multiselectfield.db.fields.MultiSelectField(
                        choices=[
                            (401, "MoonminingAutomaticFracture"),
                            (402, "MoonminingExtractionCancelled"),
                            (403, "MoonminingExtractionFinished"),
                            (404, "MoonminingExtractionStarted"),
                            (405, "MoonminingLaserFired"),
                            (513, "OwnershipTransferred"),
                            (501, "StructureAnchoring"),
                            (502, "StructureDestroyed"),
                            (503, "StructureFuelAlert"),
                            (504, "StructureLostArmor"),
                            (505, "StructureLostShields"),
                            (506, "StructureOnline"),
                            (507, "StructureServicesOffline"),
                            (508, "StructureUnanchoring"),
                            (509, "StructureUnderAttack"),
                            (510, "StructureWentHighPower"),
                            (511, "StructureWentLowPower"),
                        ],
                        default=structures.models.get_default_notification_types,
                        help_text="only notifications which selected types are sent to this webhook",
                        max_length=67,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="whether notifications are currently sent to this webhook",
                    ),
                ),
                (
                    "is_default",
                    models.BooleanField(
                        default=False,
                        help_text="whether newly added owners have this automatically webhook preset",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="owner",
            name="webhooks",
            field=models.ManyToManyField(
                blank=True,
                default=None,
                help_text="notifications are sent to these webhooks. ",
                to="structures.Webhook",
            ),
        ),
        migrations.CreateModel(
            name="EveMoon",
            fields=[
                (
                    "id",
                    models.IntegerField(
                        help_text="Eve Online item ID",
                        primary_key=True,
                        serialize=False,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                (
                    "position_x",
                    models.FloatField(
                        blank=True,
                        default=None,
                        help_text="x position of the structure in the solar system",
                        null=True,
                    ),
                ),
                (
                    "position_y",
                    models.FloatField(
                        blank=True,
                        default=None,
                        help_text="y position of the structure in the solar system",
                        null=True,
                    ),
                ),
                (
                    "position_z",
                    models.FloatField(
                        blank=True,
                        default=None,
                        help_text="z position of the structure in the solar system",
                        null=True,
                    ),
                ),
                (
                    "eve_solar_system",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="structures.EveSolarSystem",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="eveconstellation",
            name="eve_region",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="structures.EveRegion"
            ),
        ),
        migrations.CreateModel(
            name="StructureService",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(help_text="Name of the service", max_length=64),
                ),
                (
                    "state",
                    models.IntegerField(
                        choices=[(1, "offline"), (2, "online")],
                        help_text="Current state of this service",
                    ),
                ),
                (
                    "structure",
                    models.ForeignKey(
                        help_text="Structure this service is installed to",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="structures.Structure",
                    ),
                ),
            ],
            options={
                "unique_together": {("structure", "name")},
            },
        ),
        migrations.CreateModel(
            name="Notification",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "notification_id",
                    models.BigIntegerField(
                        validators=[django.core.validators.MinValueValidator(0)]
                    ),
                ),
                ("timestamp", models.DateTimeField()),
                (
                    "notification_type",
                    models.IntegerField(
                        choices=[
                            (401, "MoonminingAutomaticFracture"),
                            (402, "MoonminingExtractionCancelled"),
                            (403, "MoonminingExtractionFinished"),
                            (404, "MoonminingExtractionStarted"),
                            (405, "MoonminingLaserFired"),
                            (513, "OwnershipTransferred"),
                            (501, "StructureAnchoring"),
                            (502, "StructureDestroyed"),
                            (503, "StructureFuelAlert"),
                            (504, "StructureLostArmor"),
                            (505, "StructureLostShields"),
                            (506, "StructureOnline"),
                            (507, "StructureServicesOffline"),
                            (508, "StructureUnanchoring"),
                            (509, "StructureUnderAttack"),
                            (510, "StructureWentHighPower"),
                            (511, "StructureWentLowPower"),
                        ]
                    ),
                ),
                ("text", models.TextField(blank=True, default=None, null=True)),
                ("is_read", models.BooleanField(blank=True, default=None, null=True)),
                ("is_sent", models.BooleanField(blank=True, default=False)),
                ("last_updated", models.DateTimeField()),
                (
                    "owner",
                    models.ForeignKey(
                        help_text="Corporation that received this notification",
                        on_delete=django.db.models.deletion.CASCADE,
                        to="structures.Owner",
                    ),
                ),
                (
                    "sender",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="structures.EveEntity",
                    ),
                ),
            ],
            options={
                "unique_together": {("notification_id", "owner")},
            },
        ),
    ]
