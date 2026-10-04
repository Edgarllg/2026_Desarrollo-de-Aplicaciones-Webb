import sqlite3
import os
from datetime import date

from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

from forms.login_form import LoginForm
from forms.producto_form import ProductoForm
from forms.cliente_form import ClienteForm
from forms.proveedor_form import ProveedorForm
from forms.facturacion_form import FacturacionForm

app = Flask(__name__)
app.config['SECRET_KEY'] = 'autodrive_clave_secreta_2026'

DB_PATH = os.path.join('data', 'ferreteria.db')


# ================= CONEXIÓN Y ESTRUCTURA DE LA BASE DE DATOS =================

def get_connection():
    """Crea y retorna una conexión a la base de datos SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    """Crea las tablas del sistema si no existen (todas relacionadas entre sí)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS proveedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_empresa TEXT NOT NULL,
            contacto TEXT NOT NULL,
            telefono TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            marca TEXT NOT NULL,
            modelo TEXT NOT NULL,
            anio INTEGER NOT NULL,
            precio REAL NOT NULL,
            tipo TEXT NOT NULL,
            stock INTEGER NOT NULL,
            proveedor_id INTEGER,
            FOREIGN KEY (proveedor_id) REFERENCES proveedores(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            correo TEXT NOT NULL,
            telefono TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS facturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            fecha TEXT NOT NULL,
            total REAL NOT NULL,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detalle_factura (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            factura_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL,
            subtotal REAL NOT NULL,
            FOREIGN KEY (factura_id) REFERENCES facturas(id),
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        )
    ''')

    conn.commit()
    conn.close()


def seed_admin():
    """Crea un usuario administrador por defecto si la tabla usuarios está vacía."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM usuarios')
    total = cursor.fetchone()[0]
    if total == 0:
        cursor.execute(
            'INSERT INTO usuarios (usuario, password) VALUES (?, ?)',
            ('admin', generate_password_hash('admin123'))
        )
        conn.commit()
    conn.close()


init_db()
seed_admin()


# ================= LOGIN (Flask-Login) =================

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor inicia sesión para continuar.'
login_manager.login_message_category = 'warning'
login_manager.init_app(app)


class Usuario(UserMixin):
    def __init__(self, id, usuario):
        self.id = id
        self.usuario = usuario


@login_manager.user_loader
def load_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, usuario FROM usuarios WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return Usuario(row[0], row[1])
    return None


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, usuario, password FROM usuarios WHERE usuario = ?',
            (form.usuario.data,)
        )
        row = cursor.fetchone()
        conn.close()

        if row and check_password_hash(row[2], form.password.data):
            login_user(Usuario(row[0], row[1]))
            return redirect(url_for('index'))

        flash('Usuario o contraseña incorrectos.', 'danger')

    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente.', 'success')
    return redirect(url_for('login'))


@app.route('/')
def index():
    stats = None
    recientes = []
    if current_user.is_authenticated:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM productos')
        total_productos = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM clientes')
        total_clientes = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM proveedores')
        total_proveedores = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM facturas')
        total_facturas = cursor.fetchone()[0]
        cursor.execute('''
            SELECT f.id, c.nombre, f.fecha, f.total, d.cantidad
            FROM facturas f
            JOIN clientes c ON f.cliente_id = c.id
            LEFT JOIN detalle_factura d ON d.factura_id = f.id
            ORDER BY f.id DESC LIMIT 5
        ''')
        recientes = cursor.fetchall()
        conn.close()
        stats = {
            'productos': total_productos,
            'clientes': total_clientes,
            'proveedores': total_proveedores,
            'facturas': total_facturas,
        }
    return render_template('index.html', stats=stats, recientes=recientes)


# ================= FUNCIONES AUXILIARES PARA CHOICES RELACIONALES =================

def get_proveedor_choices():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, nombre_empresa FROM proveedores')
    filas = cursor.fetchall()
    conn.close()
    return [(0, '— Ninguno —')] + [(f[0], f[1]) for f in filas]


def get_cliente_choices():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, nombre FROM clientes')
    filas = cursor.fetchall()
    conn.close()
    return [(f[0], f[1]) for f in filas]


def get_producto_choices():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, marca, modelo, precio FROM productos')
    filas = cursor.fetchall()
    conn.close()
    return [(f[0], f'{f[1]} {f[2]} (${f[3]:.2f})') for f in filas]


def get_producto_rows():
    """Devuelve los productos con precio y stock actual (para validar inventario
    y mostrar el resumen de compra en el formulario de facturación)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, marca, modelo, precio, stock FROM productos ORDER BY marca, modelo')
    filas = cursor.fetchall()
    conn.close()
    return [
        {'id': f[0], 'marca': f[1], 'modelo': f[2], 'precio': f[3], 'stock': f[4]}
        for f in filas
    ]


# ================= MÓDULO PRODUCTOS (CRUD completo, relacionado con proveedores) =================

@app.route('/productos')
@login_required
def productos():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.id, p.marca, p.modelo, p.anio, p.precio, p.tipo, p.stock, pr.nombre_empresa
        FROM productos p
        LEFT JOIN proveedores pr ON p.proveedor_id = pr.id
        ORDER BY p.id
    ''')
    lista_productos = cursor.fetchall()
    conn.close()
    return render_template('productos.html', productos=lista_productos)


@app.route('/productos/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_producto():
    form = ProductoForm()
    form.proveedor_id.choices = get_proveedor_choices()

    if form.validate_on_submit():
        proveedor = form.proveedor_id.data if form.proveedor_id.data != 0 else None
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO productos (marca, modelo, anio, precio, tipo, stock, proveedor_id) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (form.marca.data, form.modelo.data, form.anio.data,
             form.precio.data, form.tipo.data, form.stock.data, proveedor)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('productos'))

    return render_template('formulario_producto.html', form=form, modo='nuevo')


@app.route('/productos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_producto(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM productos WHERE id = ?', (id,))
    producto = cursor.fetchone()
    conn.close()

    if not producto:
        flash('Producto no encontrado.', 'danger')
        return redirect(url_for('productos'))

    form = ProductoForm()
    form.proveedor_id.choices = get_proveedor_choices()

    if form.validate_on_submit():
        proveedor = form.proveedor_id.data if form.proveedor_id.data != 0 else None
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE productos SET marca=?, modelo=?, anio=?, precio=?, tipo=?, stock=?, proveedor_id=? '
            'WHERE id=?',
            (form.marca.data, form.modelo.data, form.anio.data,
             form.precio.data, form.tipo.data, form.stock.data, proveedor, id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('productos'))

    elif request.method == 'GET':
        form.marca.data = producto[1]
        form.modelo.data = producto[2]
        form.anio.data = producto[3]
        form.precio.data = producto[4]
        form.tipo.data = producto[5]
        form.stock.data = producto[6]
        form.proveedor_id.data = producto[7] or 0

    return render_template('formulario_producto.html', form=form, modo='editar', item_id=id)


@app.route('/productos/eliminar/<int:id>')
@login_required
def eliminar_producto(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM productos WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Producto eliminado.', 'success')
    return redirect(url_for('productos'))


# ================= MÓDULO CLIENTES (CRUD completo) =================

@app.route('/clientes')
@login_required
def clientes():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clientes ORDER BY id')
    lista_clientes = cursor.fetchall()
    conn.close()
    return render_template('clientes.html', clientes=lista_clientes)


@app.route('/clientes/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_cliente():
    form = ClienteForm()
    if form.validate_on_submit():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO clientes (nombre, correo, telefono) VALUES (?, ?, ?)',
            (form.nombre.data, form.correo.data, form.telefono.data)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('clientes'))
    return render_template('formulario_cliente.html', form=form, modo='nuevo')


@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clientes WHERE id = ?', (id,))
    cliente = cursor.fetchone()
    conn.close()

    if not cliente:
        flash('Cliente no encontrado.', 'danger')
        return redirect(url_for('clientes'))

    form = ClienteForm()
    if form.validate_on_submit():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE clientes SET nombre=?, correo=?, telefono=? WHERE id=?',
            (form.nombre.data, form.correo.data, form.telefono.data, id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('clientes'))
    elif request.method == 'GET':
        form.nombre.data = cliente[1]
        form.correo.data = cliente[2]
        form.telefono.data = cliente[3]

    return render_template('formulario_cliente.html', form=form, modo='editar', item_id=id)


@app.route('/clientes/eliminar/<int:id>')
@login_required
def eliminar_cliente(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM clientes WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Cliente eliminado.', 'success')
    return redirect(url_for('clientes'))


# ================= MÓDULO PROVEEDORES (CRUD completo) =================

@app.route('/proveedores')
@login_required
def proveedores():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM proveedores ORDER BY id')
    lista_proveedores = cursor.fetchall()
    conn.close()
    return render_template('proveedores.html', proveedores=lista_proveedores)


@app.route('/proveedores/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_proveedor():
    form = ProveedorForm()
    if form.validate_on_submit():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO proveedores (nombre_empresa, contacto, telefono) VALUES (?, ?, ?)',
            (form.nombre_empresa.data, form.contacto.data, form.telefono.data)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('proveedores'))
    return render_template('formulario_proveedor.html', form=form, modo='nuevo')


@app.route('/proveedores/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_proveedor(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM proveedores WHERE id = ?', (id,))
    proveedor = cursor.fetchone()
    conn.close()

    if not proveedor:
        flash('Proveedor no encontrado.', 'danger')
        return redirect(url_for('proveedores'))

    form = ProveedorForm()
    if form.validate_on_submit():
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE proveedores SET nombre_empresa=?, contacto=?, telefono=? WHERE id=?',
            (form.nombre_empresa.data, form.contacto.data, form.telefono.data, id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('proveedores'))
    elif request.method == 'GET':
        form.nombre_empresa.data = proveedor[1]
        form.contacto.data = proveedor[2]
        form.telefono.data = proveedor[3]

    return render_template('formulario_proveedor.html', form=form, modo='editar', item_id=id)


@app.route('/proveedores/eliminar/<int:id>')
@login_required
def eliminar_proveedor(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM proveedores WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Proveedor eliminado.', 'success')
    return redirect(url_for('proveedores'))


# ===== MÓDULO FACTURACIÓN (CRUD completo, relaciona clientes + productos + facturas) =====

@app.route('/facturacion')
@login_required
def facturacion():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT f.id, c.nombre, f.fecha, f.total, d.cantidad
        FROM facturas f
        JOIN clientes c ON f.cliente_id = c.id
        LEFT JOIN detalle_factura d ON d.factura_id = f.id
        ORDER BY f.id DESC
    ''')
    lista_facturas = cursor.fetchall()
    conn.close()
    return render_template('facturacion.html', facturas=lista_facturas)


@app.route('/facturacion/nueva', methods=['GET', 'POST'])
@login_required
def nueva_factura():
    form = FacturacionForm()
    form.cliente_id.choices = get_cliente_choices()
    productos_info = get_producto_rows()
    form.producto_id.choices = [(p['id'], f"{p['marca']} {p['modelo']}") for p in productos_info]

    if not form.cliente_id.choices or not productos_info:
        flash('Debe existir al menos un cliente y un producto registrados antes de facturar.', 'warning')
        return redirect(url_for('facturacion'))

    if form.validate_on_submit():
        producto = next((p for p in productos_info if p['id'] == form.producto_id.data), None)

        # ----- Validación de stock: no se puede facturar más unidades de las disponibles -----
        if producto and form.cantidad.data > producto['stock']:
            flash(
                f"No se puede realizar la facturación: solo hay {producto['stock']} "
                f"unidad(es) de {producto['marca']} {producto['modelo']} en stock.",
                'danger'
            )
            return render_template('formulario_facturacion.html', form=form, modo='nuevo',
                                    productos_info=productos_info)

        conn = get_connection()
        cursor = conn.cursor()
        subtotal = producto['precio'] * form.cantidad.data

        cursor.execute(
            'INSERT INTO facturas (cliente_id, fecha, total) VALUES (?, ?, ?)',
            (form.cliente_id.data, date.today().isoformat(), subtotal)
        )
        factura_id = cursor.lastrowid

        cursor.execute(
            'INSERT INTO detalle_factura (factura_id, producto_id, cantidad, subtotal) '
            'VALUES (?, ?, ?, ?)',
            (factura_id, form.producto_id.data, form.cantidad.data, subtotal)
        )

        # Se descuenta del stock la cantidad vendida
        cursor.execute(
            'UPDATE productos SET stock = stock - ? WHERE id = ?',
            (form.cantidad.data, form.producto_id.data)
        )

        conn.commit()
        conn.close()
        flash('Factura generada correctamente.', 'success')
        return redirect(url_for('facturacion'))

    return render_template('formulario_facturacion.html', form=form, modo='nuevo',
                            productos_info=productos_info)


@app.route('/facturacion/ver/<int:id>')
@login_required
def ver_factura(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT f.id, c.nombre, c.correo, f.fecha, f.total
        FROM facturas f
        JOIN clientes c ON f.cliente_id = c.id
        WHERE f.id = ?
    ''', (id,))
    factura = cursor.fetchone()

    cursor.execute('''
        SELECT p.marca, p.modelo, d.cantidad, d.subtotal
        FROM detalle_factura d
        JOIN productos p ON d.producto_id = p.id
        WHERE d.factura_id = ?
    ''', (id,))
    detalle = cursor.fetchall()
    conn.close()

    if not factura:
        flash('Factura no encontrada.', 'danger')
        return redirect(url_for('facturacion'))

    return render_template('ver_factura.html', factura=factura, detalle=detalle)


@app.route('/facturacion/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_factura(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, cliente_id FROM facturas WHERE id = ?', (id,))
    factura = cursor.fetchone()
    cursor.execute(
        'SELECT id, producto_id, cantidad FROM detalle_factura WHERE factura_id = ?', (id,)
    )
    detalle = cursor.fetchone()
    conn.close()

    if not factura or not detalle:
        flash('Factura no encontrada.', 'danger')
        return redirect(url_for('facturacion'))

    old_producto_id = detalle[1]
    old_cantidad = detalle[2]

    form = FacturacionForm()
    form.cliente_id.choices = get_cliente_choices()
    productos_info = get_producto_rows()
    form.producto_id.choices = [(p['id'], f"{p['marca']} {p['modelo']}") for p in productos_info]

    if form.validate_on_submit():
        nuevo_producto_id = form.producto_id.data
        nueva_cantidad = form.cantidad.data

        conn = get_connection()
        cursor = conn.cursor()

        # Se devuelve al stock la cantidad que tenía reservada esta factura
        cursor.execute(
            'UPDATE productos SET stock = stock + ? WHERE id = ?',
            (old_cantidad, old_producto_id)
        )

        # Se valida contra el stock ya actualizado (incluye lo que se acaba de devolver)
        cursor.execute('SELECT precio, stock FROM productos WHERE id = ?', (nuevo_producto_id,))
        precio, stock_disponible = cursor.fetchone()

        if nueva_cantidad > stock_disponible:
            conn.rollback()
            conn.close()
            nombre_producto = next(
                (f"{p['marca']} {p['modelo']}" for p in productos_info if p['id'] == nuevo_producto_id),
                'el vehículo seleccionado'
            )
            flash(
                f"No se puede realizar la facturación: solo hay {stock_disponible} "
                f"unidad(es) de {nombre_producto} en stock.",
                'danger'
            )
            return render_template('formulario_facturacion.html', form=form, modo='editar',
                                    item_id=id, productos_info=productos_info)

        subtotal = precio * nueva_cantidad

        cursor.execute(
            'UPDATE productos SET stock = stock - ? WHERE id = ?',
            (nueva_cantidad, nuevo_producto_id)
        )
        cursor.execute(
            'UPDATE facturas SET cliente_id=?, total=? WHERE id=?',
            (form.cliente_id.data, subtotal, id)
        )
        cursor.execute(
            'UPDATE detalle_factura SET producto_id=?, cantidad=?, subtotal=? WHERE factura_id=?',
            (nuevo_producto_id, nueva_cantidad, subtotal, id)
        )
        conn.commit()
        conn.close()
        flash('Factura actualizada correctamente.', 'success')
        return redirect(url_for('facturacion'))

    elif request.method == 'GET':
        form.cliente_id.data = factura[1]
        form.producto_id.data = old_producto_id
        form.cantidad.data = old_cantidad

    return render_template('formulario_facturacion.html', form=form, modo='editar',
                            item_id=id, productos_info=productos_info)


@app.route('/facturacion/eliminar/<int:id>')
@login_required
def eliminar_factura(id):
    conn = get_connection()
    cursor = conn.cursor()

    # Se devuelve al stock cada vehículo que estaba reservado en esta factura
    cursor.execute('SELECT producto_id, cantidad FROM detalle_factura WHERE factura_id = ?', (id,))
    for producto_id, cantidad in cursor.fetchall():
        cursor.execute('UPDATE productos SET stock = stock + ? WHERE id = ?', (cantidad, producto_id))

    cursor.execute('DELETE FROM detalle_factura WHERE factura_id = ?', (id,))
    cursor.execute('DELETE FROM facturas WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash('Factura eliminada y stock restaurado.', 'success')
    return redirect(url_for('facturacion'))


if __name__ == '__main__':
    app.run(debug=True)
