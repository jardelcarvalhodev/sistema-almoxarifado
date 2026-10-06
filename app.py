from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime

app = Flask(__name__)

def criar_banco():
    conexao = sqlite3.connect("estoque.db")
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            codigo TEXT NOT NULL,
            quantidade INTEGER NOT NULL
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
            observacoes TEXT
        )
    """)

    conexao.commit()
    conexao.close()

criar_banco()

@app.route("/")
def inicio():
    return render_template ("index.html")

@app.route("/cadastrar", methods=["GET", "POST"])
def cadastrar():

    if request.method == "POST":
        nome = request.form["nome"]
        print(nome)
        codigo = request.form["codigo"]
        print(codigo)

        quantidade = request.form["quantidade"]
        print(quantidade)

        conexao = sqlite3.connect("estoque.db")
        cursor = conexao.cursor()

        cursor.execute(
    "INSERT INTO produtos (nome, codigo, quantidade) VALUES (?, ?, ?)",
    (nome, codigo, quantidade)
)

        conexao.commit()
        conexao.close()

    return render_template("cadastro.html")

@app.route("/estoque")
def estoque():
    conexao = sqlite3.connect("estoque.db")
    cursor = conexao.cursor()

    cursor.execute("SELECT * FROM produtos")
    produtos = cursor.fetchall()

    conexao.close()

    return render_template("estoque.html", produtos=produtos)

@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    conexao = sqlite3.connect("estoque.db")
    cursor = conexao.cursor()

    cursor.execute("DELETE FROM produtos WHERE id = ?", (id,))

    conexao.commit()
    conexao.close()

    return redirect("/estoque")

@app.route("/entrada", methods=["GET", "POST"])
def entrada():

    if request.method == "POST":
        codigo = request.form["codigo"]
        quantidade = int(request.form["quantidade"])

        conexao = sqlite3.connect("estoque.db")
        cursor = conexao.cursor()

        cursor.execute(
            "SELECT * FROM produtos WHERE codigo = ?",
            (codigo,)
        )

        produto = cursor.fetchone()

        if produto:
            cursor.execute(
                "UPDATE produtos SET quantidade = quantidade + ? WHERE codigo = ?",
                (quantidade, codigo)
            )

            conexao.commit()
            conexao.close()

            return redirect("/estoque")

        else:
            conexao.close()
            return "Produto não encontrado. Cadastre o produto primeiro."

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

@app.route("/saida", methods=["GET", "POST"])
def saida():

    produto = None
    mensagem = None
    confirmacao = False
    quantidade = 0

    if request.method == "POST":

        codigo = request.form["codigo"]
        quantidade = int(request.form["quantidade"])

        conexao = sqlite3.connect("estoque.db")
        cursor = conexao.cursor()

        cursor.execute(
            "SELECT * FROM produtos WHERE codigo = ?",
            (codigo,)
        )

        produto = cursor.fetchone()

        if not produto:

            mensagem = "Produto não encontrado!"

        elif quantidade > produto[3]:

            mensagem = (
                f"Estoque insuficiente! "
                f"Existem apenas {produto[3]} unidades disponíveis."
            )

        elif request.form.get("confirmar") == "sim":

            nova_quantidade = produto[3] - quantidade

            cursor.execute(
                "UPDATE produtos SET quantidade = ? WHERE id = ?",
                (nova_quantidade, produto[0])
            )

            data = datetime.now().strftime("%d/%m/%Y %H:%M")

            cursor.execute(
                """
                INSERT INTO movimentacoes
                (produto_id, tipo, quantidade, data)
                VALUES (?, ?, ?, ?)
                """,
                (produto[0], "SAÍDA", quantidade, data)
            )

            conexao.commit()
            conexao.close()

            return redirect("/estoque")

        else:

            confirmacao = True

        conexao.close()

    return render_template(
        "saida.html",
        produto=produto,
        mensagem=mensagem,
        confirmacao=confirmacao,
        quantidade=quantidade
    )

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
            INSERT INTO fornecedores (nome, cnpj, telefone, email)
            VALUES (?, ?, ?, ?)
            """,
            (nome, cnpj, telefone, email)
        )

        conexao.commit()
        conexao.close()

        return redirect("/fornecedor")

    return render_template("fornecedor.html")

@app.route("/relatorio-fornecedores")
def relatorio_fornecedores():
    conexao = sqlite3.connect("estoque.db")
    cursor = conexao.cursor()

    cursor.execute("SELECT * FROM fornecedores ORDER BY nome")
    fornecedores = cursor.fetchall()

    conexao.close()

    return render_template(
        "relatorio_fornecedores.html",
        fornecedores=fornecedores
    )

if __name__ == "__main__":
    app.run(debug=True)