from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('detector', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailFraudCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sender_email', models.EmailField(max_length=254)),
                ('subject', models.CharField(blank=True, max_length=255)),
                ('body_text', models.TextField()),
                ('is_fraud', models.BooleanField(default=False)),
                ('risk_score', models.IntegerField(default=0)),
                ('detected_reasons', models.TextField(blank=True)),
                ('checked_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='CallFraudCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone_number', models.CharField(max_length=30)),
                ('call_context', models.TextField(blank=True)),
                ('is_fraud', models.BooleanField(default=False)),
                ('risk_score', models.IntegerField(default=0)),
                ('detected_reasons', models.TextField(blank=True)),
                ('checked_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='MessageFraudCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sender_info', models.CharField(max_length=100)),
                ('message_text', models.TextField()),
                ('is_fraud', models.BooleanField(default=False)),
                ('risk_score', models.IntegerField(default=0)),
                ('detected_reasons', models.TextField(blank=True)),
                ('checked_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
