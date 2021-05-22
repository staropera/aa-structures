# Generated by Django 3.1.10 on 2021-05-22 13:46

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("structures", "0024_fix_name_fields_too_small"),
    ]

    operations = [
        migrations.AddField(
            model_name="owner",
            name="are_pocos_public",
            field=models.BooleanField(
                default=False,
                help_text="whether pocos of this owner are shown on public POCO page",
            ),
        ),
        migrations.CreateModel(
            name="PocoDetails",
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
                ("alliance_tax_rate", models.FloatField(default=None, null=True)),
                ("allow_access_with_standings", models.BooleanField()),
                ("allow_alliance_access", models.BooleanField()),
                ("bad_standing_tax_rate", models.FloatField(default=None, null=True)),
                ("corporation_tax_rate", models.FloatField(default=None, null=True)),
                (
                    "excellent_standing_tax_rate",
                    models.FloatField(default=None, null=True),
                ),
                ("good_standing_tax_rate", models.FloatField(default=None, null=True)),
                (
                    "neutral_standing_tax_rate",
                    models.FloatField(default=None, null=True),
                ),
                ("reinforce_exit_end", models.PositiveIntegerField()),
                ("reinforce_exit_start", models.PositiveIntegerField()),
                (
                    "standing_level",
                    models.IntegerField(
                        choices=[
                            (-99, "none"),
                            (-10, "terrible"),
                            (-5, "bad"),
                            (0, "neutral"),
                            (5, "good"),
                            (10, "excellent"),
                        ],
                        default=-99,
                    ),
                ),
                (
                    "terrible_standing_tax_rate",
                    models.FloatField(default=None, null=True),
                ),
                (
                    "structure",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="poco_details",
                        to="structures.structure",
                    ),
                ),
            ],
        ),
    ]
