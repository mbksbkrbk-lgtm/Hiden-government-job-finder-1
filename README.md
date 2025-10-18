# gov-hidden-vacancy-finder (Render-ready)

Files:
 - app.py
 - requirements.txt
 - Procfile

Deploy on Render (mobile-friendly):
1. Create a GitHub repo and upload these files (Add file -> Upload files).
2. Sign up at https://www.scraperapi.com and get your API key.
3. In Render, set environment variable SCRAPERAPI_KEY to your API key (Service -> Environment -> Add variable).
4. On Render, New -> Web Service -> Connect GitHub -> select repo.
5. Build command: pip install -r requirements.txt
   Start command: gunicorn app:app
6. Deploy and open your public URL. Paste a Govt site URL on the homepage (e.g. https://goidirectory.gov.in) and click Find Jobs.
