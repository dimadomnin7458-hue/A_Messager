from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import random
import string
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_2025'
DATABASE = 'data1.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL,
        creator_id INTEGER
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        text TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(room_id) REFERENCES rooms(id)
    )''')
    conn.commit()
    conn.close()

init_db()

# --- АВТОРИЗАЦИЯ И РЕГИСТРАЦИЯ ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        try:
            conn = get_db()
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            conn.close()
            flash('Регистрация успешна! Теперь войдите.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Это имя пользователя уже занято.')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('index'))
        flash('Неверный логин или пароль')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# --- ЛОГИКА КОМНАТ ---

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])

@app.route('/create_room', methods=['POST'])
def create_room():
    room_name = request.form.get('room_name')
    room_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    if room_name:
        conn = get_db()
        conn.execute('INSERT INTO rooms (name, code, creator_id) VALUES (?, ?, ?)',
                     (room_name, room_code, session['user_id']))
        conn.commit()
        conn.close()
        flash(f'Комната "{room_name}" создана! Код доступа: {room_code}')
    return redirect(url_for('index'))

@app.route('/join_room', methods=['POST'])
def join_room():
    code = request.form.get('room_code').strip().upper()
    conn = get_db()
    room = conn.execute('SELECT id FROM rooms WHERE code = ?', (code,)).fetchone()
    conn.close()
    if room:
        return redirect(url_for('chat', room_id=room['id']))
    flash('Комната с таким кодом не найдена')
    return redirect(url_for('index'))

@app.route('/chat/<int:room_id>')
def chat(room_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    conn = get_db()
    room = conn.execute('SELECT * FROM rooms WHERE id = ?', (room_id,)).fetchone()
    conn.close()
    if not room: return "Комната не найдена", 404
    return render_template('chat.html', room=room, user_id=session['user_id'])

@app.route('/delete_room/<int:room_id>')
def delete_room(room_id):
    conn = get_db()
    room = conn.execute('SELECT creator_id FROM rooms WHERE id = ?', (room_id,)).fetchone()
    if room and room['creator_id'] == session['user_id']:
        conn.execute('DELETE FROM messages WHERE room_id = ?', (room_id,))
        conn.execute('DELETE FROM rooms WHERE id = ?', (room_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('index'))

# --- API ДЛЯ ЧАТА ---

@app.route('/api/messages/<int:room_id>')
def get_messages(room_id):
    conn = get_db()
    messages = conn.execute('''
        SELECT username, text, strftime('%H:%M', timestamp) as time 
        FROM messages WHERE room_id = ? ORDER BY timestamp ASC
    ''', (room_id,)).fetchall()
    conn.close()
    return jsonify([dict(m) for m in messages])

@app.route('/api/send', methods=['POST'])
def send_message():
    data = request.json
    conn = get_db()
    conn.execute('INSERT INTO messages (room_id, username, text) VALUES (?, ?, ?)',
                 (data['room_id'], session['username'], data['text']))
    conn.commit()
    conn.close()
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True)
