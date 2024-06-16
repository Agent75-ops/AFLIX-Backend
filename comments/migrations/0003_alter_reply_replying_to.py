# Generated by Django 4.2.13 on 2024-05-21 06:38

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('comments', '0002_comment_commentlikedislike_reply_replylikedislike_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reply',
            name='replying_to',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='replied_to_me', to='comments.reply'),
        ),
    ]