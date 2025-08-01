import hashlib

def generate_image_mock(prompt: str):
    # Simula un URL unico per ogni prompt
    fake_hash = hashlib.md5(prompt.encode()).hexdigest()
    return f"https://yourdomain.com/images/{fake_hash}.png"

