from app import create_app

# Compatibility entrypoint for platforms configured with "gunicorn main:app"
app = create_app()
