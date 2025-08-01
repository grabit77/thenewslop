#!/bin/bash
set -e

# 1️⃣ Esegui export_to_json.py
python3 export_to_json.py
echo "✅ Esportate news in news.json"

# 2️⃣ Fai pull con rebase per aggiornare la branch locale
git pull --rebase origin main || {
  echo "❌ Errore durante il pull, risolvere manualmente."
  exit 1
}

# 3️⃣ Aggiungi **tutti** i cambiamenti e file nuovi (anche non tracciati)
git add -A

# 4️⃣ Controlla se ci sono modifiche da pushare
if git diff --cached --quiet; then
  echo "ℹ️ Nessuna modifica da pushare."
  exit 0
fi

# 5️⃣ Commit e push
git commit -m "Aggiornamento automatico news, db e immagini"
git push origin main
echo "🚀 Push completato con successo!"
