from flask import Flask, render_template, request

app = Flask(__name__)


@app.route("/")
def inicio():
    return render_template ("index.html")

@app.route("/cadastrar", methods=["GET", "POST"])
def cadastrar():

    if request.method == "POST":
        print("Formulário enviado!")

    return render_template("cadastro.html")


if __name__ == "__main__":
    app.run(debug=True)