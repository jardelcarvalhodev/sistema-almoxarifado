import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    jsonify, session, url_for, flash
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "troque-esta-chave-por-uma-chave-secreta"
)

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "estoque.db")


def conectar_banco():
    conexao = sqlite3.connect(DB_NAME)
    conexao.row_factory = sqlite3.Row
    return conexao


def horario_atual():
    return datetime.now().strftime("%H:%M:%S")


def data_atual():
    return datetime.now().strftime("%d/%m/%Y")


def adicionar_coluna(cursor, tabela, coluna, definicao):
    cursor.execute(f"PRAGMA table_info({tabela})")
    existentes = [linha["name"] for linha in cursor.fetchall()]
    if coluna not in existentes:
        cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}")


def criar_banco():
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            codigo TEXT NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 0,
            categoria TEXT,
            ativo INTEGER NOT NULL DEFAULT 1
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cnpj TEXT,
            telefone TEXT,
            email TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movimentacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            data TEXT NOT NULL,
            destino TEXT,
            responsavel TEXT,
            requisicao TEXT,
            observacoes TEXT,
            lote TEXT,
            horario_registro TEXT,
            fornecedor_id INTEGER,
            nota_fiscal TEXT,
            valor REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            lote TEXT NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL,
            perfil TEXT NOT NULL DEFAULT 'usuario'
        )
    """)

    for coluna, definicao in {
        "categoria": "TEXT",
        "ativo": "INTEGER NOT NULL DEFAULT 1",
    }.items():
        adicionar_coluna(cursor, "produtos", coluna, definicao)

    for coluna, definicao in {
        "lote": "TEXT",
        "horario_registro": "TEXT",
        "fornecedor_id": "INTEGER",
        "nota_fiscal": "TEXT",
        "valor": "REAL",
        "destino": "TEXT",
        "responsavel": "TEXT",
        "requisicao": "TEXT",
        "observacoes": "TEXT",
    }.items():
        adicionar_coluna(cursor, "movimentacoes", coluna, definicao)

    for coluna, definicao in {
        "contato": "TEXT",
        "endereco": "TEXT",
        "observacao": "TEXT",
    }.items():
        adicionar_coluna(cursor, "fornecedores", coluna, definicao)

    # Mantém compatibilidade com produtos antigos que ainda não tinham lote.
    cursor.execute("""
        SELECT p.id, p.quantidade
        FROM produtos p
        WHERE NOT EXISTS (SELECT 1 FROM lotes l WHERE l.produto_id = p.id)
    """)
    for produto in cursor.fetchall():
        cursor.execute(
            "INSERT INTO lotes (produto_id, lote, quantidade) VALUES (?, ?, ?)",
            (produto["id"], "SEM LOTE", produto["quantidade"])
        )

    # O administrador inicial só é criado quando explicitamente configurado.
    cursor.execute("SELECT COUNT(*) AS total FROM usuarios")
    if cursor.fetchone()["total"] == 0:
        senha_admin = os.environ.get("ADMIN_INITIAL_PASSWORD")
        if senha_admin:
            cursor.execute(
                "INSERT INTO usuarios (usuario, senha, perfil) VALUES (?, ?, 'admin')",
                ("admin", generate_password_hash(senha_admin))
            )

    conexao.commit()
    conexao.close()


criar_banco()


def administrador_obrigatorio(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        if session.get("perfil") != "admin":
            return "Acesso permitido somente ao administrador.", 403
        return funcao(*args, **kwargs)
    return wrapper


@app.before_request
def proteger_sistema():
    rotas_publicas = {"login", "cadastro_usuario", "static"}
    if request.endpoint is None or request.endpoint in rotas_publicas:
        return
    if not session.get("usuario_id"):
        return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("usuario_id"):
        return redirect(url_for("inicio"))

    erro = None
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        conexao = conectar_banco()
        try:
            registro = conexao.execute(
                "SELECT * FROM usuarios WHERE usuario = ?", (usuario,)
            ).fetchone()
        finally:
            conexao.close()

        if registro and check_password_hash(registro["senha"], senha):
            session.clear()
            session["usuario_id"] = registro["id"]
            session["usuario"] = registro["usuario"]
            session["perfil"] = registro["perfil"]
            return redirect(url_for("inicio"))
        erro = "Usuário ou senha incorretos."

    return render_template("login.html", erro=erro)


@app.route("/cadastro-usuario", methods=["GET", "POST"])
def cadastro_usuario():
    erro = None
    sucesso = None
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")
        confirmar = request.form.get("confirmar_senha", request.form.get("confirmar", ""))

        if len(usuario) < 3:
            erro = "O usuário deve ter pelo menos 3 caracteres."
        elif len(senha) < 8:
            erro = "A senha deve ter pelo menos 8 caracteres."
        elif senha != confirmar:
            erro = "As senhas não coincidem."
        else:
            conexao = conectar_banco()
            try:
                conexao.execute(
                    "INSERT INTO usuarios (usuario, senha, perfil) VALUES (?, ?, 'usuario')",
                    (usuario, generate_password_hash(senha))
                )
                conexao.commit()
                sucesso = "Cadastro realizado. Você já pode entrar."
            except sqlite3.IntegrityError:
                erro = "Esse nome de usuário já está em uso."
            finally:
                conexao.close()

    return render_template("cadastro_usuario.html", erro=erro, sucesso=sucesso)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/cadastrar", methods=["GET", "POST"])
def cadastrar():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        codigo = request.form.get("codigo", "").strip()
        categoria = request.form.get("categoria", "").strip()
        lote = request.form.get("lote", "").strip() or "SEM LOTE"

        try:
            quantidade = int(request.form.get("quantidade", "0"))
        except ValueError:
            return "Quantidade inválida.", 400

        if not nome or not codigo:
            return "Preencha o nome e o código do produto.", 400
        if quantidade < 0:
            return "A quantidade não pode ser negativa.", 400

        conexao = conectar_banco()
        try:
            cursor = conexao.cursor()
            existente = cursor.execute(
                "SELECT id FROM produtos WHERE codigo = ? AND ativo = 1", (codigo,)
            ).fetchone()
            if existente:
                return "Já existe um produto ativo com esse código.", 400

            cursor.execute(
                "INSERT INTO produtos (nome, codigo, quantidade, categoria, ativo) VALUES (?, ?, ?, ?, 1)",
                (nome, codigo, quantidade, categoria)
            )
            produto_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO lotes (produto_id, lote, quantidade) VALUES (?, ?, ?)",
                (produto_id, lote, quantidade)
            )
            cursor.execute("""
                INSERT INTO movimentacoes
                (produto_id, tipo, quantidade, data, lote, horario_registro, responsavel, observacoes)
                VALUES (?, 'CADASTRO', ?, ?, ?, ?, ?, ?)
            """, (
                produto_id, quantidade, data_atual(), lote, horario_atual(),
                session.get("usuario"), "Produto cadastrado no sistema."
            ))
            conexao.commit()
        finally:
            conexao.close()
        flash("Produto cadastrado com sucesso.")
        return redirect(url_for("estoque"))

    return render_template("cadastro.html")


@app.route("/estoque")
def estoque():
    busca = request.args.get("busca", "").strip()
    conexao = conectar_banco()
    try:
        consulta = """
            SELECT p.*,
                   COALESCE((
                       SELECT GROUP_CONCAT(l.lote, ', ')
                       FROM lotes l
                       WHERE l.produto_id = p.id AND l.quantidade > 0
                   ), 'SEM LOTE') AS lote
            FROM produtos p
            WHERE p.ativo = 1
        """
        parametros = []
        if busca:
            consulta += " AND (p.nome LIKE ? OR p.codigo LIKE ?)"
            termo = f"%{busca}%"
            parametros.extend([termo, termo])
        consulta += " ORDER BY p.nome COLLATE NOCASE"
        produtos = conexao.execute(consulta, parametros).fetchall()
    finally:
        conexao.close()
    return render_template("estoque.html", produtos=produtos)


@app.route("/buscar-produto")
def buscar_produto():
    codigo = request.args.get("codigo", "").strip()
    conexao = conectar_banco()
    try:
        produto = conexao.execute("""
            SELECT id, nome, codigo, quantidade FROM produtos
            WHERE codigo = ? AND ativo = 1
        """, (codigo,)).fetchone()
        if not produto:
            return jsonify({"encontrado": False})
        lotes = conexao.execute("""
            SELECT lote, quantidade FROM lotes
            WHERE produto_id = ? AND quantidade > 0 ORDER BY lote
        """, (produto["id"],)).fetchall()
        return jsonify({
            "encontrado": True, "id": produto["id"], "nome": produto["nome"],
            "codigo": produto["codigo"], "quantidade": produto["quantidade"],
            "lotes": [dict(item) for item in lotes]
        })
    finally:
        conexao.close()


@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    conexao = conectar_banco()
    try:
        cursor = conexao.cursor()
        produto = cursor.execute(
            "SELECT id FROM produtos WHERE id = ? AND ativo = 1", (id,)
        ).fetchone()
        if not produto:
            flash("Produto não encontrado.")
            return redirect(url_for("estoque"))
        cursor.execute("UPDATE produtos SET ativo = 0 WHERE id = ?", (id,))
        conexao.commit()
    finally:
        conexao.close()
    flash("Produto excluído da listagem.")
    return redirect(url_for("estoque"))


@app.route("/entrada", methods=["GET", "POST"])
def entrada():
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        lote = request.form.get("lote", "").strip() or "SEM LOTE"
        data = request.form.get("data", "").strip() or data_atual()
        observacoes = (
            request.form.get("observacao", "").strip()
            or request.form.get("observacoes", "").strip()
        )
        fornecedor_texto = request.form.get("fornecedor", "").strip()
        nota_fiscal = request.form.get("nota_fiscal", "").strip()
        try:
            quantidade = int(request.form.get("quantidade", "0"))
            valor_texto = request.form.get("valor", "").strip().replace(",", ".")
            valor = float(valor_texto) if valor_texto else None
            fornecedor_id = int(fornecedor_texto) if fornecedor_texto else None
        except ValueError:
            return "Quantidade, fornecedor ou valor inválido.", 400
        if quantidade <= 0:
            return "A quantidade deve ser maior que zero.", 400

        conexao = conectar_banco()
        try:
            cursor = conexao.cursor()
            produto = cursor.execute(
                "SELECT id FROM produtos WHERE codigo = ? AND ativo = 1", (codigo,)
            ).fetchone()
            if not produto:
                return "Produto não encontrado ou inativo.", 404
            produto_id = produto["id"]
            lote_existente = cursor.execute(
                "SELECT id FROM lotes WHERE produto_id = ? AND lote = ?",
                (produto_id, lote)
            ).fetchone()
            if lote_existente:
                cursor.execute(
                    "UPDATE lotes SET quantidade = quantidade + ? WHERE id = ?",
                    (quantidade, lote_existente["id"])
                )
            else:
                cursor.execute(
                    "INSERT INTO lotes (produto_id, lote, quantidade) VALUES (?, ?, ?)",
                    (produto_id, lote, quantidade)
                )
            cursor.execute(
                "UPDATE produtos SET quantidade = quantidade + ? WHERE id = ?",
                (quantidade, produto_id)
            )
            cursor.execute("""
                INSERT INTO movimentacoes
                (produto_id, tipo, quantidade, data, lote, horario_registro,
                 fornecedor_id, nota_fiscal, valor, observacoes, responsavel)
                VALUES (?, 'ENTRADA', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                produto_id, quantidade, data, lote, horario_atual(),
                fornecedor_id, nota_fiscal or None, valor, observacoes or None,
                session.get("usuario")
            ))
            conexao.commit()
        finally:
            conexao.close()
        flash("Entrada registrada com sucesso.")
        return redirect(url_for("estoque"))

    conexao = conectar_banco()
    try:
        fornecedores = conexao.execute(
            "SELECT * FROM fornecedores ORDER BY nome"
        ).fetchall()
        produtos = conexao.execute(
            "SELECT id, nome, codigo, quantidade FROM produtos WHERE ativo = 1 ORDER BY nome"
        ).fetchall()
    finally:
        conexao.close()
    return render_template("entrada.html", fornecedores=fornecedores, produtos=produtos)


@app.route("/saida", methods=["GET", "POST"])
def saida():
    mensagem = None
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        lote = request.form.get("lote", "").strip() or "SEM LOTE"
        data_saida = request.form.get("data", "").strip() or data_atual()
        observacoes = (
            request.form.get("observacao", "").strip()
            or request.form.get("observacoes", "").strip()
        )
        try:
            quantidade = int(request.form.get("quantidade", "0"))
        except ValueError:
            quantidade = 0
        if quantidade <= 0:
            flash("Informe uma quantidade maior que zero.")
            return redirect(url_for("saida"))

        conexao = conectar_banco()
        try:
            cursor = conexao.cursor()
            produto = cursor.execute("""
                SELECT * FROM produtos WHERE codigo = ? AND ativo = 1
            """, (codigo,)).fetchone()
            if not produto:
                flash("Produto não encontrado ou inativo.")
                return redirect(url_for("saida"))

            lote_banco = cursor.execute("""
                SELECT id, quantidade FROM lotes WHERE produto_id = ? AND lote = ?
            """, (produto["id"], lote)).fetchone()
            if not lote_banco:
                # Se o usuário não informou lote e só existe um lote, seleciona-o.
                lotes_disponiveis = cursor.execute("""
                    SELECT id, lote, quantidade FROM lotes
                    WHERE produto_id = ? AND quantidade > 0 ORDER BY lote
                """, (produto["id"],)).fetchall()
                if not request.form.get("lote", "").strip() and len(lotes_disponiveis) == 1:
                    lote_banco = lotes_disponiveis[0]
                    lote = lote_banco["lote"]
                else:
                    flash("Lote não encontrado. Informe um lote válido.")
                    return redirect(url_for("saida"))
            if quantidade > lote_banco["quantidade"]:
                flash("A quantidade solicitada é maior que o saldo desse lote.")
                return redirect(url_for("saida"))
            if quantidade > produto["quantidade"]:
                flash("A quantidade solicitada é maior que o estoque total.")
                return redirect(url_for("saida"))

            cursor.execute(
                "UPDATE produtos SET quantidade = quantidade - ? WHERE id = ?",
                (quantidade, produto["id"])
            )
            cursor.execute(
                "UPDATE lotes SET quantidade = quantidade - ? WHERE id = ?",
                (quantidade, lote_banco["id"])
            )
            cursor.execute("""
                INSERT INTO movimentacoes
                (produto_id, tipo, quantidade, data, lote, horario_registro, responsavel, observacoes)
                VALUES (?, 'SAÍDA', ?, ?, ?, ?, ?, ?)
            """, (
                produto["id"], quantidade, data_saida, lote, horario_atual(),
                session.get("usuario"), observacoes or None
            ))
            conexao.commit()
        finally:
            conexao.close()
        flash("Saída registrada com sucesso.")
        return redirect(url_for("estoque"))

    conexao = conectar_banco()
    try:
        produtos = conexao.execute(
            "SELECT id, nome, codigo, quantidade FROM produtos WHERE ativo = 1 ORDER BY nome"
        ).fetchall()
    finally:
        conexao.close()
    return render_template(
        "saida.html", produtos=produtos, mensagem=mensagem,
        produto=None, lotes=[], confirmacao=False, quantidade=0, lote="", data_saida=""
    )


@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    conexao = conectar_banco()
    try:
        cursor = conexao.cursor()
        produto = cursor.execute(
            "SELECT * FROM produtos WHERE id = ? AND ativo = 1", (id,)
        ).fetchone()
        if not produto:
            return "Produto não encontrado.", 404

        lote_atual = cursor.execute("""
            SELECT lote FROM lotes WHERE produto_id = ?
            ORDER BY CASE WHEN quantidade > 0 THEN 0 ELSE 1 END, id LIMIT 1
        """, (id,)).fetchone()

        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            codigo = request.form.get("codigo", "").strip()
            categoria = request.form.get("categoria", "").strip()
            lote_novo = request.form.get("lote", "").strip() or "SEM LOTE"
            if not nome or not codigo:
                return "Preencha nome e código.", 400
            duplicado = cursor.execute("""
                SELECT id FROM produtos
                WHERE codigo = ? AND id != ? AND ativo = 1
            """, (codigo, id)).fetchone()
            if duplicado:
                return "Já existe outro produto com esse código.", 400

            cursor.execute(
                "UPDATE produtos SET nome = ?, codigo = ?, categoria = ? WHERE id = ?",
                (nome, codigo, categoria, id)
            )
            if lote_atual:
                cursor.execute(
                    "UPDATE lotes SET lote = ? WHERE id = (SELECT id FROM lotes WHERE produto_id = ? ORDER BY id LIMIT 1)",
                    (lote_novo, id)
                )
            else:
                cursor.execute(
                    "INSERT INTO lotes (produto_id, lote, quantidade) VALUES (?, ?, ?)",
                    (id, lote_novo, produto["quantidade"])
                )
            conexao.commit()
            flash("Produto atualizado com sucesso.")
            return redirect(url_for("estoque"))

        # Fornece o lote como propriedade acessível no template.
        produto_dict = dict(produto)
        produto_dict["lote"] = lote_atual["lote"] if lote_atual else ""
        return render_template("editar.html", produto=produto_dict)
    finally:
        conexao.close()


@app.route("/fornecedor", methods=["GET", "POST"])
def fornecedor():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        cnpj = request.form.get("cnpj", "").strip()
        contato = request.form.get("contato", "").strip()
        telefone = request.form.get("telefone", "").strip()
        email = request.form.get("email", "").strip()
        endereco = request.form.get("endereco", "").strip()
        observacao = request.form.get("observacao", "").strip()

        if not nome:
            return "Informe o nome do fornecedor.", 400
        if not cnpj:
            return "O CNPJ é obrigatório.", 400

        conexao = conectar_banco()
        try:
            conexao.execute("""
                INSERT INTO fornecedores (nome, cnpj, contato, telefone, email, endereco, observacao)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (nome, cnpj, contato, telefone, email, endereco, observacao))
            conexao.commit()
        finally:
            conexao.close()
        flash("Fornecedor cadastrado com sucesso.")
        return redirect(url_for("relatorio_fornecedores"))
    return render_template("fornecedor.html")


@app.route("/historico")
def historico():
    busca = request.args.get("busca", "").strip()
    tipo = request.args.get("tipo", "").strip()
    data_inicio = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()

    conexao = conectar_banco()
    try:
        consulta = """
            SELECT m.*,
                   p.nome AS produto_nome, p.nome AS nome_produto,
                   p.codigo AS produto_codigo, p.codigo AS codigo,
                   m.responsavel AS usuario,
                   m.observacoes AS observacao,
                   COALESCE(m.horario_registro, '') AS horario
            FROM movimentacoes m
            LEFT JOIN produtos p ON p.id = m.produto_id
            LEFT JOIN fornecedores f ON f.id = m.fornecedor_id
            WHERE 1 = 1
        """
        parametros = []
        if busca:
            consulta += """
                AND (p.nome LIKE ? OR p.codigo LIKE ? OR m.lote LIKE ?
                     OR m.nota_fiscal LIKE ? OR f.nome LIKE ?)
            """
            termo = f"%{busca}%"
            parametros.extend([termo] * 5)
        if tipo in ("ENTRADA", "SAÍDA", "SAIDA", "CADASTRO"):
            if tipo == "SAIDA":
                consulta += " AND m.tipo IN ('SAIDA', 'SAÍDA')"
            else:
                consulta += " AND m.tipo = ?"
                parametros.append(tipo)
        # Datas são armazenadas como dd/mm/aaaa; converte para ISO para comparação.
        if data_inicio:
            try:
                inicio_iso = datetime.strptime(data_inicio, "%Y-%m-%d").date()
                consulta += """
                    AND substr(m.data, 7, 4) || '-' || substr(m.data, 4, 2) || '-' || substr(m.data, 1, 2) >= ?
                """
                parametros.append(inicio_iso.isoformat())
            except ValueError:
                pass
        if data_fim:
            try:
                fim_iso = datetime.strptime(data_fim, "%Y-%m-%d").date()
                consulta += """
                    AND substr(m.data, 7, 4) || '-' || substr(m.data, 4, 2) || '-' || substr(m.data, 1, 2) <= ?
                """
                parametros.append(fim_iso.isoformat())
            except ValueError:
                pass
        consulta += " ORDER BY m.id DESC"
        movimentacoes = conexao.execute(consulta, parametros).fetchall()
    finally:
        conexao.close()

    # Junta data e horário na coluna que a página exibe.
    itens = []
    for linha in movimentacoes:
        item = dict(linha)
        item["data"] = f'{linha["data"]} {linha["horario"] or ""}'.strip()
        itens.append(item)
    return render_template(
        "historico.html", movimentacoes=itens, busca=busca, tipo=tipo,
        data_inicio=data_inicio, data_fim=data_fim
    )


@app.route("/historico/limpar", methods=["POST"])
@administrador_obrigatorio
def limpar_historico():
    conexao = conectar_banco()
    try:
        conexao.execute("DELETE FROM movimentacoes")
        conexao.commit()
    finally:
        conexao.close()
    flash("Histórico de movimentações limpo.")
    return redirect(url_for("historico"))


@app.route("/relatorio-fornecedores")
def relatorio_fornecedores():
    busca = request.args.get("busca", "").strip()
    conexao = conectar_banco()
    try:
        consulta = "SELECT * FROM fornecedores WHERE 1 = 1"
        parametros = []
        if busca:
            termo = f"%{busca}%"
            consulta += " AND (nome LIKE ? OR cnpj LIKE ? OR contato LIKE ? OR telefone LIKE ? OR email LIKE ?)"
            parametros.extend([termo] * 5)
        consulta += " ORDER BY nome COLLATE NOCASE"
        fornecedores = conexao.execute(consulta, parametros).fetchall()
    finally:
        conexao.close()
    return render_template("relatorio_fornecedores.html", fornecedores=fornecedores)


if __name__ == "__main__":
    app.run(debug=True)
