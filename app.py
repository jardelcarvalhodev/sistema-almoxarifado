
import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    jsonify,
    session,
    url_for,
)
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)

# Em produção, configure FLASK_SECRET_KEY como variável de ambiente.
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "chave-temporaria-kaiko-troque-antes-de-publicar"
)

DB_NAME = "estoque.db"


# ============================================================
# CONEXÃO COM O BANCO DE DADOS
# ============================================================

def conectar_banco():
    conexao = sqlite3.connect(DB_NAME)
    conexao.row_factory = sqlite3.Row
    return conexao


# ============================================================
# CRIAÇÃO E ATUALIZAÇÃO DO BANCO
# ============================================================

def criar_banco():
    conexao = sqlite3.connect(DB_NAME)
    cursor = conexao.cursor()

    # PRODUTOS
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

    cursor.execute("PRAGMA table_info(produtos)")
    colunas_produtos = [coluna[1] for coluna in cursor.fetchall()]

    if "categoria" not in colunas_produtos:
        cursor.execute(
            "ALTER TABLE produtos ADD COLUMN categoria TEXT"
        )

    if "ativo" not in colunas_produtos:
        cursor.execute("""
            ALTER TABLE produtos
            ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1
        """)

    # FORNECEDORES
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cnpj TEXT,
            telefone TEXT,
            email TEXT
        )
    """)

    # MOVIMENTAÇÕES
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

    cursor.execute("PRAGMA table_info(movimentacoes)")
    colunas_movimentacoes = [
        coluna[1] for coluna in cursor.fetchall()
    ]

    novas_colunas = {
        "lote": "TEXT",
        "horario_registro": "TEXT",
        "fornecedor_id": "INTEGER",
        "nota_fiscal": "TEXT",
        "valor": "REAL",
        "destino": "TEXT",
        "responsavel": "TEXT",
        "requisicao": "TEXT",
        "observacoes": "TEXT",
    }

    for coluna, definicao in novas_colunas.items():
        if coluna not in colunas_movimentacoes:
            cursor.execute(
                f"ALTER TABLE movimentacoes ADD COLUMN {coluna} {definicao}"
            )

    # LOTES
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            lote TEXT NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 0
        )
    """)

    # USUÁRIOS DO SISTEMA
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL UNIQUE,
            senha TEXT NOT NULL,
            perfil TEXT NOT NULL DEFAULT 'admin'
        )
    """)

    # Cria o administrador inicial somente se ainda não existir.
    cursor.execute(
        "SELECT id FROM usuarios WHERE usuario = ?",
        ("admin",)
    )

    if cursor.fetchone() is None:
        cursor.execute("""
            INSERT INTO usuarios (usuario, senha, perfil)
            VALUES (?, ?, ?)
        """, (
            "admin",
            generate_password_hash("Kaiko@2026!"),
            "admin"
        ))

    conexao.commit()
    conexao.close()


criar_banco()


def horario_atual():
    return datetime.now().strftime("%H:%M:%S")


# ============================================================
# LOGIN E PROTEÇÃO DO SISTEMA
# ============================================================

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
            cursor = conexao.cursor()
            cursor.execute(
                "SELECT * FROM usuarios WHERE usuario = ?",
                (usuario,)
            )
            usuario_encontrado = cursor.fetchone()
        finally:
            conexao.close()

        if (
            usuario_encontrado
            and check_password_hash(usuario_encontrado["senha"], senha)
        ):
            session.clear()
            session["usuario_id"] = usuario_encontrado["id"]
            session["usuario"] = usuario_encontrado["usuario"]
            session["perfil"] = usuario_encontrado["perfil"]

            return redirect(url_for("inicio"))

        erro = "Usuário ou senha incorretos."

    return render_template("login.html", erro=erro)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.before_request
def proteger_sistema():
    # Login e arquivos estáticos não exigem autenticação.
    rotas_publicas = {"login", "static"}

    if request.endpoint is None:
        return None

    if request.endpoint in rotas_publicas:
        return None

    if not session.get("usuario_id"):
        return redirect(url_for("login"))

    return None


# ============================================================
# PÁGINA INICIAL
# ============================================================

@app.route("/")
def inicio():
    return render_template("index.html")


# ============================================================
# CADASTRAR PRODUTO
# ============================================================

@app.route("/cadastrar", methods=["GET", "POST"])
def cadastrar():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        categoria = request.form.get("categoria", "").strip()
        codigo = request.form.get("codigo", "").strip()
        lote = request.form.get("lote", "").strip()

        try:
            quantidade = int(request.form.get("quantidade", "0"))
        except ValueError:
            return "Quantidade inválida.", 400

        if not nome or not codigo or not lote:
            return "Preencha nome, código e lote.", 400

        if quantidade < 0:
            return "A quantidade não pode ser negativa.", 400

        conexao = conectar_banco()

        try:
            cursor = conexao.cursor()

            cursor.execute("""
                SELECT id
                FROM produtos
                WHERE codigo = ? AND ativo = 1
            """, (codigo,))

            if cursor.fetchone():
                return "Já existe um produto ativo com esse código.", 400

            cursor.execute("""
                INSERT INTO produtos
                    (nome, codigo, quantidade, categoria, ativo)
                VALUES (?, ?, ?, ?, 1)
            """, (nome, codigo, quantidade, categoria))

            produto_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO lotes (produto_id, lote, quantidade)
                VALUES (?, ?, ?)
            """, (produto_id, lote, quantidade))

            conexao.commit()

        finally:
            conexao.close()

        return redirect("/estoque")

    return render_template("cadastro.html")


# ============================================================
# CONSULTAR ESTOQUE
# ============================================================

@app.route("/estoque")
def estoque():
    conexao = conectar_banco()

    try:
        cursor = conexao.cursor()

        cursor.execute("""
            SELECT *
            FROM produtos
            WHERE ativo = 1
            ORDER BY nome
        """)
        produtos = cursor.fetchall()

        cursor.execute("""
            SELECT lotes.*
            FROM lotes
            INNER JOIN produtos ON produtos.id = lotes.produto_id
            WHERE produtos.ativo = 1
            ORDER BY lotes.lote
        """)
        lotes = cursor.fetchall()

    finally:
        conexao.close()

    return render_template(
        "estoque.html",
        produtos=produtos,
        lotes=lotes
    )


# ============================================================
# BUSCAR PRODUTO E LOTES
# ============================================================

@app.route("/buscar-produto")
def buscar_produto():
    codigo = request.args.get("codigo", "").strip()
    conexao = conectar_banco()

    try:
        cursor = conexao.cursor()

        cursor.execute("""
            SELECT id, nome, codigo
            FROM produtos
            WHERE codigo = ? AND ativo = 1
        """, (codigo,))

        produto = cursor.fetchone()

        if not produto:
            return jsonify({"encontrado": False})

        cursor.execute("""
            SELECT lote, quantidade
            FROM lotes
            WHERE produto_id = ? AND quantidade > 0
            ORDER BY lote
        """, (produto["id"],))

        lotes = cursor.fetchall()

        return jsonify({
            "encontrado": True,
            "id": produto["id"],
            "nome": produto["nome"],
            "codigo": produto["codigo"],
            "lotes": [
                {
                    "lote": item["lote"],
                    "quantidade": item["quantidade"]
                }
                for item in lotes
            ]
        })

    finally:
        conexao.close()


# ============================================================
# EXCLUIR PRODUTO
# ============================================================

@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    conexao = conectar_banco()

    try:
        cursor = conexao.cursor()

        cursor.execute("""
            UPDATE produtos
            SET ativo = 0
            WHERE id = ? AND ativo = 1
        """, (id,))

        conexao.commit()

    finally:
        conexao.close()

    return redirect("/estoque")


# ============================================================
# ENTRADA DE MATERIAL
# ============================================================

@app.route("/entrada", methods=["GET", "POST"])
def entrada():
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        lote = request.form.get("lote", "").strip()
        data_entrada = request.form.get("data", "").strip()
        fornecedor_texto = request.form.get("fornecedor", "").strip()
        nota_fiscal = request.form.get("nota_fiscal", "").strip()
        observacoes = request.form.get("observacoes", "").strip()

        try:
            quantidade = int(request.form.get("quantidade", "0"))

            valor_texto = (
                request.form.get("valor", "")
                .strip()
                .replace(",", ".")
            )

            valor = float(valor_texto) if valor_texto else None

            fornecedor_id = (
                int(fornecedor_texto) if fornecedor_texto else None
            )

        except ValueError:
            return "Quantidade, fornecedor ou valor inválido.", 400

        if not codigo or not lote or not data_entrada:
            return "Preencha código, lote e data da entrada.", 400

        if quantidade <= 0:
            return "A quantidade da entrada deve ser maior que zero.", 400

        if valor is not None and valor < 0:
            return "O valor não pode ser negativo.", 400

        conexao = conectar_banco()

        try:
            cursor = conexao.cursor()

            cursor.execute("""
                SELECT id
                FROM produtos
                WHERE codigo = ? AND ativo = 1
            """, (codigo,))

            produto = cursor.fetchone()

            if not produto:
                return (
                    "Produto não encontrado ou inativo. "
                    "Cadastre um produto ativo primeiro.",
                    404
                )

            produto_id = produto["id"]

            cursor.execute("""
                SELECT id
                FROM lotes
                WHERE produto_id = ? AND lote = ?
            """, (produto_id, lote))

            lote_existente = cursor.fetchone()

            if lote_existente:
                cursor.execute("""
                    UPDATE lotes
                    SET quantidade = quantidade + ?
                    WHERE id = ?
                """, (quantidade, lote_existente["id"]))
            else:
                cursor.execute("""
                    INSERT INTO lotes (produto_id, lote, quantidade)
                    VALUES (?, ?, ?)
                """, (produto_id, lote, quantidade))

            cursor.execute("""
                UPDATE produtos
                SET quantidade = quantidade + ?
                WHERE id = ? AND ativo = 1
            """, (quantidade, produto_id))

            cursor.execute("""
                INSERT INTO movimentacoes (
                    produto_id,
                    tipo,
                    quantidade,
                    data,
                    lote,
                    horario_registro,
                    fornecedor_id,
                    nota_fiscal,
                    valor,
                    observacoes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                produto_id,
                "ENTRADA",
                quantidade,
                data_entrada,
                lote,
                horario_atual(),
                fornecedor_id,
                nota_fiscal or None,
                valor,
                observacoes or None
            ))

            conexao.commit()

        finally:
            conexao.close()

        return redirect("/estoque")

    conexao = conectar_banco()

    try:
        cursor = conexao.cursor()
        cursor.execute("""
            SELECT *
            FROM fornecedores
            ORDER BY nome
        """)
        fornecedores = cursor.fetchall()

    finally:
        conexao.close()

    return render_template(
        "entrada.html",
        fornecedores=fornecedores
    )


# ============================================================
# SAÍDA DE MATERIAL
# ============================================================

@app.route("/saida", methods=["GET", "POST"])
def saida():
    produto = None
    mensagem = None
    confirmacao = False
    quantidade = 0
    lote = ""
    data_saida = ""
    lotes = []

    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        lote = request.form.get("lote", "").strip()
        data_saida = request.form.get("data", "").strip()
        confirmar = request.form.get("confirmar") == "sim"

        try:
            quantidade = int(request.form.get("quantidade", "0"))
        except ValueError:
            quantidade = 0

        if not data_saida:
            mensagem = "Informe a data da saída."
        elif quantidade <= 0:
            mensagem = "Informe uma quantidade maior que zero."
        elif not lote:
            mensagem = "Selecione o lote de onde sairá o produto."

        conexao = conectar_banco()

        try:
            cursor = conexao.cursor()

            cursor.execute("""
                SELECT *
                FROM produtos
                WHERE codigo = ? AND ativo = 1
            """, (codigo,))

            produto = cursor.fetchone()

            if not mensagem and not produto:
                mensagem = "Produto não encontrado ou inativo!"

            if produto:
                cursor.execute("""
                    SELECT id, lote, quantidade
                    FROM lotes
                    WHERE produto_id = ?
                    ORDER BY lote
                """, (produto["id"],))

                lotes = cursor.fetchall()

            lote_banco = None

            if not mensagem and produto:
                cursor.execute("""
                    SELECT id, quantidade
                    FROM lotes
                    WHERE produto_id = ? AND lote = ?
                """, (produto["id"], lote))

                lote_banco = cursor.fetchone()

                if not lote_banco:
                    mensagem = f"O lote '{lote}' não existe para esse produto."

                elif quantidade > lote_banco["quantidade"]:
                    mensagem = (
                        f"Estoque insuficiente no lote {lote}! "
                        f"Esse lote tem apenas "
                        f"{lote_banco['quantidade']} unidades."
                    )

                elif quantidade > produto["quantidade"]:
                    mensagem = (
                        "Estoque geral insuficiente! "
                        f"Existem apenas {produto['quantidade']} unidades."
                    )

            if not mensagem and produto and lote_banco and confirmar:
                cursor.execute("""
                    UPDATE produtos
                    SET quantidade = quantidade - ?
                    WHERE id = ? AND ativo = 1
                """, (quantidade, produto["id"]))

                cursor.execute("""
                    UPDATE lotes
                    SET quantidade = quantidade - ?
                    WHERE id = ?
                """, (quantidade, lote_banco["id"]))

                cursor.execute("""
                    INSERT INTO movimentacoes (
                        produto_id,
                        tipo,
                        quantidade,
                        data,
                        lote,
                        horario_registro
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    produto["id"],
                    "SAÍDA",
                    quantidade,
                    data_saida,
                    lote,
                    horario_atual()
                ))

                conexao.commit()
                return redirect("/estoque")

            if not mensagem and produto and lote_banco and not confirmar:
                confirmacao = True

        finally:
            conexao.close()

    return render_template(
        "saida.html",
        produto=produto,
        lotes=lotes,
        mensagem=mensagem,
        confirmacao=confirmacao,
        quantidade=quantidade,
        lote=lote,
        data_saida=data_saida
    )


# ============================================================
# EDITAR PRODUTO
# ============================================================

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    conexao = conectar_banco()

    try:
        cursor = conexao.cursor()

        cursor.execute(
            "SELECT * FROM produtos WHERE id = ? AND ativo = 1",
            (id,)
        )
        produto = cursor.fetchone()

        if not produto:
            return "Produto não encontrado ou inativo.", 404

        if request.method == "POST":
            nome = request.form.get("nome", "").strip()
            codigo = request.form.get("codigo", "").strip()
            categoria = request.form.get("categoria", "").strip()

            if not nome or not codigo:
                return "Preencha o nome e o código do produto.", 400

            cursor.execute("""
                SELECT id
                FROM produtos
                WHERE codigo = ?
                  AND id != ?
                  AND ativo = 1
            """, (codigo, id))

            if cursor.fetchone():
                return "Já existe outro produto ativo com esse código.", 400

            cursor.execute("""
                UPDATE produtos
                SET nome = ?, codigo = ?, categoria = ?
                WHERE id = ? AND ativo = 1
            """, (nome, codigo, categoria, id))

            conexao.commit()
            return redirect("/estoque")

        return render_template(
            "editar.html",
            produto=produto
        )

    finally:
        conexao.close()


# ============================================================
# CADASTRAR FORNECEDOR
# ============================================================

@app.route("/fornecedor", methods=["GET", "POST"])
def fornecedor():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        cnpj = request.form.get("cnpj", "").strip()
        telefone = request.form.get("telefone", "").strip()
        email = request.form.get("email", "").strip()

        if not nome:
            return "Informe o nome do fornecedor.", 400

        conexao = conectar_banco()

        try:
            cursor = conexao.cursor()

            cursor.execute("""
                INSERT INTO fornecedores (nome, cnpj, telefone, email)
                VALUES (?, ?, ?, ?)
            """, (nome, cnpj, telefone, email))

            conexao.commit()

        finally:
            conexao.close()

        return redirect("/fornecedor")

    return render_template("fornecedor.html")


# ============================================================
# HISTÓRICO COMPLETO DE MOVIMENTAÇÕES
# ============================================================

@app.route("/historico")
def historico():
    busca = request.args.get("busca", "").strip()
    tipo = request.args.get("tipo", "").strip()
    data_inicio = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()

    conexao = conectar_banco()

    try:
        cursor = conexao.cursor()

        consulta = """
            SELECT
                m.id,
                m.tipo,
                m.data,
                m.horario_registro,
                m.quantidade,
                m.lote,
                m.nota_fiscal,
                m.valor,
                m.observacoes,
                p.nome AS produto_nome,
                p.codigo AS produto_codigo,
                f.nome AS fornecedor_nome
            FROM movimentacoes m
            LEFT JOIN produtos p ON p.id = m.produto_id
            LEFT JOIN fornecedores f ON f.id = m.fornecedor_id
            WHERE 1 = 1
        """

        parametros = []

        if busca:
            consulta += """
                AND (
                    p.nome LIKE ?
                    OR p.codigo LIKE ?
                    OR m.lote LIKE ?
                    OR m.nota_fiscal LIKE ?
                    OR f.nome LIKE ?
                )
            """
            termo = f"%{busca}%"
            parametros.extend([termo, termo, termo, termo, termo])

        if tipo in ("ENTRADA", "SAÍDA"):
            consulta += " AND m.tipo = ?"
            parametros.append(tipo)

        if data_inicio:
            consulta += """
                AND date(
                    CASE
                        WHEN length(m.data) = 10
                             AND substr(m.data, 3, 1) = '/'
                        THEN substr(m.data, 7, 4) || '-' ||
                             substr(m.data, 4, 2) || '-' ||
                             substr(m.data, 1, 2)
                        ELSE m.data
                    END
                ) >= date(?)
            """
            parametros.append(data_inicio)

        if data_fim:
            consulta += """
                AND date(
                    CASE
                        WHEN length(m.data) = 10
                             AND substr(m.data, 3, 1) = '/'
                        THEN substr(m.data, 7, 4) || '-' ||
                             substr(m.data, 4, 2) || '-' ||
                             substr(m.data, 1, 2)
                        ELSE m.data
                    END
                ) <= date(?)
            """
            parametros.append(data_fim)

        consulta += " ORDER BY m.id DESC"

        cursor.execute(consulta, parametros)
        movimentacoes = cursor.fetchall()

    finally:
        conexao.close()

    return render_template(
        "historico.html",
        movimentacoes=movimentacoes,
        busca=busca,
        tipo=tipo,
        data_inicio=data_inicio,
        data_fim=data_fim
    )


# ============================================================
# RELATÓRIO DE FORNECEDORES
# ============================================================

@app.route("/relatorio-fornecedores")
def relatorio_fornecedores():
    conexao = conectar_banco()

    try:
        cursor = conexao.cursor()
        cursor.execute("""
            SELECT *
            FROM fornecedores
            ORDER BY nome
        """)
        fornecedores = cursor.fetchall()

    finally:
        conexao.close()

    return render_template(
        "relatorio_fornecedores.html",
        fornecedores=fornecedores
    )


# ============================================================
# INICIAR SISTEMA
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)
