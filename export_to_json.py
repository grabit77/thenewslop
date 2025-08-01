import sqlite3
import json

DB_FILE = "news.db"
JSON_FILE = "news.json"

def export_db_to_json(db_file, json_file):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()
    c.execute("SELECT id, news, prompt, image_name, timestamp FROM news ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()

    # Costruiamo una lista di dizionari
    news_list = []
    for row in rows:
        news_list.append({
            "id": row[0],
            "news": row[1],
            "prompt": row[2],
            "image_name": row[3],
            "timestamp": row[4]
        })

    # Scriviamo su JSON con indentazione per leggibilità
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(news_list, f, ensure_ascii=False, indent=4)

    print(f"✅ Esportate {len(news_list)} news in {json_file}")

if __name__ == "__main__":
    export_db_to_json(DB_FILE, JSON_FILE)
