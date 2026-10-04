from flask import Flask, render_template, request, redirect
import sqlite3

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

        else:
            conexao.close()
            return "Produto não encontrado. Cadastre o produto primeiro."

        conexao.close()

        return redirect("/estoque")

    return render_template("entrada.html")

@app.route("/saida", methods=["GET", "POST"])
def saida():
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

        conexao.close()

        return "Produto encontrado!" if produto else "Produto não encontrado!"

    return render_template("saida.html")

if __name__ == "__main__":
    app.run(debug=True)