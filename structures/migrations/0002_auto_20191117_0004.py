# Generated by Django 2.2.5 on 2019-11-17 00:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('structures', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='text',
            field=models.TextField(blank=True, default=None, null=True),
        ),
    ]
