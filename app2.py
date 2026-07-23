import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
import hashlib
from flask import Flask, render_template_string, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'chave_secreta_para_sessoes_seguras'
XML_FILE = 'produtividade.xml'

# --- FUNÇÕES DE AUXÍLIO PARA MANIPULAÇÃO DO XML ---

def get_xml_root():
    """Lê o arquivo XML ou cria a estrutura inicial se não existir."""
    if not os.path.exists(XML_FILE):
        root = ET.Element('dados')
        usuarios_elem = ET.SubElement(root, 'usuarios')
        produtividade_elem = ET.SubElement(root, 'produtividades')
        
        # Criação dos usuários padrão (Senhas hash de '123456')
        senha_padrao = hashlib.sha256('123456'.encode()).hexdigest()
        
        usuarios_padrao = [
            {'id': '1', 'nome': 'Flavio Xavier', 'email': 'flavio@trf2.jus.br', 'senha': senha_padrao, 'perfil': 'gerencial'},
            {'id': '2', 'nome': 'Aline Souza', 'email': 'aline@trf2.jus.br', 'senha': senha_padrao, 'perfil': 'servidor'},
            {'id': '3', 'nome': 'Lucas Motta', 'email': 'lucas@trf2.jus.br', 'senha': senha_padrao, 'perfil': 'servidor'}
        ]
        
        for u in usuarios_padrao:
            u_elem = ET.SubElement(usuarios_elem, 'usuario')
            for k, v in u.items():
                child = ET.SubElement(u_elem, k)
                child.text = str(v)
                
        save_xml(root)
        return root
    
    tree = ET.parse(XML_FILE)
    return tree.getroot()

def save_xml(root):
    """Salva a árvore XML formatada com recuos e quebras de linha."""
    xml_str = ET.tostring(root, encoding='utf-8')
    parsed = minidom.parseString(xml_str)
    pretty_xml = parsed.toprettyxml(indent="  ")
    
    # Remove linhas em branco extras geradas pelo toprettyxml
    clean_xml = "\n".join([line for line in pretty_xml.splitlines() if line.strip()])
    
    with open(XML_FILE, "w", encoding="utf-8") as f:
        f.write(clean_xml)

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# --- TEMPLATE BASE (HTML / Bootstrap) ---

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>Sistema de Produtividade TRF2 (XML)</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/all.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <nav class="navbar navbar-dark bg-dark mb-4">
        <div class="container">
            <span class="navbar-brand mb-0 h1">
                <i class="fas fa-file-code me-2"></i>Controle de Produtividade (Armazenamento XML)
            </span>
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

# --- ROTAS DA APLICAÇÃO ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        senha_hashed = hash_senha(senha)
        
        root = get_xml_root()
        usuario_encontrado = None
        
        for u in root.findall('.//usuario'):
            if u.find('email').text == email and u.find('senha').text == senha_hashed:
                usuario_encontrado = {
                    'id': u.find('id').text,
                    'nome': u.find('nome').text,
                    'perfil': u.find('perfil').text
                }
                break
        
        if usuario_encontrado:
            session['user_id'] = usuario_encontrado['id']
            session['user_nome'] = usuario_encontrado['nome']
            session['user_perfil'] = usuario_encontrado['perfil']
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
        
    root = get_xml_root()
    produtividades_elem = root.find('produtividades')
    
    # Processa o formulário de cadastro de minutas do Servidor
    if request.method == 'POST' and session['user_perfil'] == 'servidor':
        user_id = session['user_id']
        mes = request.form['mes']
        semana = request.form['semana']
        despachos = request.form['despachos'] or '0'
        decisoes = request.form['decisoes'] or '0'
        votos = request.form['votos'] or '0'
        
        # Procura se já existe um registro para o mesmo Usuário, Mês e Semana
        existente = None
        for p in produtividades_elem.findall('item'):
            if (p.find('usuario_id').text == user_id and 
                p.find('mes').text == mes and 
                p.find('semana').text == semana and 
                p.find('ano').text == '2026'):
                existente = p
                break
        
        if existente is not None:
            # Atualiza
            existente.find('despachos').text = despachos
            existente.find('decisoes').text = decisoes
            existente.find('votos').text = votos
        else:
            # Cria novo item no XML
            item = ET.SubElement(produtividades_elem, 'item')
            ET.SubElement(item, 'usuario_id').text = user_id
            ET.SubElement(item, 'ano').text = '2026'
            ET.SubElement(item, 'mes').text = mes
            ET.SubElement(item, 'semana').text = semana
            ET.SubElement(item, 'despachos').text = despachos
            ET.SubElement(item, 'decisoes').text = decisoes
            ET.SubElement(item, 'votos').text = votos
            
        save_xml(root)
        flash('Produtividade salva com sucesso no XML!', 'success')
        return redirect(url_for('dashboard'))
    
    dados = []
    
    if session['user_perfil'] == 'gerencial':
        # Visão Gerencial: Consolida por Servidor e Mês
        usuarios = {u.find('id').text: u.find('nome').text for u in root.findall('.//usuario') if u.find('perfil').text == 'servidor'}
        
        # Estrutura auxiliar: {(usuario_id, mes): [sem1, sem2, sem3, sem4, sem5]}
        consolidação = {}
        
        for p in produtividades_elem.findall('item'):
            uid = p.find('usuario_id').text
            if uid in usuarios:
                mes = p.find('mes').text
                semana = int(p.find('semana').text)
                total_semana = int(p.find('despachos').text) + int(p.find('decisoes').text) + int(p.find('votos').text)
                
                chave = (uid, mes)
                if chave not in consolidação:
                    consolidação[chave] = [0, 0, 0, 0, 0]
                
                if 1 <= semana <= 5:
                    consolidação[chave][semana - 1] = total_semana
                    
        for (uid, mes), semanas in consolidação.items():
            totais_validos = [s for s in semanas if s > 0]
            media = sum(semanas) / len(semanas) if semanas else 0
            dados.append({
                'nome': usuarios[uid],
                'mes': mes,
                'sem1': semanas[0],
                'sem2': semanas[1],
                'sem3': semanas[2],
                'sem4': semanas[3],
                'sem5': semanas[4],
                'media_semanal': media
            })
            
    else:
        # Visão do Servidor: Busca apenas as suas minutas
        user_id = session['user_id']
        for p in produtividades_elem.findall('item'):
            if p.find('usuario_id').text == user_id:
                despachos = int(p.find('despachos').text)
                decisoes = int(p.find('decisoes').text)
                votos = int(p.find('votos').text)
                dados.append({
                    'mes': p.find('mes').text,
                    'semana': p.find('semana').text,
                    'despachos': despachos,
                    'decisoes': decisoes,
                    'votos': votos,
                    'total': despachos + decisoes + votos
                })

    DASHBOARD_HTML = """
    {% extends "base" %}
    {% block content %}
    
    {% if session['user_perfil'] == 'servidor' %}
    <!-- Lançamento de Produtividade -->
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
    
    <!-- Visualização de Minutas Próprias -->
    <div class="card shadow-sm">
        <div class="card-header bg-dark text-white"><strong>Minhas Minutas Registradas (XML)</strong></div>
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
                    <tr>
                        <td>{{ row.mes }}</td>
                        <td>Semana {{ row.semana }}</td>
                        <td>{{ row.despachos }}</td>
                        <td>{{ row.decisoes }}</td>
                        <td>{{ row.votos }}</td>
                        <td class="table-primary fw-bold">{{ row.total }}</td>
                    </tr>
                    {% else %}
                    <tr><td colspan="6" class="text-center text-muted">Nenhuma minuta registrada até o momento.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    {% else %}
    
    <!-- Painel Gerencial (Acesso a Todos os Servidores) -->
    <div class="card shadow-sm">
        <div class="card-header bg-dark text-white d-flex justify-content-between align-items-center">
            <strong><i class="fas fa-lock me-2"></i>Consolidado Mensal de Produtividade (XML)</strong>
            <span class="badge bg-warning text-dark">Perfil Gerencial</span>
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
                    {% else %}
                    <tr><td colspan="8" class="text-center text-muted">Nenhum dado cadastrado pelos servidores ainda.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    {% endif %}
    {% endblock %}
    """
    return render_template_string(BASE_TEMPLATE + DASHBOARD_HTML, dados=dados)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    get_xml_root() # Inicializa o XML se não existir
    app.run(debug=True)
