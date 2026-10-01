from flask import Flask, render_template, request
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

if __name__ == "__main__":
    app.run(debug=True)