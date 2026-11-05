from flask import Flask, redirect, render_template, request

from base import ouvrir_base

app = Flask(__name__)


# Page d'accueil : lit les membres et affiche PAGE.
@app.get("/")
def accueil():
    with ouvrir_base() as conn:
        nb_groupes = conn.execute("SELECT COUNT(*) FROM groupes").fetchone()[0]
        nb_membres = conn.execute("SELECT COUNT(*) FROM membres").fetchone()[0]
        nb_depenses = conn.execute("SELECT COUNT(*) FROM depenses").fetchone()[0]

        membres = conn.execute("SELECT nom FROM membres").fetchall()
        
    return render_template("index.html", membres=membres, nb_groupes=nb_groupes, nb_membres=nb_membres, nb_depenses=nb_depenses)


# Exemple : reçoit le formulaire et ajoute un membre au groupe 1.
@app.post("/membres")
def ajouter_membre():
    nom = request.form["nom"]
    groupe_id = request.form.get("groupe_id")

    if not nom.strip() or not groupe_id:
        return redirect("/membres")
    with ouvrir_base() as conn:
        conn.execute("INSERT INTO membres (groupe_id, nom) VALUES (?, ?)", (int(groupe_id), nom.strip()))
    return redirect("/membres")

# Pages affichées

@app.get("/membres")
def membres():
    with ouvrir_base() as conn:
        groupes = conn.execute("SELECT id, nom FROM groupes").fetchall()
        # Jointure pour récupérer le nom du groupe (évite la KeyError dans membres.html)
        membres = conn.execute("""
            SELECT m.id, m.nom, g.nom as groupe 
            FROM membres m
            LEFT JOIN groupes g ON m.groupe_id = g.id
        """).fetchall()
    return render_template("membres.html", membres=membres, groupes=groupes)

@app.get("/depenses")
def depenses():
    return render_template("depenses.html")

@app.get("/groupes")
def groupes():
    with ouvrir_base() as conn:
        groupes = conn.execute(
            "SELECT id, nom, date_debut, date_fin FROM groupes"
        ).fetchall()

    return render_template("groupes.html", groupes=groupes)

@app.post("/groupes")
def ajouter_groupe():
    nom = request.form["nom"].strip()
    date_debut = request.form["date_debut"]
    date_fin = request.form["date_fin"]

    if not nom or not date_debut or not date_fin:
        return redirect("/groupes")

    if date_fin < date_debut:
        return redirect("/groupes")

    with ouvrir_base() as conn:
        conn.execute(
            """
            INSERT INTO groupes (nom, date_debut, date_fin)
            VALUES (?, ?, ?)
            """,
            (nom, date_debut, date_fin)
        )

    return redirect("/groupes")

# Ajoutez vos fonctions ici. Le HTML va dans PAGE.


if __name__ == "__main__":
    app.run(debug=True)
