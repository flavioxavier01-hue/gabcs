import os
import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'chave_secreta_para_sessoes_seguras'
DATABASE = 'produtividade.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DATABASE):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Criação das tabelas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                senha_hash TEXT NOT NULL,
                perfil TEXT CHECK(perfil IN ('gerencial', 'servidor')) NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS produtividade (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER NOT NULL,
                ano INTEGER NOT NULL,
                mes TEXT NOT NULL,
                semana INTEGER NOT NULL,
                despachos INTEGER DEFAULT 0,
                decisoes INTEGER DEFAULT 0,
                votos INTEGER DEFAULT 0,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )
        ''')
        
        # Inserção de usuários de teste (Senhas padrão: 123456)
        usuarios_teste = [
            ('Flavio Xavier', 'flavio@trf2.jus.br', generate_password_hash('123456'), 'gerencial'),
            ('Aline Souza', 'aline@trf2.jus.br', generate_password_hash('123456'), 'servidor'),
            ('Lucas Motta', 'lucas@trf2.jus.br', generate_password_hash('123456'), 'servidor')
        ]
        
        try:
            cursor.executemany('INSERT INTO usuarios (nome, email, senha_hash, perfil) VALUES (?, ?, ?, ?)', usuarios_teste)
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        finally:
            conn.close()

# Base HTML Template (Bootstrap para interface limpa)
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Sistema de Produtividade TRF2</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/all.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <nav class="navbar navbar-dark bg-dark mb-4">
        <div class="container">
            <span class="navbar-brand mb-0 h1"><i class="fas fa-chart-line me-2"></i>Controle de Produtividade</span>
            {% if session.get('user_id') %}
                <span class="navbar-text text-white">
                    Olá, <strong>{{ session['user_nome'] }}</strong> ({{ session['user_perfil'].upper() }}) | 
                    <a href="{{ url_for('logout') }}" class="btn btn-sm btn-danger ms-2">Sair</a>
                </span>
            {% endif %}
        </div>
    </nav>
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM usuarios WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['senha_hash'], senha):
            session['user_id'] = user['id']
            session['user_nome'] = user['nome']
            session['user_perfil'] = user['perfil']
            return redirect(url_for('dashboard'))
        else:
            flash('Credenciais inválidas. Tente novamente.', 'danger')
            
    LOGIN_HTML = """
    {% extends "base" %}
    {% block content %}
    <div class="row justify-content-center mt-5">
        <div class="col-md-4">
            <div class="card shadow">
                <div class="card-body">
                    <h3 class="card-title text-center mb-4">Acesso ao Sistema</h3>
                    <form method="POST">
                        <div class="mb-3">
                            <label class="form-label">E-mail Institucional</label>
                            <input type="email" name="email" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Senha</label>
                            <input type="password" name="senha" class="form-control" required>
                        </div>
                        <button type="submit" class="btn btn-primary w-100">Entrar</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    {% endblock %}
    """
    return render_template_string(BASE_TEMPLATE + LOGIN_HTML)

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    
    # Se o formulário de cadastro de minutas for enviado (Apenas perfil servidor ou próprio)
    if request.method == 'POST' and session['user_perfil'] == 'servidor':
        mes = request.form['mes']
        semana = int(request.form['semana'])
        despachos = int(request.form['despachos'] or 0)
        decisoes = int(request.form['decisoes'] or 0)
        votos = int(request.form['votos'] or 0)
        
        # Verifica se já existe registro para a semana para atualizar ou inserir novo
        existente = conn.execute('SELECT id FROM produtividade WHERE usuario_id = ? AND mes = ? AND semana = ? AND ano = 2026', 
                                 (session['user_id'], mes, semana)).fetchone()
        
        if existente:
            conn.execute('UPDATE produtividade SET despachos=?, decisoes=?, votos=? WHERE id=?', 
                         (despachos, decisoes, votos, existente['id']))
        else:
            conn.execute('INSERT INTO produtividade (usuario_id, ano, mes, semana, despachos, decisoes, votos) VALUES (?, 2026, ?, ?, ?, ?, ?)',
                         (session['user_id'], mes, semana, despachos, decisoes, votos))
        conn.commit()
        flash('Produtividade registrada com sucesso!', 'success')
    
    # Lógica de Visualização baseada nos Requisitos de Perfil
    if session['user_perfil'] == 'gerencial':
        # Visão Gerencial: Agrupado por Servidor e Mês (Exibe todas as semanas consolidadas)
        dados = conn.execute('''
            SELECT u.nome, p.mes, 
                   SUM(CASE WHEN p.semana = 1 THEN p.despachos + p.decisoes + p.votos ELSE 0 END) as sem1,
                   SUM(CASE WHEN p.semana = 2 THEN p.despachos + p.decisoes + p.votos ELSE 0 END) as sem2,
                   SUM(CASE WHEN p.semana = 3 THEN p.despachos + p.decisoes + p.votos ELSE 0 END) as sem3,
                   SUM(CASE WHEN p.semana = 4 THEN p.despachos + p.decisoes + p.votos ELSE 0 END) as sem4,
                   SUM(CASE WHEN p.semana = 5 THEN p.despachos + p.decisoes + p.votos ELSE 0 END) as sem5,
                   AVG(p.despachos + p.decisoes + p.votos) as media_semanal
            FROM usuarios u
            LEFT JOIN produtividade p ON u.id = p.usuario_id
            WHERE u.perfil = 'servidor'
            GROUP BY u.id, p.mes
        ''').fetchall()
    else:
        # Visão do Servidor: Apenas suas próprias minutas detalhadas
        dados = conn.execute('''
            SELECT mes, semana, despachos, decisoes, votos, (despachos + decisoes + votos) as total
            FROM produtividade 
            WHERE usuario_id = ? 
            ORDER BY mes, semana
        ''', (session['user_id'],)).fetchall()
        
    conn.close()

    DASHBOARD_HTML = """
    {% extends "base" %}
    {% block content %}
    
    {% if session['user_perfil'] == 'servidor' %}
    <div class="card mb-4 shadow-sm">
        <div class="card-header bg-primary text-white"><strong>Lançar Produtividade Semanal</strong></div>
        <div class="card-body">
            <form method="POST" class="row g-3">
                <div class="col-md-2">
                    <label class="form-label">Mês</label>
                    <select name="mes" class="form-select" required>
                        <option value="Janeiro">Janeiro</option>
                        <option value="Fevereiro">Fevereiro</option>
                        <option value="Março">Março</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <label class="form-label">Semana</label>
                    <select name="semana" class="form-select" required>
                        <option value="1">Semana 1</option>
                        <option value="2">Semana 2</option>
                        <option value="3">Semana 3</option>
                        <option value="4">Semana 4</option>
                        <option value="5">Semana 5</option>
                    </select>
                </div>
                <div class="col-md-2">
                    <label class="form-label">Despachos</label>
                    <input type="number" name="despachos" class="form-control" min="0" value="0">
                </div>
                <div class="col-md-2">
                    <label class="form-label">Decisões</label>
                    <input type="number" name="decisoes" class="form-control" min="0" value="0">
                </div>
                <div class="col-md-2">
                    <label class="form-label">Votos</label>
                    <input type="number" name="votos" class="form-control" min="0" value="0">
                </div>
                <div class="col-md-2 d-flex align-items-end">
                    <button type="submit" class="btn btn-success w-100">Salvar Mínuta</button>
                </div>
            </form>
        </div>
    </div>
    
    <div class="card shadow-sm">
        <div class="card-header bg-dark text-white"><strong>Minhas Minutas Registradas</strong></div>
        <div class="card-body">
            <table class="table table-striped align-middle">
                <thead>
                    <tr>
                        <th>Mês</th>
                        <th>Semana</th>
                        <th>Despachos</th>
                        <th>Decisões</th>
                        <th>Votos</th>
                        <th class="table-primary">Total da Semana</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in dados %}
                    {% if row.mes %}
                    <tr>
                        <td>{{ row.mes }}</td>
                        <td>Semana {{ row.semana }}</td>
                        <td>{{ row.despachos }}</td>
                        <td>{{ row.decisoes }}</td>
                        <td>{{ row.votos }}</td>
                        <td class="table-primary fw-bold">{{ row.total }}</td>
                    </tr>
                    {% endif %}
                    {% else %}
                    <tr><td colspan="6" class="text-center text-muted">Nenhuma minuta cadastrada até o momento.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    {% else %}
    
    <div class="card shadow-sm">
        <div class="card-header bg-dark text-white d-flex justify-content-between align-items-center">
            <strong><i class="fas fa-lock me-2"></i>Consolidado Mensal de Produtividade (Acesso Restrito)</strong>
            <span class="badge bg-warning text-dark">Perfil Gerencial Ativo</span>
        </div>
        <div class="card-body">
            <table class="table table-bordered table-hover align-middle">
                <thead class="table-secondary">
                    <tr>
                        <th>Servidor</th>
                        <th>Mês de Referência</th>
                        <th>Total Sem. 1</th>
                        <th>Total Sem. 2</th>
                        <th>Total Sem. 3</th>
                        <th>Total Sem. 4</th>
                        <th>Total Sem. 5</th>
                        <th class="table-success text-center">Média Semanal</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in dados %}
                    {% if row.mes %}
                    <tr>
                        <td class="fw-bold">{{ row.nome }}</td>
                        <td><span class="badge bg-info text-dark">{{ row.mes }}</span></td>
                        <td>{{ row.sem1 }}</td>
                        <td>{{ row.sem2 }}</td>
                        <td>{{ row.sem3 }}</td>
                        <td>{{ row.sem4 }}</td>
                        <td>{{ row.sem5 }}</td>
                        <td class="table-success text-center fw-bold text-success">{{ "%.2f"|format(row.media_semanal) }}</td>
                    </tr>
                    {% endif %}
                    {% else %}
                    <tr><td colspan="8" class="text-center text-muted">Nenhum dado mensal enviado pelos servidores ainda.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    {% bitend %}
    {% endblock %}
    """
    return render_template_string(BASE_TEMPLATE + DASHBOARD_HTML, dados=dados)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run()
