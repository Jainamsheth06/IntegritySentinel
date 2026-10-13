import os
import shutil
from pathlib import Path
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fraudguard.settings')

if os.environ.get('VERCEL'):
    try:
        tmp_db = Path('/tmp/db.sqlite3')
        base_db = Path(__file__).resolve().parent.parent / 'db.sqlite3'
        if base_db.exists() and not tmp_db.exists():
            shutil.copy2(base_db, tmp_db)
    except Exception as e:
        print(f"Error copying initial database: {e}")

    try:
        from django.core.management import call_command
        call_command('migrate', interactive=False)
    except Exception as e:
        print(f"Auto-migration warning: {e}")

application = get_wsgi_application()
app = application

