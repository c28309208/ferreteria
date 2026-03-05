from flask import Flask, render_template, request, jsonify
import database
import threading
import time
import urllib.request
import os

app = Flask(__name__)

# ─────────────────────────────────────────
# KEEP ALIVE - evita que Render se duerma
# ─────────────────────────────────────────

def keep_alive():
    url = os.environ.get('RENDER_EXTERNAL_URL', '')
    if not url:
        return  # Solo corre en Render
    while True:
        time.sleep(600)  # cada 10 minutos
        try:
            urllib.request.urlopen(f'{url}/ping', timeout=10)
            print("✅ Keep-alive ping enviado")
        except Exception as e:
            print(f"⚠️ Keep-alive error: {e}")

@app.route('/ping')
def ping():
    return 'pong', 200

@app.route('/')
def index():
    productos = database.get_productos()
    return render_template('index.html', productos=productos)

@app.route('/buscar')
def buscar():
    query = request.args.get('q', '')
    productos = database.buscar_producto(query)
    return jsonify(productos)

@app.route('/venta', methods=['POST'])
def venta():
    data = request.json
    ticket = database.procesar_venta(data)
    return jsonify(ticket)

@app.route('/productos')
def productos():
    return render_template('productos.html')

@app.route('/api/productos', methods=['GET'])
def get_productos():
    return jsonify(database.get_productos())

@app.route('/api/productos', methods=['POST'])
def crear_producto():
    return jsonify(database.crear_producto(request.json))

@app.route('/api/productos/<int:id>', methods=['PUT'])
def actualizar_producto(id):
    return jsonify(database.actualizar_producto(id, request.json))

@app.route('/api/productos/<int:id>', methods=['DELETE'])
def eliminar_producto(id):
    return jsonify(database.eliminar_producto(id))

@app.route('/reportes')
def reportes():
    return render_template('reportes.html')

@app.route('/api/reporte')
def api_reporte():
    filtro = request.args.get('filtro', 'hoy')
    data = database.get_reporte(filtro)
    return jsonify(data)

@app.route('/ticket')
def ticket():
    return render_template('ticket.html')

@app.route('/proveedores')
def proveedores():
    return render_template('proveedores.html')

@app.route('/api/proveedores', methods=['GET'])
def get_proveedores():
    return jsonify(database.get_proveedores())

@app.route('/api/proveedores', methods=['POST'])
def crear_proveedor():
    return jsonify(database.crear_proveedor(request.json))

@app.route('/api/proveedores/<int:id>', methods=['PUT'])
def actualizar_proveedor(id):
    return jsonify(database.actualizar_proveedor(id, request.json))

@app.route('/api/proveedores/<int:id>', methods=['DELETE'])
def eliminar_proveedor(id):
    return jsonify(database.eliminar_proveedor(id))

if __name__ == '__main__':
    t = threading.Thread(target=keep_alive, daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
