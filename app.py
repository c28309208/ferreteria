from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import database
import threading
import time
import urllib.request
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tlapaleria-mirador-2026-secreto')

def keep_alive():
    url = os.environ.get('RENDER_EXTERNAL_URL', '')
    if not url:
        return
    while True:
        time.sleep(600)
        try:
            urllib.request.urlopen(f'{url}/ping', timeout=10)
            print("✅ Keep-alive ping enviado")
        except Exception as e:
            print(f"⚠️ Keep-alive error: {e}")

@app.route('/ping')
def ping():
    return 'pong', 200

def login_requerido(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def solo_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        if session.get('rol') != 'admin':
            return jsonify({'error': 'Acceso solo para administrador'}), 403
        return f(*args, **kwargs)
    return decorated

def usuario_actual():
    return session.get('usuario', 'desconocido')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        usuario = data.get('usuario', '').strip()
        password = data.get('password', '')
        resultado = database.verificar_login(usuario, password)
        if resultado:
            session['usuario'] = usuario
            session['rol'] = resultado['rol']
            session['nombre'] = resultado.get('nombre', usuario)
            database.registrar_log(usuario, 'LOGIN', 'Inicio de sesion')
            return jsonify({'ok': True, 'rol': resultado['rol']})
        return jsonify({'error': 'Usuario o contrasena incorrectos'}), 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    usuario = usuario_actual()
    database.registrar_log(usuario, 'LOGOUT', 'Cerro sesion')
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_requerido
def index():
    return render_template('index.html')

@app.route('/buscar')
@login_requerido
def buscar():
    query = request.args.get('q', '')
    return jsonify(database.buscar_producto(query))

@app.route('/venta', methods=['POST'])
@login_requerido
def venta():
    data = request.json
    ticket = database.procesar_venta(data)
    if 'error' not in ticket:
        items_str = ', '.join([f"{i['nombre']} x{i['cantidad']}" for i in ticket.get('items', [])])
        database.registrar_log(usuario_actual(), 'VENTA', f"Ticket #{ticket.get('id')} | {items_str} | Total: ${ticket.get('total')}")
    return jsonify(ticket)

@app.route('/productos')
@login_requerido
def productos():
    return render_template('productos.html')

@app.route('/api/productos', methods=['GET'])
@login_requerido
def get_productos():
    return jsonify(database.get_productos())

@app.route('/api/productos', methods=['POST'])
@login_requerido
def crear_producto():
    r = database.crear_producto(request.json)
    if 'ok' in r:
        database.registrar_log(usuario_actual(), 'CREAR PRODUCTO', f"{request.json.get('nombre')} | Precio: ${request.json.get('precio')} | Stock: {request.json.get('stock')}")
    return jsonify(r)

@app.route('/api/productos/<int:id>', methods=['PUT'])
@login_requerido
def actualizar_producto(id):
    r = database.actualizar_producto(id, request.json)
    if 'ok' in r:
        database.registrar_log(usuario_actual(), 'EDITAR PRODUCTO', f"ID {id} | {request.json}")
    return jsonify(r)

@app.route('/api/productos/<int:id>', methods=['DELETE'])
@login_requerido
def eliminar_producto(id):
    r = database.eliminar_producto(id)
    if 'ok' in r:
        database.registrar_log(usuario_actual(), 'ELIMINAR PRODUCTO', f"Elimino producto ID {id}")
    return jsonify(r)

@app.route('/reportes')
@login_requerido
def reportes():
    return render_template('reportes.html')

@app.route('/api/reporte')
@login_requerido
def api_reporte():
    filtro = request.args.get('filtro', 'hoy')
    return jsonify(database.get_reporte(filtro))

@app.route('/ticket')
@login_requerido
def ticket():
    return render_template('ticket.html')

@app.route('/proveedores')
@login_requerido
def proveedores():
    return render_template('proveedores.html')

@app.route('/api/proveedores', methods=['GET'])
@login_requerido
def get_proveedores():
    return jsonify(database.get_proveedores())

@app.route('/api/proveedores', methods=['POST'])
@login_requerido
def crear_proveedor():
    r = database.crear_proveedor(request.json)
    if 'ok' in r:
        database.registrar_log(usuario_actual(), 'CREAR PROVEEDOR', f"{request.json.get('proveedor')} | Monto: ${request.json.get('monto')}")
    return jsonify(r)

@app.route('/api/proveedores/<int:id>', methods=['PUT'])
@login_requerido
def actualizar_proveedor(id):
    r = database.actualizar_proveedor(id, request.json)
    if 'ok' in r:
        database.registrar_log(usuario_actual(), 'EDITAR PROVEEDOR', f"ID {id} | {request.json}")
    return jsonify(r)

@app.route('/api/proveedores/<int:id>', methods=['DELETE'])
@login_requerido
def eliminar_proveedor(id):
    r = database.eliminar_proveedor(id)
    if 'ok' in r:
        database.registrar_log(usuario_actual(), 'ELIMINAR PROVEEDOR', f"Elimino proveedor ID {id}")
    return jsonify(r)

@app.route('/usuarios')
@login_requerido
def usuarios():
    if session.get('rol') != 'admin':
        return redirect(url_for('index'))
    return render_template('usuarios.html')

@app.route('/api/usuarios', methods=['GET'])
@solo_admin
def get_usuarios():
    return jsonify(database.get_usuarios())

@app.route('/api/usuarios', methods=['POST'])
@solo_admin
def crear_usuario():
    r = database.crear_usuario(request.json)
    if 'ok' in r:
        database.registrar_log(usuario_actual(), 'CREAR USUARIO', f"Nuevo: {request.json.get('usuario')} | Rol: {request.json.get('rol')}")
    return jsonify(r)

@app.route('/api/usuarios/<usuario>', methods=['DELETE'])
@solo_admin
def eliminar_usuario(usuario):
    r = database.eliminar_usuario(usuario)
    if 'ok' in r:
        database.registrar_log(usuario_actual(), 'ELIMINAR USUARIO', f"Elimino usuario: {usuario}")
    return jsonify(r)

@app.route('/api/usuarios/<usuario>/password', methods=['PUT'])
@solo_admin
def cambiar_password(usuario):
    r = database.cambiar_password(usuario, request.json.get('password', ''))
    if 'ok' in r:
        database.registrar_log(usuario_actual(), 'CAMBIAR CONTRASENA', f"Cambio contrasena de: {usuario}")
    return jsonify(r)

@app.route('/logs')
@login_requerido
def logs():
    if session.get('rol') != 'admin':
        return redirect(url_for('index'))
    return render_template('logs.html')

@app.route('/api/logs')
@solo_admin
def get_logs():
    return jsonify(database.get_logs())

@app.route('/api/sesion')
def api_sesion():
    if 'usuario' in session:
        return jsonify({'usuario': session['usuario'], 'rol': session['rol'], 'nombre': session.get('nombre', '')})
    return jsonify({'usuario': None}), 401

if __name__ == '__main__':
    t = threading.Thread(target=keep_alive, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
