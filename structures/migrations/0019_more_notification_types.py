# Generated by Django 3.1.6 on 2021-02-19 12:05

from django.db import migrations
import multiselectfield.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ("structures", "0018_restructure_notifications_2"),
    ]

    operations = [
        migrations.AlterField(
            model_name="webhook",
            name="notification_types",
            field=multiselectfield.db.fields.MultiSelectField(
                choices=[
                    ("StructureAnchoring", "Upwell structure anchoring"),
                    ("StructureOnline", "Upwell structure went online"),
                    (
                        "StructureServicesOffline",
                        "Upwell structure services went offline",
                    ),
                    ("StructureWentHighPower", "Upwell structure went high power"),
                    ("StructureWentLowPower", "Upwell structure went low power"),
                    ("StructureUnanchoring", "Upwell structure unanchoring"),
                    ("StructureFuelAlert", "Upwell structure fuel alert"),
                    ("StructureUnderAttack", "Upwell structure is under attack"),
                    ("StructureLostShields", "Upwell structure lost shields"),
                    ("StructureLostArmor", "Upwell structure lost armor"),
                    ("StructureDestroyed", "Upwell structure destroyed"),
                    (
                        "StructuresReinforcementChanged",
                        "Upwell structure reinforcement time changed",
                    ),
                    ("OwnershipTransferred", "Upwell structure ownership transferred"),
                    ("OrbitalAttacked", "Customs office attacked"),
                    ("OrbitalReinforced", "Customs office reinforced"),
                    ("TowerAlertMsg", "Starbase attacked"),
                    ("TowerResourceAlertMsg", "Starbase fuel alert"),
                    ("MoonminingExtractionStarted", "Moonmining extraction started"),
                    ("MoonminingLaserFired", "Moonmining laser fired"),
                    (
                        "MoonminingExtractionCancelled",
                        "Moonmining extraction cancelled",
                    ),
                    ("MoonminingExtractionFinished", "Moonmining extraction finished"),
                    (
                        "MoonminingAutomaticFracture",
                        "Moonmining automatic fracture triggered",
                    ),
                    ("SovStructureReinforced", "Sovereignty structure reinforced"),
                    ("SovStructureDestroyed", "Sovereignty structure destroyed"),
                    ("EntosisCaptureStarted", "Sovereignty entosis capture started"),
                    (
                        "SovCommandNodeEventStarted",
                        "Sovereignty command node event started",
                    ),
                    ("SovAllClaimAquiredMsg", "Sovereignty claim acknowledgment"),
                    ("SovAllClaimLostMsg", "Sovereignty lost"),
                    ("WarDeclared", "War declared"),
                    ("AllyJoinedWarAggressorMsg", "War ally joined aggressor"),
                    ("AllyJoinedWarAllyMsg", "War ally joined ally"),
                    ("AllyJoinedWarDefenderMsg", "War ally joined defender"),
                    ("WarAdopted", "War adopted"),
                    ("WarInherited", "War inherited"),
                    ("CorpWarSurrenderMsg", "War party surrendered"),
                    ("WarRetractedByConcord", "War retracted by Concord"),
                    ("CharAppAcceptMsg", "Character joins corporation"),
                    ("CharLeftCorpMsg", "Character leaves corporation"),
                ],
                default=[
                    "StructureAnchoring",
                    "StructureDestroyed",
                    "StructureFuelAlert",
                    "StructureLostArmor",
                    "StructureLostShields",
                    "StructureOnline",
                    "StructureServicesOffline",
                    "StructureUnderAttack",
                    "StructureWentHighPower",
                    "StructureWentLowPower",
                    "OrbitalAttacked",
                    "OrbitalReinforced",
                    "TowerAlertMsg",
                    "TowerResourceAlertMsg",
                    "SovStructureReinforced",
                    "SovStructureDestroyed",
                ],
                help_text="select which type of notifications should be forwarded to this webhook",
                max_length=800,
            ),
        ),
    ]
