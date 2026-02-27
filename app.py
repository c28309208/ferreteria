from flask import Flask, render_template, request, jsonify
import database

app = Flask(__name__)

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
    productos = database.get_productos()
    return render_template('productos.html', productos=productos)

@app.route('/reportes')
def reportes():
    return render_template('reportes.html')

@app.route('/api/reporte')
def api_reporte():
    filtro = request.args.get('filtro', 'hoy')
    data = database.get_reporte(filtro)
    return jsonify(data)

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
    import os
app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)