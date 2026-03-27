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


def _extract_column_text(lines, line_idx, col_start, col_end):
    """
    Extrae texto de una columna específica en una línea.
    col_start y col_end son posiciones de caracteres en la línea.
    Los rangos ya están calculados con puntos medios entre columnas.
    """
    if line_idx < 0 or line_idx >= len(lines):
        return ''
    raw = lines[line_idx]
    cs = max(0, col_start)
    ce = min(len(raw), col_end)
    return raw[cs:ce].strip()


def _is_skip_line(segment):
    """Determina si un segmento de texto debe saltarse al buscar nombres."""
    if not segment or len(segment) < 3:
        return True
    # Viñetas
    if segment.startswith('-'):
        return True
    # Precios o códigos largos
    if re.search(r'\$|\d{5,7}', segment):
        return True
    # Etiquetas técnicas conocidas
    if re.match(r'(Clave|C[oó]digo|P[úu]blico|Mayoreo|Caja|M[áa]ster|Min|Contenido'
                r'|Mezcla|Velocidad|Temp|Usos|Voltaje|Incluye[n]?|Cumple|Conexi[oó]n'
                r'|Di[áa]metro|NOM-|NC\s|Cal\.|Liso|Anillado|Tornillo|Collar|Seguro'
                r'|Sistema|Regulador|Gatillo|Video|Refacciones|Corona|Espesor|Largo'
                r'|Nueva imagen|CONTENIDO|Soporte|Bisagras|Pernos|Cuchillas)',
                segment, re.IGNORECASE):
        return True
    # Solo símbolos/números
    if re.match(r'^[\W\d]+$', segment):
        return True
    # Ver en página
    if re.search(r'Ver en p[áa]gina|p[áa]gina \d', segment, re.IGNORECASE):
        return True
    # Disclaimers / pie de página
    if re.search(r'Los precios de este|PROMOTRUPER|mejora continua|presentaci[oó]n del cat[áa]logo'
                 r'|se seguir[áa] surtiendo|agotar existencias', segment, re.IGNORECASE):
        return True
    # Medidas sueltas
    if re.match(r'^[\d\s/.,]*(cm|mm|oz|ml|kg|lb|m|L|pulgadas?|"|°|ºC)\)?$', segment, re.IGNORECASE):
        return True
    # Líneas que empiezan en minúscula = continuaciones, no encabezados
    first_alpha = ''
    for ch in segment:
        if ch.isalpha():
            first_alpha = ch
            break
    if first_alpha and first_alpha.islower():
        return True
    return False


def _is_bullet_in_context(lines, line_idx, col_start):
    """
    Verifica si la línea tiene un guion/viñeta cerca del inicio de la columna.
    En layout multi-columna, el '-' puede estar unos caracteres antes del col_start.
    """
    if line_idx < 0 or line_idx >= len(lines):
        return False
    raw = lines[line_idx]
    # Revisar desde 15 chars antes del col_start hasta col_start+5
    check_start = max(0, col_start - 15)
    check_end = min(len(raw), col_start + 10)
    prefix = raw[check_start:check_end]
    # Si hay un '-' precedido solo por espacios en esa zona, es viñeta
    stripped = prefix.lstrip()
    if stripped.startswith('-'):
        return True
    return False


def _find_product_name(lines, codigo_line_idx, col_start, col_end):
    """
    Busca el nombre de producto en una columna específica,
    buscando hacia atrás desde la línea de Código.
    Usa posiciones de columna para aislar el texto correcto
    en layouts multi-columna de pdftotext.
    """
    # Recopilar todos los candidatos válidos con su posición
    candidatos = []
    for back in range(codigo_line_idx - 1, max(codigo_line_idx - 35, -1), -1):
        segment = _extract_column_text(lines, back, col_start, col_end)

        if _is_skip_line(segment):
            continue

        # Verificar si es una viñeta mirando el contexto amplio de la línea
        if _is_bullet_in_context(lines, back, col_start):
            continue

        candidatos.append((back, segment))

    if not candidatos:
        return ''

    # Preferir el candidato que tiene viñetas "-" después de él en la misma columna.
    # Ese es el verdadero encabezado del producto. Los callouts como
    # "Baja tensión superficial..." aparecen después de las viñetas.
    mejor = candidatos[0]  # fallback: el más cercano al Código
    for back, segment in candidatos:
        # Revisar las siguientes 3 líneas en la columna buscando viñetas
        tiene_viñetas = False
        for fwd in range(back + 1, min(back + 5, codigo_line_idx)):
            if _is_bullet_in_context(lines, fwd, col_start):
                tiene_viñetas = True
                break
            fwd_seg = _extract_column_text(lines, fwd, col_start, col_end)
            # Si es una línea en minúscula podría ser continuación del nombre, seguir buscando
            if fwd_seg:
                ffa = ''
                for ch in fwd_seg:
                    if ch.isalpha():
                        ffa = ch
                        break
                if ffa and ffa.isupper():
                    break  # Otra línea con mayúscula = no es continuación
        if tiene_viñetas:
            mejor = (back, segment)
            break  # Este es el verdadero encabezado

    back, nombre = mejor

    # Capturar continuación en la línea siguiente (ej: "PTFE" + "en aerosol")
    if back + 1 < codigo_line_idx:
        next_seg = _extract_column_text(lines, back + 1, col_start, col_end)
        if next_seg and len(next_seg) < 40:
            nf = ''
            for ch in next_seg:
                if ch.isalpha():
                    nf = ch
                    break
            if nf and nf.islower():
                if not re.match(r'(Incluye|Clave|C[oó]digo|P[úu]blico|Mayoreo|Contenido|Temp|Usos)', next_seg, re.IGNORECASE):
                    nombre = nombre + ' ' + next_seg

    return nombre


def _parse_text_block(text):
    """
    Parsea un bloque de texto y extrae productos.
    Usa detección de columnas basada en posiciones de caracteres
    para manejar correctamente el layout multi-columna de pdftotext.
    """
    products = []
    lines = text.split('\n')

    i = 0
    while i < len(lines):
        line = lines[i]

        # Buscar línea con "Código:"
        if re.match(r'\s*C[oó]digo\s*:', line, re.IGNORECASE):
            # Encontrar posición y valor de cada código en la línea
            code_matches = list(re.finditer(r'(\d{4,7})', line))
            if not code_matches:
                i += 1
                continue

            codigos = [m.group() for m in code_matches]
            col_positions = [m.start() for m in code_matches]

            # Calcular rangos de columna usando puntos medios entre códigos.
            # Los códigos suelen estar centrados/derechos en su columna,
            # pero el nombre está alineado a la izquierda, así que usamos
            # el punto medio entre códigos adyacentes como límite.
            col_ranges = []
            for k in range(len(col_positions)):
                if k == 0:
                    cs = 0
                else:
                    # Punto medio entre este código y el anterior
                    cs = (col_positions[k - 1] + col_positions[k]) // 2

                if k + 1 < len(col_positions):
                    ce = (col_positions[k] + col_positions[k + 1]) // 2
                else:
                    ce = max(len(line), col_positions[k] + 60)
                col_ranges.append((cs, ce))

            # Buscar Clave y Público en líneas siguientes
            claves_line = ''
            precios_line = ''
            for j in range(i + 1, min(i + 20, len(lines))):
                l = lines[j]
                if re.match(r'\s*Clave\s*:', l, re.IGNORECASE):
                    claves_line = l
                elif re.match(r'\s*P[úu]blico\s*:', l, re.IGNORECASE):
                    precios_line = l
                    break

            # Extraer claves por posición de columna
            all_claves = list(re.finditer(r'([A-Z][A-Z0-9]{1,5}-[A-Z0-9][A-Z0-9●\-]*)', claves_line))
            # Extraer precios por posición de columna
            all_precios = list(re.finditer(r'\$\s*([\d,]+)', precios_line))

            # Para cada código, encontrar su clave, precio y nombre por columna
            for k, codigo in enumerate(codigos):
                col_start, col_end = col_ranges[k]

                # Buscar clave dentro del rango de columna
                clave = ''
                for cm in all_claves:
                    if col_start - 10 <= cm.start() <= col_end + 10:
                        clave = cm.group()
                        break

                # Buscar precio dentro del rango de columna
                precio_str = ''
                for pm in all_precios:
                    if col_start - 10 <= pm.start() <= col_end + 10:
                        precio_str = pm.group(1).replace(',', '')
                        break

                if not codigo or not precio_str:
                    continue

                # Buscar nombre del producto en la columna correcta
                nombre = _find_product_name(lines, i, col_start, col_end)

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

            # Limpiar y validar el nombre extraído
            nombre = p['nombre'].strip()
            # Eliminar espacios múltiples internos (residuos de multi-columna)
            nombre = re.sub(r'\s{3,}', ' ', nombre)
            # Descartar nombres que claramente son texto de layout
            es_malo = False
            if not nombre or len(nombre) > 80 or '■' in nombre or '●' in nombre:
                es_malo = True
            # Nombres que contienen datos técnicos mezclados (residuos de columnas)
            elif re.search(r'MM\s*00|NC\s*\d|oz\)|ml\)', nombre):
                es_malo = True
            # Nombres que son disclaimers parciales
            elif re.search(r'presentaci[oó]n|cat[áa]logo|surtiendo|existencias|PROMOTRUPER', nombre, re.IGNORECASE):
                es_malo = True
            # Nombres demasiado cortos (probablemente truncados)
            elif len(nombre) < 4:
                es_malo = True
            if es_malo:
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
