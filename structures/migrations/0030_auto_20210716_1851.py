# Generated by Django 3.1.12 on 2021-07-16 18:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("structures", "0029_auto_20210716_1849"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fuelnotificationconfig",
            name="level",
            field=models.CharField(
                choices=[
                    ("danger", "danger"),
                    ("default", "default"),
                    ("info", "info"),
                    ("primary", "primary"),
                    ("success", "success"),
                    ("warning", "warning"),
                ],
                default="warning",
                max_length=10,
            ),
        ),
    ]
