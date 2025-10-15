import os
import requests
from bs4 import BeautifulSoup
import psycopg2
from datetime import datetime, timezone
import re

DATABASE_URL = os.environ.get("DATABASE_URL")

def init_db():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS alertas_amber (
                id TEXT PRIMARY KEY,
                titulo TEXT,
                lugar TEXT,
                edad INTEGER,
                url TEXT,
                fecha_extraccion TIMESTAMP DEFAULT NOW()
            )
        ''')
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Base de datos inicializada.")
    except Exception as e:
        print(f"❌ Error al conectar a la base de datos: {e}")

def scrape_alertas():
    url = "https://www.mp.gob.pa/category/alerta-amber/"
    headers = {'User-Agent': 'Mozilla/5.0 (Investigacion; +tuemail@institucion.edu)'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ Error al acceder al MP: {e}")
        return []

    soup = BeautifulSoup(resp.content, 'html.parser')
    posts = soup.select('article')

    alertas = []
    for post in posts:
        link = post.select_one('a')
        if not link:
            continue
        href = link['href']
        title = link.get_text(strip=True)

        edad = None
        lugar = "Desconocido"
        if "años" in title.lower():
            m = re.search(r'(\d{1,2})\s*años', title, re.IGNORECASE)
            edad = int(m.group(1)) if m else None

        alertas.append({
            'id': href.split('/')[-2] or href,
            'titulo': title,
            'lugar': lugar,
            'edad': edad,
            'url': href
        })
    return alertas

def guardar_en_db(alertas):
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        for a in alertas:
            cur.execute('''
                INSERT INTO alertas_amber (id, titulo, lugar, edad, url)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
            ''', (a['id'], a['titulo'], a['lugar'], a['edad'], a['url']))
        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ Guardadas {len(alertas)} alertas.")
    except Exception as e:
        print(f"❌ Error al guardar en la base de datos: {e}")

if __name__ == "__main__":
    print(f"\n🕒 Ejecución iniciada: {datetime.now(timezone.utc).isoformat()}")
    init_db()
    alertas = scrape_alertas()
    if alertas:
        guardar_en_db(alertas)
    else:
        print("📭 No hay nuevas alertas.")
    print("🔚 Ejecución finalizada.\n")
