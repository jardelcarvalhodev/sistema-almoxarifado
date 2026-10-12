
import sqlite3
from getpass import getpass
from werkzeug.security import generate_password_hash

DB_NAME = "estoque.db"

print("=== ALTERAR LOGIN DO KAIKO ===")

novo_usuario = input("Digite o novo usuário: ").strip()
nova_senha = getpass("Digite a nova senha: ")
confirmacao = getpass("Digite a nova senha novamente: ")

if not novo_usuario:
    print("Erro: o usuário não pode ficar vazio.")
    raise SystemExit

if len(nova_senha) < 12:
    print("Erro: use uma senha com pelo menos 12 caracteres.")
    raise SystemExit

if nova_senha != confirmacao:
    print("Erro: as senhas não são iguais.")
    raise SystemExit

conexao = sqlite3.connect(DB_NAME)

try:
    cursor = conexao.cursor()

    cursor.execute(
        "SELECT id FROM usuarios WHERE usuario = ?",
        (novo_usuario,)
    )
    existente = cursor.fetchone()

    cursor.execute(
        "SELECT id FROM usuarios WHERE usuario = ?",
        ("admin",)
    )
    administrador = cursor.fetchone()

    if administrador is None:
        print("Erro: usuário administrador não encontrado.")
        conexao.rollback()

    elif existente and existente[0] != administrador[0]:
        print("Erro: esse nome de usuário já está em uso.")
        conexao.rollback()

    else:
        cursor.execute("""
            UPDATE usuarios
            SET usuario = ?, senha = ?
            WHERE id = ?
        """, (
            novo_usuario,
            generate_password_hash(nova_senha),
            administrador[0]
        ))

        conexao.commit()
        print("Login alterado com sucesso!")

finally:
    conexao.close()
