import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # la chiave deve stare nella variabile d'ambiente OPENAI_API_KEY

def generate_prompt(headlines):
    prompt_text = (
        "Genera un prompt in inglese per creare un illustrazione basata su tutte le seguenti informazioni. voglio un illustrazione fotorealistica con personaggi reali della politica coinvolti nelle news, tutte le varie news devono essere rappresentate in una specie di collage di informazioni frammentarie.:\n"
        + "\n".join(headlines)
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt_text}]
    )
    return response.choices[0].message.content

