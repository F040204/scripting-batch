from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import json
from pathlib import Path
import re
import uuid
import smbprotocol
from smbprotocol.connection import Connection
from smbprotocol.session import Session
from smbprotocol.tree import TreeConnect
from smbprotocol.open import Open, CreateDisposition
from smbprotocol.exceptions import SMBException

def smb_connect(server, share, username, password):
    smbprotocol.ClientConfig(username=username, password=password)

    conn = Connection(uuid.uuid4(), server, 445)
    conn.connect()

    session = Session(conn, username=username, password=password)
    session.connect()

    tree = TreeConnect(session, fr"\\{server}\{share}")
    tree.connect()

    return conn, session, tree

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this-in-production'

# Configuración
USERS_FILE = 'users.json'
BATCHES_FILE = 'batches.json'
SMB_PATH = '//172.16.11.104/pond/incoming/orexplore/'

# Inicializar archivos de datos
def init_data_files():
    if not os.path.exists(USERS_FILE):
        users = {
            'Felipe.Campos': {
                'password': generate_password_hash('WeScanRocks'),
                'created_at': datetime.now().isoformat()
            }
        }
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
    
    if not os.path.exists(BATCHES_FILE):
        with open(BATCHES_FILE, 'w') as f:
            json.dump([], f)

init_data_files()

# Funciones auxiliares
def load_users():
    with open(USERS_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def load_batches():
    with open(BATCHES_FILE, 'r') as f:
        return json.load(f)

def save_batches(batches):
    with open(BATCHES_FILE, 'w') as f:
        json.dump(batches, f, indent=4)

def check_file_values(hole_id, from_val, to_val, machine):
    """Verifica si los valores coinciden con el archivo .txr en el servidor"""
    try:
        # Aquí debes implementar la lógica para leer el archivo .txr del servidor SMB
        # Por ahora retorna True como ejemplo
        file_path = os.path.join(SMB_PATH, f"{hole_id}.txr")
        # Implementar lectura del archivo SMB aquí
        return True
    except:
        return False

def get_preview_image(hole_id):
    """Busca la imagen .jpg asociada al hole_id"""
    try:
        # Implementar búsqueda de imagen en servidor SMB
        image_path = f"smb://172.16.11.104/pond/incoming/orexplore/{hole_id}.jpg"
        return image_path
    except:
        return None

def calculate_metros_escaneados():
    """Calcula los metros escaneados totales"""
    batches = load_batches()
    total = 0
    for batch in batches:
        if batch.get('status') == 'correct':
            try:
                to_val = float(batch.get('to', 0))
                from_val = float(batch.get('from', 0))
                total += (to_val - from_val)
            except:
                pass
    return round(total, 2)

# Rutas
@app.route('/')
def root():
    return redirect(url_for('index_route'))

@app.route('/index/')
def index_route():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        users = load_users()
        
        if username in users and check_password_hash(users[username]['password'], password):
            session['username'] = username
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'message': 'Usuario o contraseña incorrectos'})
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/create_user', methods=['GET', 'POST'])
def create_user():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        users = load_users()
        
        if username in users:
            return jsonify({'success': False, 'message': 'El usuario ya existe'})
        
        users[username] = {
            'password': generate_password_hash(password),
            'created_at': datetime.now().isoformat()
        }
        save_users(users)
        
        return jsonify({'success': True, 'message': 'Usuario creado exitosamente'})
    
    return render_template('create_user.html')

@app.route('/api/batches', methods=['GET', 'POST'])
def batches_api():
    if 'username' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    if request.method == 'GET':
        page = int(request.args.get('page', 1))
        per_page = 20
        
        batches = load_batches()
        batches.reverse()
        
        start = (page - 1) * per_page
        end = start + per_page
        
        paginated_batches = batches[start:end]
        total_pages = (len(batches) + per_page - 1) // per_page
        
        return jsonify({
            'batches': paginated_batches,
            'total_pages': total_pages,
            'current_page': page
        })
    
    elif request.method == 'POST':
        data = request.json
        batches = load_batches()
        
        batch_number = len(batches) + 1
        
        new_batch = {
            'batch_number': batch_number,
            'hole_id': data.get('hole_id'),
            'from': data.get('from'),
            'to': data.get('to'),
            'machine': data.get('machine'),
            'comentarios': data.get('comentarios', ''),
            'status': 'correct' if check_file_values(
                data.get('M_hole_id'),
                data.get('M_from'),
                data.get('M_to'),
                data.get('M_machine')
            ) else 'incorrect',
            'created_at': datetime.now().isoformat()
        }
        
        batches.append(new_batch)
        save_batches(batches)
        
        return jsonify({'success': True, 'batch': new_batch})
@app.route('/api/batches/<int:batch_number>', methods=['DELETE'])
def delete_batch(batch_number):
    if 'username' not in session:
        return jsonify({'error': 'No autorizado'}), 401

    batches = load_batches()
    updated = [b for b in batches if b['batch_number'] != batch_number]

    if len(updated) == len(batches):
        return jsonify({'error': 'Batch no encontrado'}), 404

    # Reasignar numeración limpia
    for i, b in enumerate(updated, start=1):
        b['batch_number'] = i

    save_batches(updated)

    return jsonify({'success': True})

@app.route('/api/metros_escaneados')
def metros_escaneados_api():
    if 'username' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    total = calculate_metros_escaneados()
    return jsonify({'metros': total})

@app.route('/api/preview/<int:batch_number>')
def preview_image(batch_number):
    if 'username' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    batches = load_batches()
    batch = next((b for b in batches if b['batch_number'] == batch_number), None)
    
    if batch:
        image_path = get_preview_image(batch['hole_id'])
        return jsonify({'image_path': image_path})
    
    return jsonify({'error': 'Batch no encontrado'}), 404

@app.route('/status_checker')
@app.route('/status_checker')
def status_checker():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('status_checker.html', username=session['username'])


@app.route('/api/status_checker_data')
def status_checker_data():
    if 'username' not in session:
        return jsonify({'error': 'No autorizado'}), 401

    page = int(request.args.get('page', 1))
    per_page = 30

    batches = load_batches()
    batches.reverse()

    # Aquí NO va ninguna función definida
    # Aquí solo ejecutamos lógica
    smb_data = leer_orexplore_smb()   # <-- llamamos la función correctamente

    # ejemplo de integración (ajusta según tu lógica)
    for batch in batches:
        for smb in smb_data:
            if smb["M_hole_id"] == batch["hole_id"]:
                batch["machine_values"] = {
                    "M_hole_id": smb["M_hole_id"],
                    "M_from": smb["M_from"],
                    "M_to": smb["M_to"],
                    "M_machine": batch["machine"]
                }

    return jsonify(batches[(page-1)*per_page: page*per_page])


# ⚠️ ESTA FUNCIÓN DEBE IR FUERA DE LA RUTA, A NIVEL GLOBAL
def leer_orexplore_smb(server="17.16.11.104",
                       share="pond",
                       username="felipe@OrexChile",
                       password="El.040204"):

    conn, session, tree = smb_connect(server, share, username, password)

    base = "incoming/Orexplore"
    resultados = []

    base_dir = Open(tree, base)
    base_dir.create(CreateDisposition.FILE_OPEN)

    for info in base_dir.query_directory("*"):
        hole_id = info.file_name
        hole_path = f"{base}/{hole_id}"

        if "." in hole_id:
            continue

        try:
            hole_dir = Open(tree, hole_path)
            hole_dir.create(CreateDisposition.FILE_OPEN)
        except SMBException:
            continue

        for batch_info in hole_dir.query_directory("*"):
            batch_folder = batch_info.file_name

            if not batch_folder.startswith("batch-"):
                continue

            M_to = batch_folder.replace("batch-", "")
            batch_path = f"{hole_path}/{batch_folder}"

            depth_path = f"{batch_path}/depth.txt"

            try:
                depth_file = Open(tree, depth_path)
                depth_file.create(CreateDisposition.FILE_OPEN)
                raw = depth_file.read(0, 2048).decode("utf-8")
                M_from = raw.splitlines()[0].strip()
                depth_file.close()
            except SMBException:
                continue

            resultados.append({
                "M_hole_id": hole_id,
                "M_from": M_from,
                "M_to": M_to,
                "M_machine": None
            })
    return resultados
    for batch in batches:
        batch['machine_values'] = {
            'hole_id': batch['hole_id'],
            'from': smb['M_from'],
            'to': smb['M_to'],
            'machine': batch['machine']
        }
    
    start = (page - 1) * per_page
    end = start + per_page
    
    paginated_batches = batches[start:end]
    total_pages = (len(batches) + per_page - 1) // per_page
    
    return jsonify({
        'batches': paginated_batches,
        'total_pages': total_pages,
        'current_page': page
    })

@app.route('/metros')
def metros():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('metros.html', username=session['username'])

@app.route('/api/metros_data')
def metros_data():
    if 'username' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    batches = load_batches()
    
    now = datetime.now()
    daily_data = []
    
    for hour in range(24):
        time_point = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        metros = 0
        
        for batch in batches:
            if batch.get('status') == 'correct':
                batch_time = datetime.fromisoformat(batch['created_at'])
                if batch_time.date() == now.date() and batch_time.hour <= hour:
                    try:
                        metros += float(batch['to']) - float(batch['from'])
                    except:
                        pass
        
        daily_data.append({
            'hour': hour,
            'metros': round(metros, 2)
        })
    
    monthly_data = []
    
    for day in range(30):
        date_point = now - timedelta(days=29-day)
        metros = 0
        
        for batch in batches:
            if batch.get('status') == 'correct':
                batch_time = datetime.fromisoformat(batch['created_at'])
                if batch_time.date() == date_point.date():
                    try:
                        metros += float(batch['to']) - float(batch['from'])
                    except:
                        pass
        
        monthly_data.append({
            'day': date_point.strftime('%d/%m'),
            'metros': round(metros, 2)
        })
    
    return jsonify({
        'daily': daily_data,
        'monthly': monthly_data
    })

if __name__ == '__main__':
    app.run(host='172.16.11.151', port=5001, debug=True)
