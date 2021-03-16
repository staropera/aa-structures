# Generated by Django 3.1.6 on 2021-03-16 17:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("structures", "0020_more_war_notifications"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="general",
            options={
                "default_permissions": (),
                "managed": False,
                "permissions": (
                    ("basic_access", "Can access this app and view public pages"),
                    ("view_corporation_structures", "Can view corporation structures"),
                    ("view_alliance_structures", "Can view alliance structures"),
                    ("view_all_structures", "Can view all structures"),
                    ("add_structure_owner", "Can add new structure owner"),
                    (
                        "view_all_unanchoring_status",
                        "Can view unanchoring timers for all structures the user can see",
                    ),
                ),
            },
        ),
    ]
