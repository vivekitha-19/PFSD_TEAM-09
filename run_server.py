#!/usr/bin/env python
"""
╔══════════════════════════════════════════════════════════════════╗
║     FARMER ADVISORY SYSTEM - SETUP & RUN SCRIPT                 ║
║     Run this file directly in PyCharm to start the server        ║
╚══════════════════════════════════════════════════════════════════╝

HOW TO RUN IN PYCHARM:
1. Right-click this file → Run 'run_server.py'
   OR
2. Open terminal in PyCharm → python run_server.py

The server will start at: http://127.0.0.1:8000
"""
import os
import sys
import subprocess

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'farmer_advisory.settings')

def check_packages():
    """Check if required packages are installed"""
    required = ['django', 'graphene_django', 'pymongo', 'nltk', 'sklearn', 'corsheaders']
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    return missing

def run():
    print("=" * 60)
    print("  🌾 FARMER ADVISORY AI SYSTEM - Starting Up")
    print("=" * 60)

    # Check packages
    missing = check_packages()
    if missing:
        print(f"\n⚠️  Missing packages detected: {missing}")
        print("   Installing requirements...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])

    # Download NLTK data
    print("\n📥 Downloading NLTK data...")
    try:
        import nltk
        for r in ['punkt', 'stopwords', 'wordnet', 'omw-1.4']:
            nltk.download(r, quiet=True)
        print("   ✅ NLTK data ready")
    except Exception as e:
        print(f"   ⚠️  NLTK download skipped: {e}")

    # Run migrations
    print("\n🗄️  Running Django migrations...")
    from django.core.management import call_command
    import django
    django.setup()
    call_command('migrate', '--run-syncdb', verbosity=0)
    print("   ✅ Database migrations complete")

    # Start development server
    print("\n" + "=" * 60)
    print("  🚀 Starting development server...")
    print("  📍 Dashboard:   http://127.0.0.1:8000")
    print("  ⚡ GraphQL API: http://127.0.0.1:8000/graphql/")
    print("  💚 Health:      http://127.0.0.1:8000/health/")
    print("  Press Ctrl+C to stop")
    print("=" * 60 + "\n")

    call_command('runserver', '127.0.0.1:8000')

if __name__ == '__main__':
    run()
