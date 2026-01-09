import os

# Estructura de directorios
directories = [
    'templates',
    'static/css',
    'static/js'
]

# Archivos y su contenido
files = {
    'requirements.txt': '''Flask==3.0.0
Werkzeug==3.0.1''',

    'app.py': '''from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import json
from pathlib import Path
import re

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

@app.route('/create_user_secret_access_2024', methods=['GET', 'POST'])
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
                data.get('hole_id'),
                data.get('from'),
                data.get('to'),
                data.get('machine')
            ) else 'incorrect',
            'created_at': datetime.now().isoformat()
        }
        
        batches.append(new_batch)
        save_batches(batches)
        
        return jsonify({'success': True, 'batch': new_batch})

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
    
    for batch in batches:
        batch['machine_values'] = {
            'hole_id': batch['hole_id'],
            'from': batch['from'],
            'to': batch['to'],
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
    app.run(host='172.16.11.104', port=5001, debug=True)
''',

    'templates/login.html': '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Portal de Operaciones</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body class="login-page">
    <div class="login-container">
        <div class="login-box">
            <h1>Portal de Operaciones</h1>
            <form id="loginForm">
                <div class="form-group">
                    <label for="username">Usuario:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                <div class="form-group">
                    <label for="password">Contraseña:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit" class="btn btn-primary">Ingresar</button>
                <div id="error-message" class="error-message"></div>
            </form>
        </div>
    </div>

    <script>
        document.getElementById('loginForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            const response = await fetch('/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            
            if (data.success) {
                window.location.href = '/index/';
            } else {
                document.getElementById('error-message').textContent = data.message;
            }
        });
    </script>
</body>
</html>
''',

    'templates/index.html': '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Portal de Operaciones</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <div class="header">
        <h1>Portal de Operaciones</h1>
        <div class="user-info">
            <div>Usuario: <strong>{{ username }}</strong></div>
            <a href="/logout" class="btn btn-secondary">Cerrar Sesión</a>
            <div class="metros-info">Metros Escaneados: <strong id="metrosEscaneados">0</strong> m</div>
        </div>
    </div>

    <div class="container">
        <div class="button-group">
            <button class="btn btn-primary" onclick="openAddBatchModal()">Add Batch</button>
            <button class="btn btn-primary" onclick="window.location.href='/status_checker'">Status Checker</button>
            <button class="btn btn-primary" onclick="window.location.href='/metros'">Metros</button>
            <button class="btn btn-primary" onclick="window.open('LINK_MINERAL_EDITOR_AQUI', '_blank')">Mineral Editor</button>
            <button class="btn btn-primary" onclick="window.open('LINK_TELEMETRIA_AQUI', '_blank')">Telemetría</button>
        </div>

        <div class="table-container">
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Batch N°</th>
                        <th>Hole ID</th>
                        <th>From</th>
                        <th>To</th>
                        <th>Machine</th>
                        <th>Status</th>
                        <th>Comentarios</th>
                        <th>Preview</th>
                    </tr>
                </thead>
                <tbody id="batchesTable">
                </tbody>
            </table>
        </div>

        <div class="pagination" id="pagination">
        </div>
    </div>

    <div id="addBatchModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <span class="modal-title">Agregar Batch</span>
                <span class="close" onclick="closeAddBatchModal()">&times;</span>
            </div>
            <form id="addBatchForm">
                <div class="form-group">
                    <label for="machine">Machine:</label>
                    <input type="text" id="machine" name="machine" required>
                </div>
                <div class="form-group">
                    <label for="holeId">Hole ID:</label>
                    <input type="text" id="holeId" name="holeId" required>
                </div>
                <div class="form-group">
                    <label for="from">From:</label>
                    <input type="number" step="0.01" id="from" name="from" required>
                </div>
                <div class="form-group">
                    <label for="to">To:</label>
                    <input type="number" step="0.01" id="to" name="to" required>
                </div>
                <div class="form-group">
                    <label for="comentarios">Comentarios:</label>
                    <textarea id="comentarios" name="comentarios" rows="3"></textarea>
                </div>
                <div class="modal-footer">
                    <button type="submit" class="btn btn-primary">Ingresar</button>
                    <button type="button" class="btn btn-secondary" onclick="closeAddBatchModal()">Cancelar</button>
                </div>
            </form>
        </div>
    </div>

    <div id="previewModal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <span class="modal-title">Preview</span>
                <span class="close" onclick="closePreviewModal()">&times;</span>
            </div>
            <div class="preview-content">
                <img id="previewImage" src="" alt="Preview">
            </div>
        </div>
    </div>

    <script src="{{ url_for('static', filename='js/script.js') }}"></script>
</body>
</html>
''',

    'templates/status_checker.html': '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Status Checker - Portal de Operaciones</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <div class="header">
        <h1>Status Checker</h1>
        <div class="user-info">
            <div>Usuario: <strong>{{ username }}</strong></div>
            <a href="/index/" class="btn btn-secondary">Volver</a>
            <a href="/logout" class="btn btn-secondary">Cerrar Sesión</a>
        </div>
    </div>

    <div class="container">
        <div class="table-container">
            <table class="data-table status-table">
                <thead>
                    <tr>
                        <th rowspan="2">Batch N°</th>
                        <th colspan="4">Ingresado en OP</th>
                        <th colspan="4">Ingresado en Máquina</th>
                        <th rowspan="2">Edit</th>
                    </tr>
                    <tr>
                        <th>Hole ID</th>
                        <th>From</th>
                        <th>To</th>
                        <th>Machine</th>
                        <th>Hole ID</th>
                        <th>From</th>
                        <th>To</th>
                        <th>Machine</th>
                    </tr>
                </thead>
                <tbody id="statusTable">
                </tbody>
            </table>
        </div>

        <div class="pagination" id="pagination">
        </div>
    </div>

    <script>
        let currentPage = 1;

        async function loadStatusData(page = 1) {
            const response = await fetch(`/api/status_checker_data?page=${page}`);
            const data = await response.json();

            const tbody = document.getElementById('statusTable');
            tbody.innerHTML = '';

            data.batches.forEach(batch => {
                const row = document.createElement('tr');
                
                const hasDifferences = 
                    batch.hole_id !== batch.machine_values.hole_id ||
                    batch.from !== batch.machine_values.from ||
                    batch.to !== batch.machine_values.to ||
                    batch.machine !== batch.machine_values.machine;

                const batchClass = hasDifferences ? 'error-text' : '';
                
                row.innerHTML = `
                    <td class="${batchClass}"><strong>${batch.batch_number}</strong></td>
                    <td class="${batch.hole_id !== batch.machine_values.hole_id ? 'error-text' : ''}">${batch.hole_id}</td>
                    <td class="${batch.from !== batch.machine_values.from ? 'error-text' : ''}">${batch.from}</td>
                    <td class="${batch.to !== batch.machine_values.to ? 'error-text' : ''}">${batch.to}</td>
                    <td class="${batch.machine !== batch.machine_values.machine ? 'error-text' : ''}">${batch.machine}</td>
                    <td class="${batch.hole_id !== batch.machine_values.hole_id ? 'error-text' : ''}">${batch.machine_values.hole_id}</td>
                    <td class="${batch.from !== batch.machine_values.from ? 'error-text' : ''}">${batch.machine_values.from}</td>
                    <td class="${batch.to !== batch.machine_values.to ? 'error-text' : ''}">${batch.machine_values.to}</td>
                    <td class="${batch.machine !== batch.machine_values.machine ? 'error-text' : ''}">${batch.machine_values.machine}</td>
                    <td><button class="btn btn-small" onclick="editBatch(${batch.batch_number})">Editar</button></td>
                `;
                
                tbody.appendChild(row);
            });

            const pagination = document.getElementById('pagination');
            pagination.innerHTML = '';
            
            for (let i = 1; i <= data.total_pages; i++) {
                const button = document.createElement('button');
                button.textContent = i;
                button.className = i === page ? 'btn btn-primary' : 'btn btn-secondary';
                button.onclick = () => loadStatusData(i);
                pagination.appendChild(button);
            }

            currentPage = page;
        }

        function editBatch(batchNumber) {
            alert(`Editar Batch ${batchNumber} - Funcionalidad a implementar`);
        }

        loadStatusData();
    </script>
</body>
</html>
''',

    'templates/metros.html': '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Metros Escaneados - Portal de Operaciones</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="header">
        <h1>Metros Escaneados</h1>
        <div class="user-info">
            <div>Usuario: <strong>{{ username }}</strong></div>
            <a href="/index/" class="btn btn-secondary">Volver</a>
            <a href="/logout" class="btn btn-secondary">Cerrar Sesión</a>
        </div>
    </div>

    <div class="container">
        <div class="charts-container">
            <div class="chart-box">
                <h2>Metros Escaneados - Hoy</h2>
                <canvas id="dailyChart"></canvas>
            </div>
            <div class="chart-box">
                <h2>Metros Escaneados - Últimos 30 Días</h2>
                <canvas id="monthlyChart"></canvas>
            </div>
        </div>
    </div>

    <script>
        async function loadMetrosData() {
            const response = await fetch('/api/metros_data');
            const data = await response.json();

            const dailyCtx = document.getElementById('dailyChart').getContext('2d');
            new Chart(dailyCtx, {
                type: 'line',
                data: {
                    labels: data.daily.map(d => `${d.hour}:00`),
                    datasets: [{
                        label: 'Metros Escaneados',
                        data: data.daily.map(d => d.metros),
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Metros'
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: 'Hora'
                            }
                        }
                    }
                }
            });

            const monthlyCtx = document.getElementById('monthlyChart').getContext('2d');
            new Chart(monthlyCtx, {
                type: 'bar',
                data: {
                    labels: data.monthly.map(d => d.day),
                    datasets: [{
                        label: 'Metros Escaneados',
                        data: data.monthly.map(d => d.metros),
                        backgroundColor: 'rgba(54, 162, 235, 0.5)',
                        borderColor: 'rgb(54, 162, 235)',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Metros'
                            }
                        },
                        x: {
                            title: {
                                display: true,
                                text: 'Día'
                            }
                        }
                    }
                }
            });
        }

        loadMetrosData();
    </script>
</body>
</html>
''',

    'templates/create_user.html': '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crear Usuario</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body class="login-page">
    <div class="login-container">
        <div class="login-box">
            <h1>Crear Nuevo Usuario</h1>
            <form id="createUserForm">
                <div class="form-group">
                    <label for="username">Usuario:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                <div class="form-group">
                    <label for="password">Contraseña:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit" class="btn btn-primary">Crear Usuario</button>
                <a href="/index/" class="btn btn-secondary">Volver</a>
                <div id="message" class="message"></div>
            </form>
        </div>
    </div>

    <script>
        document.getElementById('createUserForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            
            const response = await fetch('/create_user_secret_access_2024', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            const messageDiv = document.getElementById('message');
            
            if (data.success) {
                messageDiv.textContent = data.message;
                messageDiv.className = 'message success';
                document.getElementById('createUserForm').reset();
            } else {
                messageDiv.textContent = data.message;
                messageDiv.className = 'message error-message';
            }
        });
    </script>
</body>
</html>
''',

    'static/css/style.css': '''* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
}

.header {
    background: white;
    padding: 20px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.header h1 {
    color: #333;
    font-size: 28px;
}

.user-info {
    text-align: right;
}

.user-info div {
    margin-bottom: 5px;
}

.metros-info {
    font-size: 18px;
    color: #667eea;
    margin-top: 10px;
}

.container {
    max-width: 1400px;
    margin: 30px auto;
    padding: 20px;
    background: white;
    border-radius: 10px;
    box-shadow: 0 5px 20px rgba(0,0,0,0.1);
}

.button-group {
    display: flex;
    gap: 15px;
    margin-bottom: 30px;
    flex-wrap: wrap;
}

.btn {
    padding: 12px 24px;
    border: none;
    border-radius: 5px;
    cursor: pointer;
    font-size: 16px;
    transition: all 0.3s;
    text-decoration: none;
    display: inline-block;
}

.btn-primary {
    background: #667eea;
    color: white;
}

.btn-primary:hover {
    background: #5568d3;
    transform: translateY(-2px);
}

.btn-secondary {
    background: #6c757d;
    color: white;
}

.btn-secondary:hover {
    background: #5a6268;
}

.btn-small {
    padding: 6px 12px;
    font-size: 14px;
}

.table-container {
    overflow-x: auto;
    margin-bottom: 20px;
}

.data-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 20px;
}

.data-table th,
.data-table td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #ddd;
}

.data-table th {
    background: #667eea;
    color: white;
    font-weight: bold;
}

.data-table tr:hover {
    background: #f5f5f5;
}

.status-icon {
    font-size: 20px;
}

.status-correct {
    color: #28a745;
}

.status-incorrect {
    color: #dc3545;
}

.error-text {
    color: #dc3545 !important;
    font-weight: bold !important;
}

.pagination {
    display: flex;
    gap: 10px;
    justify-content: center;
    margin-top: 20px;
}

.modal {
    display: none;
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.5);
}

.modal-content {
    background: white;
    margin: 5% auto;
    padding: 0;
    border-radius: 10px;
    width: 90%;
    max-width: 500px;
    box-shadow: 0 5px 30px rgba(0,0,0,0.3);
    position: relative;
}

.modal-header {
    background: #667eea;
    color: white;
    padding: 15px 20px;
    border-radius: 10px 10px 0 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    cursor: move;
}

.modal-title {
    font-size: 20px;
    font-weight: bold;
}

.close {
    color: white;
    font-size: 28px;
    font-weight: bold;
    cursor: pointer;
}

.close:hover {
    color: #f1f1f1;
}

.modal-content form {
    padding: 20px;
}

.form-group {
    margin-bottom: 15px;
}

.form-group label {
    display: block;
    margin-bottom: 5px;
    font-weight: bold;
    color: #333;
}

.form-group input,
.form-group textarea {
    width: 100%;
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 5px;
    font-size: 14px;
}

.form-group textarea {
    resize: vertical;
}

.modal-footer {
    display: flex;
    gap: 10px;
    justify-content: flex-end;
    margin-top: 20px;
}

.preview-content {
    padding: 20px;
    text-align: center;
}

.preview-content img {
    max-width: 100%;
    max-height: 70vh;
    border-radius: 5px;
}

.login-page {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
}

.login-container {
    width: 100%;
    max-width: 400px;
    padding: 20px;
}

.login-box {
    background: white;
    padding: 40px;
    border-radius: 10px;
    box-shadow: 0 5px 30px rgba(0,0,0,0.2);
}

.login-box h1 {
    text-align: center;
    color: #667eea;
    margin-bottom: 30px;
}

.error-message {
    color: #dc3545;
    margin-top: 10px;
    text-align: center;
}

.message {
    margin-top: 10px;
    padding: 10px;
    border-radius: 5px;
    text-align: center;
}

.success {
    background: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
}

.charts-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 30px;
    margin-top: 30px;
}

.chart-box {
    background: white;
    padding: 20px;
    border-radius: 10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.chart-box h2 {
    color: #333;
    margin-bottom: 20px;
    text-align: center;
}

.status-table th[colspan] {
    text-align: center;
}

@media (max-width: 768px) {
    .button-group {
        flex-direction: column;
    }
    
    .charts-container {
        grid-template-columns: 1fr;
    }
    
    .header {
        flex-direction: column;
        text-align: center;
    }
}
''',

    'static/js/script.js': '''let currentPage = 1;

async function loadBatches(page = 1) {
    const response = await fetch(`/api/batches?page=${page}`);
    const data = await response.json();

    const tbody = document.getElementById('batchesTable');
    tbody.innerHTML = '';

    data.batches.forEach(batch => {
        const row = document.createElement('tr');
        const statusIcon = batch.status === 'correct' 
            ? '<span class="status-icon status-correct">✓</span>' 
            : '<span class="status-icon status-incorrect">✗</span>';
        
        row.innerHTML = `
            <td>${batch.batch_number}</td>
            <td>${batch.hole_id}</td>
            <td>${batch.from}</td>
            <td>${batch.to}</td>
            <td>${batch.machine}</td>
            <td>${statusIcon}</td>
            <td>${batch.comentarios}</td>
            <td><button class="btn btn-small" onclick="showPreview(${batch.batch_number})">Ver</button></td>
        `;
        
        tbody.appendChild(row);
    });

    const pagination = document.getElementById('pagination');
    pagination.innerHTML = '';
    
    for (let i = 1; i <= data.total_pages; i++) {
        const button = document.createElement('button');
        button.textContent = i;
        button.className = i === page ? 'btn btn-primary' : 'btn btn-secondary';
        button.onclick = () => loadBatches(i);
        pagination.appendChild(button);
    }

    currentPage = page;
    updateMetrosEscaneados();
}

async function updateMetrosEscaneados() {
    const response = await fetch('/api/metros_escaneados');
    const data = await response.json();
    document.getElementById('metrosEscaneados').textContent = data.metros;
}

function openAddBatchModal() {
    document.getElementById('addBatchModal').style.display = 'block';
}

function closeAddBatchModal() {
    document.getElementById('addBatchModal').style.display = 'none';
    document.getElementById('addBatchForm').reset();
}

document.getElementById('addBatchForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = {
        machine: document.getElementById('machine').value,
        hole_id: document.getElementById('holeId').value,
        from: document.getElementById('from').value,
        to: document.getElementById('to').value,
        comentarios: document.getElementById('comentarios').value
    };
    
    const response = await fetch('/api/batches', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
    });
    
    const data = await response.json();
    
    if (data.success) {
        closeAddBatchModal();
        loadBatches(1);
    }
});

async function showPreview(batchNumber) {
    const response = await fetch(`/api/preview/${batchNumber}`);
    const data = await response.json();
    
    if (data.image_path) {
        document.getElementById('previewImage').src = data.image_path;
        document.getElementById('previewModal').style.display = 'block';
    } else {
        alert('No se encontró imagen para este batch');
    }
}

function closePreviewModal() {
    document.getElementById('previewModal').style.display = 'none';
}

window.onclick = function(event) {
    const addModal = document.getElementById('addBatchModal');
    const previewModal = document.getElementById('previewModal');
    
    if (event.target == addModal) {
        closeAddBatchModal();
    }
    if (event.target == previewModal) {
        closePreviewModal();
    }
}

function makeDraggable(modal) {
    const header = modal.querySelector('.modal-header');
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    
    header.onmousedown = dragMouseDown;
    
    function dragMouseDown(e) {
        e.preventDefault();
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.onmouseup = closeDragElement;
        document.onmousemove = elementDrag;
    }
    
    function elementDrag(e) {
        e.preventDefault();
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;
        const content = modal.querySelector('.modal-content');
        content.style.top = (content.offsetTop - pos2) + "px";
        content.style.left = (content.offsetLeft - pos1) + "px";
    }
    
    function closeDragElement() {
        document.onmouseup = null;
        document.onmousemove = null;
    }
}

if (document.getElementById('batchesTable')) {
    loadBatches();
    makeDraggable(document.getElementById('addBatchModal'));
    makeDraggable(document.getElementById('previewModal'));
}
'''
}

def create_project():
    print("🚀 Creando estructura del proyecto Portal de Operaciones...")
    
    # Crear directorios
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Directorio creado: {directory}")
    
    # Crear archivos
    for filename, content in files.items():
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Archivo creado: {filename}")
    
    print("\n✨ ¡Proyecto creado exitosamente!")
    print("\n📋 Próximos pasos:")
    print("1. Crear entorno virtual: python -m venv venv")
    print("2. Activar entorno virtual:")
    print("   - Windows: venv\\Scripts\\activate")
    print("   - Linux/Mac: source venv/bin/activate")
    print("3. Instalar dependencias: pip install -r requirements.txt")
    print("4. Ejecutar aplicación: python app.py")
    print("\n🌐 Acceder a: http://172.16.11.104:5001/index/")
    print("👤 Usuario: Felipe.Campos")
    print("🔑 Contraseña: WeScanRocks")

if __name__ == '__main__':
    create_project()