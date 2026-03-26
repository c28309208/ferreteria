import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
import os
import json
import io

# Google Drive para imágenes
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds_json = os.environ.get('CREDENCIALES')
if creds_json:
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
else:
    creds = ServiceAccountCredentials.from_json_keyfile_name('credenciales.json', scope)

client = gspread.authorize(creds)

SHEET_ID = '1QdlBw-SsuvmhuCuex3RtXjUtkrO_nLJELQHVVYEfSfE'

# ── Google Drive para imágenes ──
_drive_service = None
_carpeta_imagenes_id = None
CARPETA_NOMBRE = 'Tlapaleria_Imagenes'

def _get_drive():
    global _drive_service
    if _drive_service is None:
        _drive_service = build('drive', 'v3', credentials=creds)
    return _drive_service

def _get_carpeta_imagenes():
    """Obtiene o crea la carpeta de imágenes en Google Drive."""
    global _carpeta_imagenes_id
    if _carpeta_imagenes_id:
        return _carpeta_imagenes_id
    drive = _get_drive()
    # Buscar carpeta existente
    res = drive.files().list(
        q=f"name='{CARPETA_NOMBRE}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields='files(id)'
    ).execute()
    archivos = res.get('files', [])
    if archivos:
        _carpeta_imagenes_id = archivos[0]['id']
    else:
        # Crear carpeta
        meta = {'name': CARPETA_NOMBRE, 'mimeType': 'application/vnd.google-apps.folder'}
        folder = drive.files().create(body=meta, fields='id').execute()
        _carpeta_imagenes_id = folder['id']
        # Hacer la carpeta pública para lectura
        drive.permissions().create(
            fileId=_carpeta_imagenes_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
    return _carpeta_imagenes_id

def subir_imagen_drive(file_bytes, filename, mimetype='image/jpeg'):
    """
    Sube una imagen a Google Drive y devuelve la URL pública.
    """
    try:
        drive = _get_drive()
        carpeta_id = _get_carpeta_imagenes()
        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mimetype, resumable=False)
        meta = {'name': filename, 'parents': [carpeta_id]}
        archivo = drive.files().create(body=meta, media_body=media, fields='id').execute()
        file_id = archivo['id']
        # Hacer el archivo público
        drive.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        # URL directa para mostrar en img src
        url = f'https://drive.google.com/thumbnail?id={file_id}&sz=w400'
        return {'ok': True, 'url': url, 'id': file_id}
    except Exception as e:
        return {'error': str(e)}

cache_productos = []
cache_tiempo = 0
CACHE_SEGUNDOS = 60

def get_sheet_productos():
    sheet = client.open_by_key(SHEET_ID)
    return sheet.sheet1

def get_sheet_ventas():
    sheet = client.open_by_key(SHEET_ID)
    return sheet.worksheet('Ventas')

def get_sheet_proveedores():
    sheet = client.open_by_key(SHEET_ID)
    return sheet.worksheet('Proveedores')

def get_sheet_usuarios():
    sheet = client.open_by_key(SHEET_ID)
    try:
        return sheet.worksheet('usuarios')
    except:
        ws = sheet.add_worksheet(title='usuarios', rows=100, cols=5)
        ws.append_row(['usuario', 'password_hash', 'rol', 'nombre', 'activo'])
        return ws

def get_sheet_logs():
    sheet = client.open_by_key(SHEET_ID)
    try:
        return sheet.worksheet('Logs')
    except:
        ws = sheet.add_worksheet(title='Logs', rows=5000, cols=4)
        ws.append_row(['Fecha', 'Usuario', 'Accion', 'Detalle'])
        return ws

# ─────────────────────────────────────────
# PRODUCTOS
# ─────────────────────────────────────────

def get_productos():
    global cache_productos, cache_tiempo
    ahora = time.time()
    if cache_productos and (ahora - cache_tiempo) < CACHE_SEGUNDOS:
        return cache_productos
    try:
        sheet = get_sheet_productos()
        cache_productos = sheet.get_all_records()
        cache_tiempo = ahora
    except Exception as e:
        print(f"Error al obtener productos: {e}")
        if not cache_productos:
            return []
    return cache_productos

def buscar_producto(query):
    productos = get_productos()
    query = query.lower()
    return [p for p in productos if query in str(p.get('nombre', '')).lower()]

def crear_producto(data):
    global cache_productos, cache_tiempo
    try:
        sheet = get_sheet_productos()
        todos = sheet.get_all_records()
        nuevo_id = max([int(r.get('id', 0)) for r in todos], default=0) + 1
        sheet.append_row([nuevo_id, data.get('nombre', ''), float(data.get('precio', 0)), int(data.get('stock', 0)), int(data.get('minimo', 5))])
        cache_productos = []
        cache_tiempo = 0
        return {'ok': True, 'id': nuevo_id}
    except Exception as e:
        return {'error': str(e)}

def actualizar_producto(id, data):
    global cache_productos, cache_tiempo
    try:
        sheet = get_sheet_productos()
        records = sheet.get_all_records()
        fila_num = None
        producto_actual = None
        for i, r in enumerate(records):
            if str(r.get('id')) == str(id):
                fila_num = i + 2
                producto_actual = r
                break
        if not fila_num:
            return {'error': 'Producto no encontrado'}
        sheet.update(f'A{fila_num}:E{fila_num}', [[id, data.get('nombre', producto_actual.get('nombre', '')), float(data.get('precio', producto_actual.get('precio', 0))), int(data.get('stock', producto_actual.get('stock', 0))), int(data.get('minimo', producto_actual.get('minimo', 5)))]])
        cache_productos = []
        cache_tiempo = 0
        return {'ok': True}
    except Exception as e:
        return {'error': str(e)}

def eliminar_producto(id):
    global cache_productos, cache_tiempo
    try:
        sheet = get_sheet_productos()
        records = sheet.get_all_records()
        fila_num = None
        for i, r in enumerate(records):
            if str(r.get('id')) == str(id):
                fila_num = i + 2
                break
        if not fila_num:
            return {'error': 'Producto no encontrado'}
        sheet.delete_rows(fila_num)
        cache_productos = []
        cache_tiempo = 0
        return {'ok': True}
    except Exception as e:
        return {'error': str(e)}

# ─────────────────────────────────────────
# VENTAS
# ─────────────────────────────────────────

def get_reporte(filtro='hoy'):
    try:
        sheet = get_sheet_ventas()
        registros = sheet.get_all_records()
    except Exception as e:
        return {'error': f'Error al obtener reporte: {e}'}

    hoy = datetime.now(ZoneInfo('America/Mexico_City'))

    if filtro == 'hoy':
        fecha_desde = hoy.strftime('%d/%m/%Y')
        ventas_filtradas = [r for r in registros if str(r.get('Fecha', '')).startswith(fecha_desde)]
    elif filtro == 'semana':
        hace_7_dias = hoy - timedelta(days=7)
        ventas_filtradas = []
        for r in registros:
            try:
                fecha_venta = datetime.strptime(str(r.get('Fecha', ''))[:10], '%d/%m/%Y')
                if fecha_venta >= hace_7_dias:
                    ventas_filtradas.append(r)
            except:
                pass
    elif filtro == 'mes':
        mes_actual = hoy.strftime('%m/%Y')
        ventas_filtradas = [r for r in registros if str(r.get('Fecha', ''))[3:10] == mes_actual]
    else:
        ventas_filtradas = registros

    total_vendido = sum(float(r.get('Subtotal', 0)) for r in ventas_filtradas)
    num_tickets = len(set(str(r.get('Ticket', '')) for r in ventas_filtradas))

    productos_vendidos = {}
    for r in ventas_filtradas:
        nombre = r.get('Producto', 'Desconocido')
        try:
            cantidad = int(r.get('Cantidad', 0))
        except:
            cantidad = 0
        productos_vendidos[nombre] = productos_vendidos.get(nombre, 0) + cantidad

    top_productos = sorted(productos_vendidos.items(), key=lambda x: x[1], reverse=True)[:5]

    metodos = {}
    for r in ventas_filtradas:
        m = str(r.get('Metodo_pago', 'desconocido'))
        try:
            metodos[m] = metodos.get(m, 0) + float(r.get('Subtotal', 0))
        except:
            pass

    return {
        'total_vendido': round(total_vendido, 2),
        'num_tickets': num_tickets,
        'num_productos': len(ventas_filtradas),
        'top_productos': top_productos,
        'metodos': metodos,
        'ventas': ventas_filtradas
    }

def procesar_venta(data):
    global cache_productos, cache_tiempo
    items = data.get('items', [])
    metodo = data.get('metodo', 'efectivo')
    if not items:
        return {'error': 'No hay productos en la venta'}
    try:
        productos = get_productos()
        sheet_productos = get_sheet_productos()
        sheet_ventas = get_sheet_ventas()
    except Exception as e:
        return {'error': f'Error de conexión con Google Sheets: {e}'}

    for item in items:
        producto_id = item.get('id')
        cantidad = item.get('cantidad', 0)
        producto = next((p for p in productos if str(p.get('id')) == str(producto_id)), None)
        if not producto:
            return {'error': f'Producto con ID {producto_id} no encontrado'}
        if int(producto.get('stock', 0)) < cantidad:
            return {'error': f"Stock insuficiente: {producto['nombre']} (disponible: {producto.get('stock', 0)})"}

    try:
        todas_ventas = sheet_ventas.get_all_records()
        tickets_unicos = set(str(r.get('Ticket', '')) for r in todas_ventas if r.get('Ticket'))
        num_ticket = len(tickets_unicos) + 1
    except:
        num_ticket = int(time.time())

    fecha_hora = datetime.now(ZoneInfo('America/Mexico_City')).strftime('%d/%m/%Y %H:%M')
    all_rows = sheet_productos.get_all_values()

    total = sum(float(next((p for p in productos if str(p.get('id')) == str(item.get('id'))), {}).get('precio', 0)) * item.get('cantidad', 0) for item in items)

    detalle = []
    for item in items:
        producto = next((p for p in productos if str(p.get('id')) == str(item.get('id'))), None)
        if producto:
            cantidad = item.get('cantidad', 0)
            subtotal = float(producto['precio']) * cantidad
            for i, row in enumerate(all_rows):
                if row[0] == str(producto.get('id')):
                    sheet_productos.update_cell(i + 1, 4, int(producto.get('stock', 0)) - cantidad)
                    break
            sheet_ventas.append_row([fecha_hora, f'#{num_ticket:04d}', producto['nombre'], cantidad, float(producto['precio']), subtotal, round(total, 2), metodo])
            detalle.append({'nombre': producto['nombre'], 'cantidad': cantidad, 'precio': float(producto['precio']), 'subtotal': subtotal})

    cache_productos = []
    cache_tiempo = 0
    return {'id': num_ticket, 'items': detalle, 'total': round(total, 2)}

# ─────────────────────────────────────────
# PROVEEDORES
# ─────────────────────────────────────────

def get_proveedores():
    try:
        sheet = get_sheet_proveedores()
        registros = sheet.get_all_records()
        for i, r in enumerate(registros):
            r['id'] = i + 1
        return {'proveedores': registros}
    except Exception as e:
        return {'proveedores': [], 'error': str(e)}

def crear_proveedor(data):
    try:
        sheet = get_sheet_proveedores()
        sheet.append_row([data.get('proveedor', ''), data.get('producto', ''), data.get('monto', 0), data.get('fecha_vencimiento', ''), data.get('estado', 'Pendiente'), data.get('notas', '')])
        return {'ok': True}
    except Exception as e:
        return {'error': str(e)}

def actualizar_proveedor(id, data):
    try:
        sheet = get_sheet_proveedores()
        registros = sheet.get_all_records()
        if id < 1 or id > len(registros):
            return {'error': 'Proveedor no encontrado'}
        actual = registros[id - 1]
        fila = id + 1
        sheet.update(f'A{fila}:F{fila}', [[data.get('proveedor', actual.get('proveedor', '')), data.get('producto', actual.get('producto', '')), data.get('monto', actual.get('monto', 0)), data.get('fecha_vencimiento', actual.get('fecha_vencimiento', '')), data.get('estado', actual.get('estado', 'Pendiente')), data.get('notas', actual.get('notas', ''))]])
        return {'ok': True}
    except Exception as e:
        return {'error': str(e)}

def eliminar_proveedor(id):
    try:
        sheet = get_sheet_proveedores()
        sheet.delete_rows(id + 1)
        return {'ok': True}
    except Exception as e:
        return {'error': str(e)}

# ─────────────────────────────────────────
# USUARIOS
# ─────────────────────────────────────────

def _hash(password):
    import hashlib
    salt = os.environ.get('SECRET_KEY', 'tlapaleria2026')
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

def verificar_login(usuario, password):
    try:
        sheet = get_sheet_usuarios()
        registros = sheet.get_all_records()
        hash_calculado = _hash(password)
        print(f"DEBUG: usuario='{usuario}' hash='{hash_calculado[:10]}...'")
        for r in registros:
            hash_guardado = str(r.get('password_hash', '')).strip()
            print(f"DEBUG: comparando con '{r.get('usuario')}' coincide={hash_guardado == hash_calculado}")
            if str(r.get('usuario', '')).lower() == usuario.lower():
                if str(r.get('activo', '1')) in ('0', 0, False, 'False', 'false'):
                    return None
                if hash_guardado == hash_calculado:
                    return {'rol': r.get('rol', 'empleado'), 'nombre': r.get('nombre', usuario)}
        return None
    except Exception as e:
        print(f"Error verificar_login: {e}")
        return None

def get_usuarios():
    try:
        sheet = get_sheet_usuarios()
        registros = sheet.get_all_records()
        return [{'usuario': r['usuario'], 'rol': r.get('rol', 'empleado'), 'nombre': r.get('nombre', ''), 'activo': r.get('activo', 1)} for r in registros]
    except:
        return []

def crear_usuario(data):
    try:
        usuario = data.get('usuario', '').strip().lower()
        password = data.get('password', '')
        rol = data.get('rol', 'empleado')
        nombre = data.get('nombre', usuario)
        if not usuario or not password:
            return {'error': 'Usuario y contraseña son obligatorios'}
        sheet = get_sheet_usuarios()
        existentes = sheet.get_all_records()
        if any(str(r.get('usuario', '')).lower() == usuario for r in existentes):
            return {'error': 'El usuario ya existe'}
        sheet.append_row([usuario, _hash(password), rol, nombre, 1])
        return {'ok': True}
    except Exception as e:
        return {'error': str(e)}

def eliminar_usuario(usuario):
    try:
        sheet = get_sheet_usuarios()
        registros = sheet.get_all_records()
        for i, r in enumerate(registros):
            if str(r.get('usuario', '')).lower() == usuario.lower():
                if r.get('rol') == 'admin':
                    return {'error': 'No puedes eliminar al admin'}
                sheet.delete_rows(i + 2)
                return {'ok': True}
        return {'error': 'Usuario no encontrado'}
    except Exception as e:
        return {'error': str(e)}

def cambiar_password(usuario, nueva_password):
    try:
        if not nueva_password or len(nueva_password) < 4:
            return {'error': 'La contraseña debe tener al menos 4 caracteres'}
        sheet = get_sheet_usuarios()
        registros = sheet.get_all_records()
        for i, r in enumerate(registros):
            if str(r.get('usuario', '')).lower() == usuario.lower():
                sheet.update_cell(i + 2, 2, _hash(nueva_password))
                return {'ok': True}
        return {'error': 'Usuario no encontrado'}
    except Exception as e:
        return {'error': str(e)}

# ─────────────────────────────────────────
# TRUPER CATÁLOGO
# ─────────────────────────────────────────

def get_sheet_truper():
    sheet = client.open_by_key(SHEET_ID)
    try:
        return sheet.worksheet('Truper')
    except:
        ws = sheet.add_worksheet(title='Truper', rows=5000, cols=5)
        ws.append_row(['codigo', 'clave', 'nombre', 'precio_catalogo', 'ultima_actualizacion'])
        return ws

def guardar_catalogo_truper(productos, fecha):
    """Guarda o actualiza el catálogo Truper en Google Sheets."""
    try:
        ws = get_sheet_truper()
        registros = ws.get_all_records()
        existentes = {str(r.get('codigo', '')): i + 2 for i, r in enumerate(registros)}

        nuevos = []
        actualizados = 0
        for p in productos:
            codigo = str(p.get('codigo', ''))
            if not codigo:
                continue
            row = [codigo, p.get('clave', ''), p.get('nombre', ''), p.get('precio', 0), fecha]
            if codigo in existentes:
                fila = existentes[codigo]
                ws.update(f'A{fila}:E{fila}', [row])
                actualizados += 1
            else:
                nuevos.append(row)

        if nuevos:
            ws.append_rows(nuevos)

        return {'ok': True, 'nuevos': len(nuevos), 'actualizados': actualizados, 'total': len(productos)}
    except Exception as e:
        return {'error': str(e)}

def get_catalogo_truper():
    """Retorna el catálogo Truper con info de stock del inventario."""
    try:
        ws = get_sheet_truper()
        catalogo = ws.get_all_records()
        inventario = get_productos()
        # Índice de inventario por clave truper y por nombre similar
        inv_por_clave = {str(p.get('clave_truper', '')).upper(): p for p in inventario if p.get('clave_truper')}

        for item in catalogo:
            clave = str(item.get('clave', '')).upper()
            inv = inv_por_clave.get(clave)
            if inv:
                item['en_inventario'] = True
                item['stock'] = inv.get('stock', 0)
                item['precio_venta'] = inv.get('precio', 0)
                item['inv_id'] = inv.get('id', '')
            else:
                item['en_inventario'] = False
                item['stock'] = 0
                item['precio_venta'] = 0
                item['inv_id'] = ''

        return catalogo
    except Exception as e:
        return []

def _asegurar_columnas_truper(sheet):
    """Asegura que la hoja de productos tenga columnas clave_truper e imagen."""
    headers = sheet.row_values(1)
    changed = False
    if 'clave_truper' not in headers:
        sheet.update_cell(1, len(headers) + 1, 'clave_truper')
        headers.append('clave_truper')
        changed = True
    if 'imagen' not in headers:
        sheet.update_cell(1, len(headers) + 1, 'imagen')
        headers.append('imagen')
        changed = True
    return headers

def sincronizar_inventario_desde_truper(productos):
    """
    Sincronización automática completa:
    - Productos que ya existen en inventario por clave_truper → actualiza precio
    - Productos nuevos → los agrega al inventario con precio del catálogo
    Retorna dict con conteos.
    """
    global cache_productos, cache_tiempo
    try:
        sheet = get_sheet_productos()
        todos = sheet.get_all_records()
        headers = _asegurar_columnas_truper(sheet)

        col_precio = headers.index('precio') + 1 if 'precio' in headers else 3
        col_clave_truper = headers.index('clave_truper') + 1 if 'clave_truper' in headers else len(headers)

        # Índice de inventario por clave_truper → fila
        inv_por_clave = {}
        for i, r in enumerate(todos):
            ct = str(r.get('clave_truper', '')).upper().strip()
            if ct:
                inv_por_clave[ct] = {'fila': i + 2, 'record': r}

        actualizados = 0
        nuevos_rows = []
        max_id = max([int(r.get('id', 0)) for r in todos], default=0)

        for p in productos:
            clave = str(p.get('clave', '')).upper().strip()
            precio = float(p.get('precio', 0))
            if not clave or not precio:
                continue

            if clave in inv_por_clave:
                # Actualizar precio en inventario existente
                fila = inv_por_clave[clave]['fila']
                sheet.update_cell(fila, col_precio, precio)
                actualizados += 1
            else:
                # Producto nuevo → preparar para inserción masiva
                max_id += 1
                nombre = p.get('nombre', '') or clave
                nuevos_rows.append([max_id, nombre, precio, 0, 5, p.get('clave', ''), ''])
                inv_por_clave[clave] = {'fila': None, 'record': {}}  # evitar duplicados

        # Insertar todos los nuevos de una sola vez (más eficiente)
        if nuevos_rows:
            sheet.append_rows(nuevos_rows)

        cache_productos = []
        cache_tiempo = 0
        return {'ok': True, 'actualizados': actualizados, 'nuevos': len(nuevos_rows), 'total': len(productos)}
    except Exception as e:
        return {'error': str(e)}

def agregar_desde_truper(data):
    """Agrega manualmente un producto Truper individual al inventario."""
    global cache_productos, cache_tiempo
    try:
        sheet = get_sheet_productos()
        todos = sheet.get_all_records()

        # Verificar si ya existe por clave_truper
        for r in todos:
            if str(r.get('clave_truper', '')).upper() == str(data.get('clave', '')).upper():
                return {'error': 'Este producto Truper ya está en el inventario'}

        _asegurar_columnas_truper(sheet)
        nuevo_id = max([int(r.get('id', 0)) for r in todos], default=0) + 1
        nombre = data.get('nombre') or data.get('clave', '')
        precio = float(data.get('precio', 0))
        stock = int(data.get('stock', 0))
        minimo = int(data.get('minimo', 5))
        clave_truper = data.get('clave', '')
        imagen = data.get('imagen', '')

        sheet.append_row([nuevo_id, nombre, precio, stock, minimo, clave_truper, imagen])
        cache_productos = []
        cache_tiempo = 0
        return {'ok': True, 'id': nuevo_id}
    except Exception as e:
        return {'error': str(e)}

# ─────────────────────────────────────────
# IMÁGENES DE PRODUCTOS
# ─────────────────────────────────────────

def actualizar_imagen_producto(id, imagen_url):
    """Actualiza la URL de imagen de un producto en Google Sheets."""
    global cache_productos, cache_tiempo
    try:
        sheet = get_sheet_productos()
        all_values = sheet.get_all_values()
        headers = all_values[0] if all_values else []

        # Obtener o crear columna imagen
        if 'imagen' not in headers:
            col_imagen = len(headers) + 1
            if 'clave_truper' not in headers:
                sheet.update_cell(1, len(headers) + 1, 'clave_truper')
                col_imagen = len(headers) + 2
            sheet.update_cell(1, col_imagen, 'imagen')
            # Re-leer headers
            all_values = sheet.get_all_values()
            headers = all_values[0]

        col_imagen = headers.index('imagen') + 1

        for i, row in enumerate(all_values[1:], start=2):
            if str(row[0]) == str(id):
                sheet.update_cell(i, col_imagen, imagen_url)
                cache_productos = []
                cache_tiempo = 0
                return {'ok': True}

        return {'error': 'Producto no encontrado'}
    except Exception as e:
        return {'error': str(e)}

# ─────────────────────────────────────────
# LOGS
# ─────────────────────────────────────────

def registrar_log(usuario, accion, detalle=''):
    try:
        sheet = get_sheet_logs()
        fecha = datetime.now(ZoneInfo('America/Mexico_City')).strftime('%d/%m/%Y %H:%M:%S')
        sheet.append_row([fecha, usuario, accion, str(detalle)])
    except Exception as e:
        print(f"Error log: {e}")

def get_logs():
    try:
        sheet = get_sheet_logs()
        registros = sheet.get_all_records()
        return list(reversed(registros))
    except:
        return []
