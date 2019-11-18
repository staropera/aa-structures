# Generated by Django 2.2.5 on 2019-11-18 16:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('structures', '0003_auto_20191117_2143'),
    ]

    operations = [
        migrations.AddField(
            model_name='webhook',
            name='is_active',
            field=models.BooleanField(default=False, help_text='whether notifications are sent to this webhook'),
        ),
    ]
