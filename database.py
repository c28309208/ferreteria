import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
import os
import json

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
        return sheet.worksheet('Usuarios')
    except:
        ws = sheet.add_worksheet(title='Usuarios', rows=100, cols=5)
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
        print(f"DEBUG: buscando usuario '{usuario}', registros: {len(registros)}")
        for r in registros:
            print(f"DEBUG: comparando con '{r.get('usuario')}', hash_guardado={str(r.get('password_hash',''))[:10]}..., hash_calculado={_hash(password)[:10]}...")
            if str(r.get('usuario', '')).lower() == usuario.lower():
                if str(r.get('activo', '1')) in ('0', 0, False, 'False', 'false'):
                    return None
                if r.get('password_hash') == _hash(password):
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
