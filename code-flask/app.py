from flask import Flask, redirect, render_template, request

from base import ouvrir_base

app = Flask(__name__)


# Page d'accueil : lit les membres et affiche PAGE.
@app.get("/")
def accueil():
    with ouvrir_base() as conn:
        membres = conn.execute("SELECT nom FROM membres").fetchall()
        
    return render_template("index.html", membres=membres)


# Exemple : reçoit le formulaire et ajoute un membre au groupe 1.
@app.post("/membres")
def ajouter_membre():
    nom = request.form["nom"]
    with ouvrir_base() as conn:
        conn.execute("INSERT INTO membres (groupe_id, nom) VALUES (1, ?)", [nom])
    return redirect("/")


# Ajoutez vos fonctions ici. Le HTML va dans PAGE.


if __name__ == "__main__":
    app.run(debug=True)
