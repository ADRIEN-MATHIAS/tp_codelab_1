from decimal import Decimal, InvalidOperation

from flask import Flask, abort, redirect, render_template, request, url_for

from base import ouvrir_base
from calculs import calculer_soldes, repartir_centimes, valider_depense, valider_sejour

app = Flask(__name__)


def _id_formulaire(valeur: str | None, champ: str) -> int:
    try:
        identifiant = int(valeur or "")
    except ValueError as erreur:
        raise ValueError(f"Le champ {champ} est invalide.") from erreur
    if identifiant <= 0:
        raise ValueError(f"Le champ {champ} est invalide.")
    return identifiant


# Transforme un montant en euros (ex: "12.34") en centimes (ex: 1234)
def _montant_en_centimes(valeur: str) -> int:
    try:
        montant = Decimal(valeur)
    except InvalidOperation as erreur:
        raise ValueError("Saisissez un montant valide.") from erreur

    if not montant.is_finite():
        raise ValueError("Saisissez un montant valide.")
    centimes = montant * 100
    if centimes != centimes.to_integral_value():
        raise ValueError("Le montant ne peut pas dépasser deux décimales.")
    return int(centimes)


# Recup le groupe avec id le plus eleve (dernier groupe cree) pour l'afficher par defaut sur la page d'accueil
def _groupe_par_defaut(conn):
    return conn.execute(
        "SELECT id FROM groupes ORDER BY id DESC LIMIT 1"
    ).fetchone()


# Redirige vers la page d'accueil avec un message d'erreur
def _erreur(message: str, groupe_id: int | None = None):
    return redirect(
        url_for("accueil", groupe_id=groupe_id, erreur=message)
    )


# --- ROUTES GET (Affichage des pages) ---

@app.get("/")
def accueil():
    erreur = request.args.get("erreur")
    groupe_id_form = request.args.get("groupe_id")
    if groupe_id_form:
        try:
            groupe_id = _id_formulaire(groupe_id_form, "groupe")
        except ValueError:
            abort(400)
    else:
        groupe_id = None

    with ouvrir_base() as conn:
        groupes = conn.execute(
            "SELECT id, nom, date_debut, date_fin FROM groupes ORDER BY id"
        ).fetchall()
        if groupe_id is None:
            groupe_defaut = _groupe_par_defaut(conn)
            groupe_id = groupe_defaut["id"] if groupe_defaut else None

        groupe = None
        membres = []
        depenses = []
        soldes = []

        if groupe_id is not None:
            groupe = conn.execute(
                "SELECT id, nom, date_debut, date_fin FROM groupes WHERE id = ?",
                (groupe_id,),
            ).fetchone()
            if groupe is None:
                abort(404)

            membres = conn.execute(
                "SELECT id, nom FROM membres WHERE groupe_id = ? ORDER BY id",
                (groupe_id,),
            ).fetchall()
            depense_rows = conn.execute(
                """
                SELECT d.id, d.libelle, d.montant_centimes, d.date,
                       d.payeur_id, payeur.nom AS payeur
                FROM depenses AS d
                JOIN membres AS payeur ON payeur.id = d.payeur_id
                WHERE d.groupe_id = ?
                ORDER BY d.date, d.id
                """,
                (groupe_id,),
            ).fetchall()

            depense_ids = [depense["id"] for depense in depense_rows]
            participants_par_depense = {depense_id: [] for depense_id in depense_ids}
            if depense_ids:
                placeholders = ",".join("?" for _ in depense_ids)
                participants_rows = conn.execute(
                    f"""
                    SELECT p.depense_id, p.membre_id, m.nom
                    FROM participants AS p
                    JOIN membres AS m ON m.id = p.membre_id
                    WHERE p.depense_id IN ({placeholders})
                    ORDER BY p.rowid
                    """,
                    depense_ids,
                ).fetchall()
                for participant in participants_rows:
                    participants_par_depense[participant["depense_id"]].append(
                        {"id": participant["membre_id"], "nom": participant["nom"]}
                    )

            membres_ids = [membre["id"] for membre in membres]
            depenses_calcul = []
            paye_par_membre = {membre_id: 0 for membre_id in membres_ids}
            du_par_membre = {membre_id: 0 for membre_id in membres_ids}
            for depense_row in depense_rows:
                depense = dict(depense_row)
                participants = participants_par_depense[depense["id"]]
                depense["participants"] = participants
                depenses.append(depense)
                participant_ids = [participant["id"] for participant in participants]
                depenses_calcul.append(
                    (depense["montant_centimes"], depense["payeur_id"], participant_ids)
                )
                paye_par_membre[depense["payeur_id"]] += depense["montant_centimes"]
                for membre_id, part in repartir_centimes(
                    depense["montant_centimes"], participant_ids
                ).items():
                    du_par_membre[membre_id] += part

            soldes_par_membre = calculer_soldes(membres_ids, depenses_calcul)
            soldes = [
                {
                    "membre_id": membre["id"],
                    "nom": membre["nom"],
                    "paye_centimes": paye_par_membre[membre["id"]],
                    "du_centimes": du_par_membre[membre["id"]],
                    "solde_centimes": soldes_par_membre[membre["id"]],
                }
                for membre in membres
            ]

    return render_template(
        "index.html",
        groupes=groupes,
        groupe=groupe,
        groupe_id=groupe_id,
        membres=membres,
        depenses=depenses,
        soldes=soldes,
        erreur=erreur,
    )

# Tes routes GET séparées qui ont été conservées
@app.get("/membres")
def membres():
    with ouvrir_base() as conn:
        groupes = conn.execute("SELECT id, nom FROM groupes").fetchall()
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


# --- ROUTES POST (Traitement des données, par ton collègue) ---

@app.post("/groupes")
def ajouter_groupe():
    nom = request.form.get("nom", "").strip()
    date_debut = request.form.get("date_debut", "").strip()
    date_fin = request.form.get("date_fin", "").strip()
    try:
        if not nom:
            raise ValueError("Le nom du groupe est obligatoire.")
        valider_sejour(date_debut, date_fin)
    except ValueError as erreur:
        return _erreur(str(erreur))

    with ouvrir_base() as conn:
        resultat = conn.execute(
            "INSERT INTO groupes (nom, date_debut, date_fin) VALUES (?, ?, ?)",
            (nom, date_debut, date_fin),
        )
        groupe_id = resultat.lastrowid
    return redirect(url_for("accueil", groupe_id=groupe_id))


@app.post("/membres")
@app.post("/groupes/<int:groupe_id>/membres")
def ajouter_membre(groupe_id: int | None = None):
    nom = request.form.get("nom", "").strip()
    try:
        if groupe_id is None:
            valeur_id = request.form.get("groupe_id")
            if valeur_id:
                groupe_id = _id_formulaire(valeur_id, "groupe")
        if not nom:
            raise ValueError("Le nom du membre est obligatoire.")
    except ValueError as erreur:
        return _erreur(str(erreur), groupe_id)

    with ouvrir_base() as conn:
        if groupe_id is None:
            groupe = _groupe_par_defaut(conn)
            groupe_id = groupe["id"] if groupe else None
        if groupe_id is None or not conn.execute(
            "SELECT 1 FROM groupes WHERE id = ?", (groupe_id,)
        ).fetchone():
            return _erreur("Sélectionnez un groupe existant.", groupe_id)
        conn.execute(
            "INSERT INTO membres (groupe_id, nom) VALUES (?, ?)",
            (groupe_id, nom),
        )
    return redirect(url_for("accueil", groupe_id=groupe_id))


@app.post("/depenses")
def ajouter_depense():
    try:
        groupe_id = _id_formulaire(request.form.get("groupe_id"), "groupe")
        libelle = request.form.get("libelle", "").strip()
        if not libelle:
            raise ValueError("Le libellé de la dépense est obligatoire.")
        montant_centimes = _montant_en_centimes(
            request.form.get("montant", "").strip()
        )
        payeur_id = _id_formulaire(request.form.get("payeur_id"), "payeur")
        participants = [
            _id_formulaire(valeur, "participant")
            for valeur in request.form.getlist("participants")
        ]
        date_depense = request.form.get("date", "").strip()
    except ValueError as erreur:
        return _erreur(str(erreur))

    with ouvrir_base() as conn:
        groupe = conn.execute(
            "SELECT date_debut, date_fin FROM groupes WHERE id = ?", (groupe_id,)
        ).fetchone()
        if groupe is None:
            return _erreur("Sélectionnez un groupe existant.", groupe_id)

        membres = {
            membre["id"]
            for membre in conn.execute(
                "SELECT id FROM membres WHERE groupe_id = ?", (groupe_id,)
            ).fetchall()
        }
        if payeur_id not in membres:
            return _erreur("Le payeur doit appartenir au groupe.", groupe_id)
        if any(membre_id not in membres for membre_id in participants):
            return _erreur(
                "Tous les participants doivent appartenir au groupe.", groupe_id
            )

        try:
            valider_depense(
                montant_centimes,
                date_depense,
                groupe["date_debut"],
                groupe["date_fin"],
                participants,
            )
        except ValueError as erreur:
            return _erreur(str(erreur), groupe_id)

        with conn:
            resultat = conn.execute(
                """
                INSERT INTO depenses
                    (groupe_id, libelle, montant_centimes, date, payeur_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (groupe_id, libelle, montant_centimes, date_depense, payeur_id),
            )
            depense_id = resultat.lastrowid
            conn.executemany(
                "INSERT INTO participants (depense_id, membre_id) VALUES (?, ?)",
                [(depense_id, membre_id) for membre_id in participants],
            )

    return redirect(url_for("accueil", groupe_id=groupe_id))


@app.post("/depenses/<int:depense_id>/supprimer")
def supprimer_depense(depense_id: int):
    with ouvrir_base() as conn:
        depense = conn.execute(
            "SELECT groupe_id FROM depenses WHERE id = ?", (depense_id,)
        ).fetchone()
        if depense is None:
            abort(404)

        groupe_id_form = request.form.get("groupe_id")
        if groupe_id_form:
            try:
                groupe_id_form = _id_formulaire(groupe_id_form, "groupe")
            except ValueError:
                abort(400)
            if groupe_id_form != depense["groupe_id"]:
                abort(404)

        conn.execute("DELETE FROM depenses WHERE id = ?", (depense_id,))
        groupe_id = depense["groupe_id"]

    return redirect(url_for("accueil", groupe_id=groupe_id))


if __name__ == "__main__":
    app.run(debug=True)
