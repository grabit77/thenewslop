import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NEWS_API_KEY")

def fetch_conflict_news():
    url = (
        f"https://newsapi.org/v2/everything?q=war+conflict+genocide&language=en&pageSize=5&apiKey={API_KEY}"
    )
    res = requests.get(url)
    articles = res.json().get("articles", [])
    headlines = [a["title"] for a in articles]
    return headlines

