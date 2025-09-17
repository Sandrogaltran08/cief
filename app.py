from flask import Flask, render_template, request, redirect, url_for, Response, send_file
import sqlite3
import os
from datetime import datetime
import csv

import hashlib

# Patch: sobrescreve md5 para ignorar o argumento usado pelo reportlab
def md5_patch(*args, **kwargs):
    return hashlib.md5()

import reportlab.pdfbase.pdfdoc as pdfdoc
pdfdoc.md5 = md5_patch


from reportlab.pdfgen import canvas
import io
from openpyxl import Workbook
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet


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


# Helpers
def query_db(query, args=(), one=False, commit=False):
    conn = sqlite3.connect(DB_NAME)  # <- corrigido, estava "/almox.db"
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
    conn.row_factory = sqlite3.Row  # 🔑 agora cada linha vira um "dict-like"
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
        turma = request.form["turma"]
        data = request.form["data"]  # ex: 17/09/2025
        hora = request.form["hora"]  # ex: 14:30
        tempo_uso = request.form["tempo_uso"]
        equipamento = request.form["equipamento"]

        # 🔄 Converte para formato padrão ISO antes de salvar no banco
        data_hora = datetime.strptime(f"{data} {hora}", "%d/%m/%Y %H:%M")

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO rentals (professor, materia, sala, turma, data_hora, tempo_uso, equipamento, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (professor, materia, sala, turma, data_hora.strftime("%Y-%m-%d %H:%M:%S"), tempo_uso, equipamento,
              "Em Uso"))
        conn.commit()
        conn.close()

        return redirect(url_for("rentals"))

    return render_template("rental_form.html")


# ----------------- INVENTÁRIO ----------------- #
@app.route("/inventory")
def inventory():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # <-- aqui
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
    q = request.args.get('q', '').strip()
    rentals = []
    items = []
    if q:
        rentals = query_db(
            "SELECT * FROM rentals WHERE professor LIKE ? OR materia LIKE ? OR sala LIKE ? ORDER BY data_hora DESC",
            (f'%{q}%', f'%{q}%', f'%{q}%'))
        items = query_db("SELECT * FROM inventory WHERE nome LIKE ? OR tipo LIKE ? OR descricao LIKE ?",
                         (f'%{q}%', f'%{q}%', f'%{q}%'))
    return render_template('index.html', search_query=q, search_rentals=rentals, search_items=items)


@app.template_filter("datetime_br")
def datetime_br(value):
    """Converte datetime ISO (do input HTML) para formato brasileiro DD/MM/AAAA HH:MM"""
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return value  # se der erro, retorna o valor original


@app.route("/rentals/delete/<int:rental_id>", methods=["POST"])
def delete_rental(rental_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM rentals WHERE id = ?", (rental_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("rentals"))


@app.route("/inventory/export/pdf")
def export_inventory_pdf():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, tipo, quantidade, descricao FROM inventory")
    rows = cursor.fetchall()
    conn.close()

    file_path = "inventory_report.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=letter)
    styles = getSampleStyleSheet()

    # Cabeçalho correto
    data = [["ID", "Nome", "Tipo", "Quantidade", "Descrição"]]

    for row in rows:
        data.append(row)

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements = []
    elements.append(Paragraph("Relatório de Inventário", styles["Title"]))
    elements.append(table)

    doc.build(elements)

    return send_file(file_path, as_attachment=True)


@app.route("/rentals/export/pdf")
def export_rentals_pdf():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, professor, materia, sala, turma, data_hora, tempo_uso, equipamento, status FROM rentals")
    rows = cursor.fetchall()
    conn.close()

    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(30, 750, "Relatório de Locações")

    y = 720
    for row in rows:
        c.drawString(30, y,
                     f"ID: {row[0]} | Prof: {row[1]} | Matéria: {row[2]} | Sala: {row[3]} | Turma: {row[4]} | Data: {row[5]} | Tempo: {row[6]} | Equip: {row[7]} | Status: {row[8]}")
        y -= 20
        if y < 50:  # quebra de página se necessário
            c.showPage()
            c.setFont("Helvetica", 12)
            y = 750

    c.save()
    output.seek(0)

    return send_file(output, as_attachment=True,
                     download_name="rentals.pdf",
                     mimetype="application/pdf")


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
