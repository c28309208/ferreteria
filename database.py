import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

import os
import json

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

# ─────────────────────────────────────────
# HOJAS
# ─────────────────────────────────────────

def get_sheet_productos():
    sheet = client.open_by_key(SHEET_ID)
    return sheet.sheet1

def get_sheet_ventas():
    sheet = client.open_by_key(SHEET_ID)
    return sheet.worksheet('Ventas')

def get_sheet_proveedores():
    sheet = client.open_by_key(SHEET_ID)
    return sheet.worksheet('Proveedores')

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
        # Generar nuevo ID
        nuevo_id = max([int(r.get('id', 0)) for r in todos], default=0) + 1
        sheet.append_row([
            nuevo_id,
            data.get('nombre', ''),
            float(data.get('precio', 0)),
            int(data.get('stock', 0)),
            int(data.get('minimo', 5))
        ])
        cache_productos = []
        cache_tiempo = 0
        return {'ok': True, 'id': nuevo_id}
    except Exception as e:
        return {'error': str(e)}

def actualizar_producto(id, data):
    global cache_productos, cache_tiempo
    try:
        sheet = get_sheet_productos()
        todos = sheet.get_all_values()  # incluye encabezado
        fila_num = None
        producto_actual = None
        records = sheet.get_all_records()
        for i, r in enumerate(records):
            if str(r.get('id')) == str(id):
                fila_num = i + 2  # +1 encabezado, +1 base 1
                producto_actual = r
                break
        if not fila_num:
            return {'error': 'Producto no encontrado'}
        sheet.update(f'A{fila_num}:E{fila_num}', [[
            id,
            data.get('nombre', producto_actual.get('nombre', '')),
            float(data.get('precio', producto_actual.get('precio', 0))),
            int(data.get('stock', producto_actual.get('stock', 0))),
            int(data.get('minimo', producto_actual.get('minimo', 5)))
        ]])
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

    errores = []
    for item in items:
        producto_id = item.get('id')
        cantidad = item.get('cantidad', 0)
        if not producto_id:
            errores.append('Producto sin ID')
            continue
        producto = next((p for p in productos if str(p.get('id')) == str(producto_id)), None)
        if not producto:
            errores.append(f'Producto con ID {producto_id} no encontrado')
            continue
        try:
            stock_actual = int(producto.get('stock', 0))
        except:
            stock_actual = 0
        if stock_actual < cantidad:
            errores.append(f"Stock insuficiente: {producto['nombre']} (disponible: {stock_actual})")

    if errores:
        return {'error': errores[0]}

    try:
        todas_ventas = sheet_ventas.get_all_records()
        if todas_ventas:
            # Contar tickets únicos, no filas
            tickets_unicos = set(str(r.get('Ticket', '')) for r in todas_ventas if r.get('Ticket'))
            num_ticket = len(tickets_unicos) + 1
        else:
            num_ticket = 1
    except:
        num_ticket = int(time.time())

    fecha_hora = datetime.now(ZoneInfo('America/Mexico_City')).strftime('%d/%m/%Y %H:%M')
    all_rows = sheet_productos.get_all_values()

    total = 0
    for item in items:
        producto_id = item.get('id')
        cantidad = item.get('cantidad', 0)
        producto = next((p for p in productos if str(p.get('id')) == str(producto_id)), None)
        if producto:
            total += float(producto['precio']) * cantidad

    detalle = []
    for item in items:
        producto_id = item.get('id')
        cantidad = item.get('cantidad', 0)
        producto = next((p for p in productos if str(p.get('id')) == str(producto_id)), None)

        if producto:
            subtotal = float(producto['precio']) * cantidad

            for i, row in enumerate(all_rows):
                if row[0] == str(producto_id):
                    nuevo_stock = int(producto.get('stock', 0)) - cantidad
                    try:
                        sheet_productos.update_cell(i + 1, 4, nuevo_stock)
                    except Exception as e:
                        print(f"Error actualizando stock: {e}")
                    break

            try:
                sheet_ventas.append_row([
                    fecha_hora,
                    f'#{num_ticket:04d}',
                    producto['nombre'],
                    cantidad,
                    float(producto['precio']),
                    subtotal,
                    round(total, 2),
                    metodo
                ])
            except Exception as e:
                print(f"Error registrando venta: {e}")

            detalle.append({
                'nombre': producto['nombre'],
                'cantidad': cantidad,
                'precio': float(producto['precio']),
                'subtotal': subtotal
            })

    cache_productos = []
    cache_tiempo = 0

    return {
        'id': num_ticket,
        'items': detalle,
        'total': round(total, 2)
    }

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
        sheet.append_row([
            data.get('proveedor', ''),
            data.get('producto', ''),
            data.get('monto', 0),
            data.get('fecha_vencimiento', ''),
            data.get('estado', 'Pendiente'),
            data.get('notas', '')
        ])
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
        sheet.update(f'A{fila}:F{fila}', [[
            data.get('proveedor', actual.get('proveedor', '')),
            data.get('producto', actual.get('producto', '')),
            data.get('monto', actual.get('monto', 0)),
            data.get('fecha_vencimiento', actual.get('fecha_vencimiento', '')),
            data.get('estado', actual.get('estado', 'Pendiente')),
            data.get('notas', actual.get('notas', ''))
        ]])
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
