from flask import Flask, render_template, request, redirect, jsonify
import sqlite3
from datetime import datetime


app = Flask(__name__)


# ============================================================
# BANCO DE DADOS
# ============================================================

def criar_banco():

    conexao = sqlite3.connect("estoque.db")
    cursor = conexao.cursor()


    # --------------------------------------------------------
    # PRODUTOS
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            codigo TEXT NOT NULL,
            quantidade INTEGER NOT NULL
        )
    """)


    # Adiciona a coluna categoria caso ela ainda não exista

    cursor.execute("PRAGMA table_info(produtos)")

    colunas_produtos = [
        coluna[1]
        for coluna in cursor.fetchall()
    ]

    if "categoria" not in colunas_produtos:

        cursor.execute(
            "ALTER TABLE produtos ADD COLUMN categoria TEXT"
        )


    # --------------------------------------------------------
    # FORNECEDORES
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fornecedores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cnpj TEXT,
            telefone TEXT,
            email TEXT
        )
    """)


    # --------------------------------------------------------
    # MOVIMENTAÇÕES
    # --------------------------------------------------------

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
            observacoes TEXT
        )
    """)


    # Adiciona a coluna lote caso ela ainda não exista

    cursor.execute(
        "PRAGMA table_info(movimentacoes)"
    )

    colunas_movimentacoes = [
        coluna[1]
        for coluna in cursor.fetchall()
    ]

    if "lote" not in colunas_movimentacoes:

        cursor.execute(
            "ALTER TABLE movimentacoes ADD COLUMN lote TEXT"
        )


    # --------------------------------------------------------
    # LOTES
    # --------------------------------------------------------

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


# Cria o banco ao iniciar o sistema

criar_banco()


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

        nome = request.form["nome"]
        print(nome)


        categoria = request.form["categoria"]
        print(categoria)


        codigo = request.form["codigo"]
        print(codigo)


        quantidade = request.form["quantidade"]
        print(quantidade)


        lote = request.form["lote"]
        print(lote)


        conexao = sqlite3.connect("estoque.db")
        cursor = conexao.cursor()


        # Cadastra o produto

        cursor.execute(
            """
            INSERT INTO produtos
            (nome, codigo, quantidade, categoria)
            VALUES (?, ?, ?, ?)
            """,
            (
                nome,
                codigo,
                quantidade,
                categoria
            )
        )


        # Pega o ID do produto recém-cadastrado

        produto_id = cursor.lastrowid


        # Cadastra o lote ligado ao produto

        cursor.execute(
            """
            INSERT INTO lotes
            (produto_id, lote, quantidade)
            VALUES (?, ?, ?)
            """,
            (
                produto_id,
                lote,
                quantidade
            )
        )


        conexao.commit()
        conexao.close()


    return render_template("cadastro.html")


# ============================================================
# CONSULTAR ESTOQUE
# ============================================================

@app.route("/estoque")
def estoque():

    conexao = sqlite3.connect("estoque.db")
    cursor = conexao.cursor()


    # Busca os produtos

    cursor.execute(
        "SELECT * FROM produtos"
    )

    produtos = cursor.fetchall()


    # Busca os lotes

    cursor.execute(
        "SELECT * FROM lotes"
    )

    lotes = cursor.fetchall()


    conexao.close()


    return render_template(
        "estoque.html",
        produtos=produtos,
        lotes=lotes
    )


# ============================================================
# BUSCAR PRODUTO PELO CÓDIGO
# ============================================================

@app.route("/buscar-produto")
def buscar_produto():

    codigo = request.args.get("codigo")

    conexao = sqlite3.connect("estoque.db")
    cursor = conexao.cursor()

    cursor.execute(
        """
        SELECT id, nome, codigo
        FROM produtos
        WHERE codigo = ?
        """,
        (codigo,)
    )

    produto = cursor.fetchone()

    if produto:

        cursor.execute(
            """
            SELECT lote, quantidade
            FROM lotes
            WHERE produto_id = ?
            AND quantidade > 0
            ORDER BY lote
            """,
            (produto[0],)
        )

        lotes = cursor.fetchall()

        conexao.close()

        return jsonify({
            "encontrado": True,
            "id": produto[0],
            "nome": produto[1],
            "codigo": produto[2],
            "lotes": [
                {
                    "lote": lote[0],
                    "quantidade": lote[1]
                }
                for lote in lotes
            ]
        })

    conexao.close()

    return jsonify({
        "encontrado": False
    })

@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):

    conexao = sqlite3.connect("estoque.db")
    cursor = conexao.cursor()


    cursor.execute(
        "DELETE FROM produtos WHERE id = ?",
        (id,)
    )


    conexao.commit()
    conexao.close()


    return redirect("/estoque")


# ============================================================
# ENTRADA DE MATERIAL
# ============================================================

@app.route("/entrada", methods=["GET", "POST"])
def entrada():

    if request.method == "POST":

        codigo = request.form["codigo"]

        quantidade = int(
            request.form["quantidade"]
        )

        lote = request.form["lote"]


        conexao = sqlite3.connect("estoque.db")
        cursor = conexao.cursor()


        # Procura o produto pelo código

        cursor.execute(
            "SELECT * FROM produtos WHERE codigo = ?",
            (codigo,)
        )


        produto = cursor.fetchone()


        if not produto:

            conexao.close()

            return (
                "Produto não encontrado. "
                "Cadastre o produto primeiro."
            )


        # ----------------------------------------------------
        # VERIFICA SE O LOTE JÁ EXISTE
        # ----------------------------------------------------

        cursor.execute(
            """
            SELECT *
            FROM lotes
            WHERE produto_id = ?
            AND lote = ?
            """,
            (
                produto[0],
                lote
            )
        )


        lote_existente = cursor.fetchone()


        if lote_existente:

            # Se já existe, soma a quantidade

            cursor.execute(
                """
                UPDATE lotes
                SET quantidade = quantidade + ?
                WHERE id = ?
                """,
                (
                    quantidade,
                    lote_existente[0]
                )
            )


        else:

            # Se não existe, cria o lote

            cursor.execute(
                """
                INSERT INTO lotes
                (produto_id, lote, quantidade)
                VALUES (?, ?, ?)
                """,
                (
                    produto[0],
                    lote,
                    quantidade
                )
            )


        # ----------------------------------------------------
        # ATUALIZA ESTOQUE GERAL
        # ----------------------------------------------------

        cursor.execute(
            """
            UPDATE produtos
            SET quantidade = quantidade + ?
            WHERE id = ?
            """,
            (
                quantidade,
                produto[0]
            )
        )


        # ----------------------------------------------------
        # REGISTRA MOVIMENTAÇÃO
        # ----------------------------------------------------

        data = datetime.now().strftime(
            "%d/%m/%Y %H:%M"
        )


        cursor.execute(
            """
            INSERT INTO movimentacoes
            (produto_id, tipo, quantidade, data, lote)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                produto[0],
                "ENTRADA",
                quantidade,
                data,
                lote
            )
        )


        conexao.commit()
        conexao.close()


        return redirect("/estoque")


    # --------------------------------------------------------
    # BUSCA FORNECEDORES
    # --------------------------------------------------------

    conexao = sqlite3.connect("estoque.db")
    cursor = conexao.cursor()


    cursor.execute(
        "SELECT * FROM fornecedores ORDER BY nome"
    )


    fornecedores = cursor.fetchall()


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


    if request.method == "POST":

        codigo = request.form["codigo"]

        quantidade = int(
            request.form["quantidade"]
        )

        lote = request.form.get(
            "lote",
            ""
        )


        conexao = sqlite3.connect("estoque.db")
        cursor = conexao.cursor()


        # Procura o produto

        cursor.execute(
            """
            SELECT *
            FROM produtos
            WHERE codigo = ?
            """,
            (codigo,)
        )


        produto = cursor.fetchone()


        # Busca os lotes do produto

        lotes = []


        if produto:

            cursor.execute(
                """
                SELECT *
                FROM lotes
                WHERE produto_id = ?
                ORDER BY lote
                """,
                (produto[0],)
            )


            lotes = cursor.fetchall()


        # Produto não encontrado

        if not produto:

            mensagem = (
                "Produto não encontrado!"
            )


        # Estoque insuficiente

        elif quantidade > produto[3]:

            mensagem = (
                f"Estoque insuficiente! "
                f"Existem apenas "
                f"{produto[3]} "
                f"unidades disponíveis."
            )


        # Confirma a saída

        elif request.form.get(
            "confirmar"
        ) == "sim":

            nova_quantidade = (
                produto[3] - quantidade
            )


            cursor.execute(
                """
                UPDATE produtos
                SET quantidade = ?
                WHERE id = ?
                """,
                (
                    nova_quantidade,
                    produto[0]
                )
            )


            data = datetime.now().strftime(
                "%d/%m/%Y %H:%M"
            )


            cursor.execute(
                """
                INSERT INTO movimentacoes
                (produto_id, tipo, quantidade, data)
                VALUES (?, ?, ?, ?)
                """,
                (
                    produto[0],
                    "SAÍDA",
                    quantidade,
                    data
                )
            )


            conexao.commit()
            conexao.close()


            return redirect("/estoque")


        else:

            confirmacao = True


        conexao.close()


    else:

        lotes = []


    return render_template(
        "saida.html",
        produto=produto,
        lotes=lotes,
        mensagem=mensagem,
        confirmacao=confirmacao,
        quantidade=quantidade,
        lote=lote
    )


# ============================================================
# CADASTRAR FORNECEDOR
# ============================================================

@app.route("/fornecedor", methods=["GET", "POST"])
def fornecedor():

    if request.method == "POST":

        nome = request.form["nome"]

        cnpj = request.form["cnpj"]

        telefone = request.form["telefone"]

        email = request.form["email"]


        conexao = sqlite3.connect("estoque.db")
        cursor = conexao.cursor()


        cursor.execute(
            """
            INSERT INTO fornecedores
            (nome, cnpj, telefone, email)
            VALUES (?, ?, ?, ?)
            """,
            (
                nome,
                cnpj,
                telefone,
                email
            )
        )


        conexao.commit()
        conexao.close()


        return redirect("/fornecedor")


    return render_template(
        "fornecedor.html"
    )


# ============================================================
# RELATÓRIO DE FORNECEDORES
# ============================================================

@app.route("/relatorio-fornecedores")
def relatorio_fornecedores():

    conexao = sqlite3.connect("estoque.db")
    cursor = conexao.cursor()


    cursor.execute(
        """
        SELECT *
        FROM fornecedores
        ORDER BY nome
        """
    )


    fornecedores = cursor.fetchall()


    conexao.close()


    return render_template(
        "relatorio_fornecedores.html",
        fornecedores=fornecedores
    )


# ============================================================
# INICIAR SISTEMA
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )