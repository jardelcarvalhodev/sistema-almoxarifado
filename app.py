from flask import Flask, render_template, request, redirect, jsonify
import sqlite3
from datetime import datetime

app = Flask(__name__)
DB_NAME = "estoque.db"


def conectar_banco():
    conexao = sqlite3.connect(DB_NAME)
    conexao.row_factory = sqlite3.Row
    return conexao


def criar_banco():
    conexao = sqlite3.connect(DB_NAME)
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            codigo TEXT NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 0,
            categoria TEXT
        )
    """)

    cursor.execute("PRAGMA table_info(produtos)")
    colunas_produtos = [coluna[1] for coluna in cursor.fetchall()]
    if "categoria" not in colunas_produtos:
        cursor.execute("ALTER TABLE produtos ADD COLUMN categoria TEXT")

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

    cursor.execute("PRAGMA table_info(movimentacoes)")
    colunas_movimentacoes = [coluna[1] for coluna in cursor.fetchall()]
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
            cursor.execute(f"ALTER TABLE movimentacoes ADD COLUMN {coluna} {definicao}")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            lote TEXT NOT NULL,
            quantidade INTEGER NOT NULL DEFAULT 0
        )
    """)

    conexao.commit()
    conexao.close()


criar_banco()


def horario_atual():
    return datetime.now().strftime("%H:%M:%S")


@app.route("/")
def inicio():
    return render_template("index.html")


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
            cursor.execute(
                "INSERT INTO produtos (nome, codigo, quantidade, categoria) VALUES (?, ?, ?, ?)",
                (nome, codigo, quantidade, categoria),
            )
            produto_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO lotes (produto_id, lote, quantidade) VALUES (?, ?, ?)",
                (produto_id, lote, quantidade),
            )
            conexao.commit()
        finally:
            conexao.close()
        return redirect("/estoque")
    return render_template("cadastro.html")


@app.route("/estoque")
def estoque():
    conexao = conectar_banco()
    try:
        cursor = conexao.cursor()
        cursor.execute("SELECT * FROM produtos ORDER BY nome")
        produtos = cursor.fetchall()
        cursor.execute("SELECT * FROM lotes ORDER BY lote")
        lotes = cursor.fetchall()
    finally:
        conexao.close()
    return render_template("estoque.html", produtos=produtos, lotes=lotes)


@app.route("/buscar-produto")
def buscar_produto():
    codigo = request.args.get("codigo", "").strip()
    conexao = conectar_banco()
    try:
        cursor = conexao.cursor()
        cursor.execute("SELECT id, nome, codigo FROM produtos WHERE codigo = ?", (codigo,))
        produto = cursor.fetchone()
        if not produto:
            return jsonify({"encontrado": False})
        cursor.execute(
            "SELECT lote, quantidade FROM lotes WHERE produto_id = ? AND quantidade > 0 ORDER BY lote",
            (produto["id"],),
        )
        lotes = cursor.fetchall()
        return jsonify({
            "encontrado": True,
            "id": produto["id"],
            "nome": produto["nome"],
            "codigo": produto["codigo"],
            "lotes": [{"lote": item["lote"], "quantidade": item["quantidade"]} for item in lotes],
        })
    finally:
        conexao.close()


@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    conexao = conectar_banco()
    try:
        cursor = conexao.cursor()
        cursor.execute("SELECT COUNT(*) FROM movimentacoes WHERE produto_id = ?", (id,))
        if cursor.fetchone()[0] > 0:
            return "Este produto possui movimentações e não pode ser excluído para preservar o histórico.", 400
        cursor.execute("DELETE FROM lotes WHERE produto_id = ?", (id,))
        cursor.execute("DELETE FROM produtos WHERE id = ?", (id,))
        conexao.commit()
    finally:
        conexao.close()
    return redirect("/estoque")


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
            valor_texto = request.form.get("valor", "").strip().replace(",", ".")
            valor = float(valor_texto) if valor_texto else None
            fornecedor_id = int(fornecedor_texto) if fornecedor_texto else None
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
            cursor.execute("SELECT id FROM produtos WHERE codigo = ?", (codigo,))
            produto = cursor.fetchone()
            if not produto:
                return "Produto não encontrado. Cadastre o produto primeiro.", 404
            produto_id = produto["id"]

            cursor.execute("SELECT id FROM lotes WHERE produto_id = ? AND lote = ?", (produto_id, lote))
            lote_existente = cursor.fetchone()
            if lote_existente:
                cursor.execute("UPDATE lotes SET quantidade = quantidade + ? WHERE id = ?", (quantidade, lote_existente["id"]))
            else:
                cursor.execute(
                    "INSERT INTO lotes (produto_id, lote, quantidade) VALUES (?, ?, ?)",
                    (produto_id, lote, quantidade),
                )

            cursor.execute("UPDATE produtos SET quantidade = quantidade + ? WHERE id = ?", (quantidade, produto_id))
            cursor.execute(
                """INSERT INTO movimentacoes
                   (produto_id, tipo, quantidade, data, lote, horario_registro, fornecedor_id, nota_fiscal, valor, observacoes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (produto_id, "ENTRADA", quantidade, data_entrada, lote, horario_atual(), fornecedor_id, nota_fiscal or None, valor, observacoes or None),
            )
            conexao.commit()
        finally:
            conexao.close()
        return redirect("/estoque")

    conexao = conectar_banco()
    try:
        cursor = conexao.cursor()
        cursor.execute("SELECT * FROM fornecedores ORDER BY nome")
        fornecedores = cursor.fetchall()
    finally:
        conexao.close()
    return render_template("entrada.html", fornecedores=fornecedores)


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
            mensagem = "Por favor, selecione o lote de onde sairá o produto."

        conexao = conectar_banco()
        try:
            cursor = conexao.cursor()
            cursor.execute("SELECT * FROM produtos WHERE codigo = ?", (codigo,))
            produto = cursor.fetchone()

            if not mensagem and not produto:
                mensagem = "Produto não encontrado!"

            if produto:
                cursor.execute("SELECT id, lote, quantidade FROM lotes WHERE produto_id = ? ORDER BY lote", (produto["id"],))
                lotes = cursor.fetchall()

            lote_banco = None
            if not mensagem and produto:
                cursor.execute(
                    "SELECT id, quantidade FROM lotes WHERE produto_id = ? AND lote = ?",
                    (produto["id"], lote),
                )
                lote_banco = cursor.fetchone()
                if not lote_banco:
                    mensagem = f"O lote '{lote}' não existe para esse produto."
                elif quantidade > lote_banco["quantidade"]:
                    mensagem = f"Estoque insuficiente no lote {lote}! Esse lote tem apenas {lote_banco['quantidade']} unidades."
                elif quantidade > produto["quantidade"]:
                    mensagem = f"Estoque geral insuficiente! Existem apenas {produto['quantidade']} unidades."

            if not mensagem and produto and lote_banco and confirmar:
                cursor.execute("UPDATE produtos SET quantidade = quantidade - ? WHERE id = ?", (quantidade, produto["id"]))
                cursor.execute("UPDATE lotes SET quantidade = quantidade - ? WHERE id = ?", (quantidade, lote_banco["id"]))
                cursor.execute(
                    """INSERT INTO movimentacoes
                       (produto_id, tipo, quantidade, data, lote, horario_registro)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (produto["id"], "SAÍDA", quantidade, data_saida, lote, horario_atual()),
                )
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
        data_saida=data_saida,
    )


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
            cursor.execute(
                "INSERT INTO fornecedores (nome, cnpj, telefone, email) VALUES (?, ?, ?, ?)",
                (nome, cnpj, telefone, email),
            )
            conexao.commit()
        finally:
            conexao.close()
        return redirect("/fornecedor")
    return render_template("fornecedor.html")


@app.route("/relatorio-fornecedores")
def relatorio_fornecedores():
    conexao = conectar_banco()
    try:
        cursor = conexao.cursor()
        cursor.execute("SELECT * FROM fornecedores ORDER BY nome")
        fornecedores = cursor.fetchall()
    finally:
        conexao.close()
    return render_template("relatorio_fornecedores.html", fornecedores=fornecedores)


if __name__ == "__main__":
    app.run(debug=True)
