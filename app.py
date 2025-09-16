from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
from datetime import datetime


app = Flask(__name__)
DB_NAME = "almox.db"


def init_db():
    """Inicializa o banco de dados SQLite com as tabelas necessárias"""
    if not os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        # Tabela de locações
        cursor.execute("""
            CREATE TABLE rentals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professor TEXT NOT NULL,
                materia TEXT NOT NULL,
                sala TEXT NOT NULL,
                data_hora TEXT NOT NULL,
                tempo_uso TEXT NOT NULL,
                equipamento TEXT NOT NULL,
                turma TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Em Uso'
            )
        """)

        # Tabela de inventário
        cursor.execute("""
            CREATE TABLE inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                tipo TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                descricao TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                subject TEXT NOT NULL,
                experience_years INTEGER NOT NULL,
                schedule TEXT
            )
        """)

        conn.commit()
        conn.close()


@app.route("/")
def index():
    return render_template("index.html")

@app.template_filter("datetimeformat")
def datetimeformat(value, format="%d/%m/%Y %H:%M"):
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime(format)
    except Exception:
        return value  # se der erro, mostra original

# Helpers
def query_db(query, args=(), one=False, commit=False):
    conn = sqlite3.connect(DB_NAME)   # <- corrigido, estava "/almox.db"
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(query, args)
    if commit:
        conn.commit()
        lastrowid = cur.lastrowid
        conn.close()
        return lastrowid
    rv = cur.fetchall()
    conn.close()
    return (rv[0] if rv else None) if one else rv

# ----------------- PROFESSORES ----------------- #
@app.route("/teachers")
def teachers():
    conn = sqlite3.connect(DB_NAME)
    teachers_list = conn.execute("SELECT * FROM teachers").fetchall()
    conn.close()
    return render_template("teachers.html", teachers=teachers_list)

@app.route("/teachers/new", methods=["GET", "POST"])
def teacher_form():
    if request.method == "POST":
        first_name = request.form["first_name"]
        last_name = request.form["last_name"]
        subject = request.form["subject"]
        experience_years = request.form["experience_years"]
        schedule = request.form["schedule"]

        conn = sqlite3.connect(DB_NAME)
        conn.execute(
            "INSERT INTO teachers (first_name, last_name, subject, experience_years, schedule) VALUES (?, ?, ?, ?, ?)",
            (first_name, last_name, subject, experience_years, schedule)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("teachers"))

    return render_template("teacher_form.html")

# ----------------- LOCAÇÕES ----------------- #
@app.route("/rentals")
def rentals():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row   # 🔑 agora cada linha vira um "dict-like"
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM rentals")
    rentals_list = cursor.fetchall()
    conn.close()
    return render_template("rentals.html", rentals=rentals_list)


@app.route("/rentals/return/<int:rental_id>")
def return_rental(rental_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE rentals SET status = 'Devolvido' WHERE id = ?", (rental_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("rentals"))

# Rota para criar nova locação
@app.route("/rentals/new", methods=["GET", "POST"])
def rental_form():
    if request.method == "POST":
        professor = request.form["professor"]
        materia = request.form["materia"]
        sala = request.form["sala"]
        data_hora = request.form["data_hora"]
        tempo_uso = request.form["tempo_uso"]
        equipamento = request.form["equipamento"]
        turma = request.form["turma"]   # 🔑 novo campo

        query_db(
            """
            INSERT INTO rentals (professor, materia, sala, turma, data_hora, tempo_uso, equipamento, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Em Uso')
            """,
            (professor, materia, sala, turma, data_hora, tempo_uso, equipamento),
            commit=True,
        )
        return redirect(url_for("rentals"))

    return render_template("rental_form.html")


# ----------------- INVENTÁRIO ----------------- #
@app.route("/inventory")
def inventory():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row   # <-- aqui
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory")
    inventory_list = cursor.fetchall()
    conn.close()
    return render_template("inventory.html", inventory=inventory_list)

@app.route("/inventory/new", methods=["GET", "POST"])
def new_inventory():
    if request.method == "POST":
        nome = request.form["nome"]
        tipo = request.form["tipo"]
        quantidade = request.form["quantidade"]
        descricao = request.form["descricao"]

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO inventory (nome, tipo, quantidade, descricao)
            VALUES (?, ?, ?, ?)
        """, (nome, tipo, quantidade, descricao))
        conn.commit()
        conn.close()

        return redirect(url_for("inventory"))

    return render_template("inventory_form.html")

@app.route("/inventory/delete/<int:item_id>")
def delete_inventory(item_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("inventory"))

@app.route("/inventory/edit/<int:item_id>", methods=["GET", "POST"])
def edit_inventory(item_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == "POST":
        nome = request.form["nome"]
        tipo = request.form["tipo"]
        quantidade = request.form["quantidade"]
        descricao = request.form["descricao"]

        cursor.execute("""
            UPDATE inventory
            SET nome = ?, tipo = ?, quantidade = ?, descricao = ?
            WHERE id = ?
        """, (nome, tipo, quantidade, descricao, item_id))
        conn.commit()
        conn.close()
        return redirect(url_for("inventory"))

    # GET → mostra os dados atuais no formulário
    cursor.execute("SELECT * FROM inventory WHERE id = ?", (item_id,))
    item = cursor.fetchone()
    conn.close()
    return render_template("inventory_form.html", item=item, edit=True)

@app.route('/search')
def search():
    q = request.args.get('q','').strip()
    rentals = []
    items = []
    if q:
        rentals = query_db("SELECT * FROM rentals WHERE professor LIKE ? OR materia LIKE ? OR sala LIKE ? ORDER BY data_hora DESC",
                           (f'%{q}%',f'%{q}%',f'%{q}%'))
        items = query_db("SELECT * FROM inventory WHERE nome LIKE ? OR tipo LIKE ? OR descricao LIKE ?",
                         (f'%{q}%',f'%{q}%',f'%{q}%'))
    return render_template('index.html', search_query=q, search_rentals=rentals, search_items=items)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)