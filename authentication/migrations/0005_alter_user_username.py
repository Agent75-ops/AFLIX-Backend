# Generated by Django 4.2.13 on 2024-06-12 13:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0004_remove_commentslikesdislike_comment_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='username',
            field=models.CharField(max_length=256),
        ),
    ]