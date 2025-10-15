import os
import requests
from bs4 import BeautifulSoup
import psycopg2
from datetime import datetime, timezone
import re

# Railway inyecta DATABASE_URL automáticamente
DATABASE_URL = os.environ.get("DATABASE_URL")

def init_db():
    """Crea la tabla si no existe"""
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS alertas_amber (
            id TEXT PRIMARY KEY,
            titulo TEXT,
            contenido TEXT,
            edad INTEGER,
            lugar TEXT,
            fecha_desaparicion DATE,
            url TEXT,
            fecha_extraccion TIMESTAMP DEFAULT NOW()
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()

def extraer_edad(texto):
    match = re.search(r'(\d{1,2})\s*(?:años?|año)', texto, re.IGNORECASE)
    return int(match.group(1)) if match else None

def extraer_lugar(texto):
    # Provincias y ciudades comunes de Panamá
    lugares = [
        "Panamá", "Colón", "Chiriquí", "Veraguas", "Coclé", "Herrera", "Los Santos",
        "Darién", "Bocas del Toro", "San Miguelito", "La Chorrera", "David", "Santiago",
        "Penonomé", "Chitré", "Aguadulce", "Albrook", "Tocumen", "Arraiján"
    ]
    for lugar in lugares:
        if lugar.lower() in texto.lower():
            return lugar
    return "Desconocido"

def scrape_alertas():
    """Scraping de la web oficial del Ministerio Público de Panamá"""
    url_base = "https://www.mp.gob.pa"
    alertas_url = f"{url_base}/category/alerta-amber/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; InvestigacionDesaparecidos/1.0; +tuemail@institucion.edu)'
    }
    
    try:
        print("📡 Conectando al Ministerio Público de Panamá...")
        resp = requests.get(alertas_url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"❌ Error al acceder a la web: {e}")
        return []

    soup = BeautifulSoup(resp.content, 'html.parser')
    posts = soup.select('article.post')  # Ajustar si la web cambia

    if not posts:
        print("⚠️ No se encontraron artículos. Revisa la estructura HTML.")
        return []

    alertas = []
    for post in posts:
        link_tag = post.select_one('h2 a') or post.select_one('a')
        if not link_tag:
            continue

        url = link_tag['href']
        if not url.startswith('http'):
            url = url_base + url

        titulo = link_tag.get_text(strip=True)

        # Obtener contenido de la página individual
        try:
            detail_resp = requests.get(url, headers=headers, timeout=10)
            detail_soup = BeautifulSoup(detail_resp.content, 'html.parser')
            content_div = detail_soup.select_one('div.entry-content') or detail_soup.select_one('article')
            contenido = content_div.get_text(strip=True) if content_div else titulo
        except:
            contenido = titulo

        edad = extraer_edad(contenido)
        lugar = extraer_lugar(contenido)

        # ID único: usamos la URL como identificador
        id_alerta = url.replace('https://', '').replace('http://', '').rstrip('/')

        alertas.append({
            'id': id_alerta,
            'titulo': titulo,
            'contenido': contenido[:1000],
            'edad': edad,
            'lugar': lugar,
            'fecha_desaparicion': datetime.now(timezone.utc).date(),
            'url': url
        })

    print(f"✅ Se encontraron {len(alertas)} alertas.")
    return alertas

def guardar_en_db(alertas):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    for a in alertas:
        cur.execute('''
            INSERT INTO alertas_amber (id, titulo, contenido, edad, lugar, fecha_desaparicion, url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        ''', (
            a['id'], a['titulo'], a['contenido'], a['edad'],
            a['lugar'], a['fecha_desaparicion'], a['url']
        ))
    conn.commit()
    cur.close()
    conn.close()
    print(f"💾 {len(alertas)} alertas guardadas en la base de datos.")

if __name__ == "__main__":
    print(f"\n🕒 Ejecución iniciada: {datetime.now(timezone.utc).isoformat()}")
    init_db()
    alertas = scrape_alertas()
    if alertas:
        guardar_en_db(alertas)
    else:
        print("📭 No hay nuevas alertas.")
    print("🔚 Ejecución finalizada.\n")
