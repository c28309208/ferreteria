"""
truper_parser.py
Parser del catálogo Truper en PDF.
Extrae: Código, Clave, Precio Público.
"""

import re
import subprocess


def _pdftotext_chunk(pdf_path, page_start, page_end):
    """Extrae texto de un rango de páginas usando pdftotext."""
    try:
        result = subprocess.run(
            ['pdftotext', '-f', str(page_start), '-l', str(page_end), '-layout', pdf_path, '-'],
            capture_output=True, text=True, timeout=60
        )
        return result.stdout
    except Exception as e:
        print(f"Error pdftotext páginas {page_start}-{page_end}: {e}")
        return ''


def _get_total_pages(pdf_path):
    """Obtiene el total de páginas del PDF."""
    try:
        result = subprocess.run(['pdfinfo', pdf_path], capture_output=True, text=True, timeout=15)
        m = re.search(r'Pages:\s+(\d+)', result.stdout)
        return int(m.group(1)) if m else 0
    except:
        return 0


def _parse_text_block(text):
    """
    Parsea un bloque de texto y extrae productos.
    Busca patrones de Código / Clave / Público en el mismo bloque.
    """
    products = []
    lines = text.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i]

        # Buscar línea con "Código:"
        if re.match(r'\s*C[oó]digo\s*:', line, re.IGNORECASE):
            raw_codes = re.sub(r'C[oó]digo\s*:\s*', '', line, flags=re.IGNORECASE)
            codigos = re.findall(r'(\d{4,7})', raw_codes)

            claves = []
            precios = []
            nombre = ''

            # Buscar hacia atrás el nombre del producto
            # El nombre suele ser la primera línea descriptiva antes del bloque Código/Clave
            for back in range(i - 1, max(i - 15, -1), -1):
                candidate = lines[back].strip()
                # Ignorar líneas vacías, bullets, precios, datos técnicos y referencias a imágenes
                if not candidate:
                    continue
                if candidate.startswith('-'):
                    continue
                if re.search(r'\$|\d{5,7}', candidate):
                    continue
                if re.match(r'(Clave|Código|Público|Mayoreo|Caja|Máster|Min|Contenido|Mezcla|Velocidad|Temp|Usos|Voltaje|Incluye|■|●)', candidate, re.IGNORECASE):
                    continue
                # Descartar líneas muy cortas o que parecen leyendas de imagen
                if len(candidate) < 5:
                    continue
                # Descartar si contiene solo caracteres no-léxicos o íconos
                if re.match(r'^[\W\d]+$', candidate):
                    continue
                # Descartar frases como "Ver en página X"
                if re.search(r'Ver en página|página \d', candidate, re.IGNORECASE):
                    continue
                nombre = candidate
                break

            # Buscar hacia adelante Clave y Público
            for j in range(i + 1, min(i + 20, len(lines))):
                l = lines[j]
                if re.match(r'\s*Clave\s*:', l, re.IGNORECASE):
                    raw_claves = re.sub(r'Clave\s*:\s*', '', l, flags=re.IGNORECASE)
                    claves = re.findall(r'([A-Z][A-Z0-9]{1,5}-[A-Z0-9][A-Z0-9●\-]*)', raw_claves)
                elif re.match(r'\s*P[úu]blico\s*:', l, re.IGNORECASE):
                    raw_precios = re.sub(r'P[úu]blico\s*:\s*', '', l, flags=re.IGNORECASE)
                    precios = re.findall(r'\$\s*([\d,]+)', raw_precios)
                    break  # Ya tenemos todo

            # Generar productos emparejando por posición
            for k, codigo in enumerate(codigos):
                clave = claves[k] if k < len(claves) else ''
                precio_str = precios[k].replace(',', '') if k < len(precios) else ''
                if codigo and precio_str:
                    try:
                        products.append({
                            'codigo': codigo,
                            'clave': clave,
                            'nombre': nombre,
                            'precio': float(precio_str)
                        })
                    except ValueError:
                        pass

        i += 1

    return products


def parse_pdf(pdf_path, progress_callback=None):
    """
    Procesa el PDF del catálogo Truper y retorna lista de productos.
    - Salta las primeras 19 páginas (portada, índice, introducción)
    - Extrae: Código, Clave, Precio Público
    - Usa la Clave como nombre si no se puede obtener uno limpio
    progress_callback(porcentaje) se llama con 0-100 si se proporciona.
    """
    total = _get_total_pages(pdf_path)
    if not total:
        return []

    # Las páginas 1-19 son portada/índice, los productos empiezan en la 20
    pagina_inicio = 20
    all_products = {}
    chunk = 20
    pages_to_process = total - pagina_inicio + 1
    chunks_total = max(1, (pages_to_process + chunk - 1) // chunk)

    for idx, start in enumerate(range(pagina_inicio, total + 1, chunk)):
        end = min(start + chunk - 1, total)
        text = _pdftotext_chunk(pdf_path, start, end)
        for p in _parse_text_block(text):
            codigo = p['codigo']
            clave  = p['clave']

            # Si no hay nombre útil, usar la Clave como nombre provisional
            nombre = p['nombre'].strip()
            # Descartar nombres que claramente son texto de layout (muy largos o con símbolos raros)
            if not nombre or len(nombre) > 80 or '■' in nombre or '●' in nombre:
                nombre = clave  # la clave ES el identificador único de Truper

            p['nombre'] = nombre

            # Guardar (preferir el que tenga mejor nombre)
            if codigo not in all_products:
                all_products[codigo] = p
            elif nombre != clave and all_products[codigo]['nombre'] == clave:
                all_products[codigo] = p

        if progress_callback:
            progress_callback(int((idx + 1) / chunks_total * 100))

    return list(all_products.values())
