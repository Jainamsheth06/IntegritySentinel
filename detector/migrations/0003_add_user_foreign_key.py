from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('detector', '0002_emailfraudcheck_callfraudcheck_messagefraudcheck'),
    ]

    operations = [
        migrations.AddField(
            model_name='transactioncheck',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='transaction_checks', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='emailfraudcheck',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='email_checks', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='callfraudcheck',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='call_checks', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='messagefraudcheck',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='message_checks', to=settings.AUTH_USER_MODEL),
        ),
    ]
