import pytest
from flask import template_rendered

import base
from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(base, "BASE", tmp_path / "data.db")
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_accueil(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"Alice" in response.data


@pytest.mark.parametrize(
    ("page", "contenu"),
    [
        ("/", "Alice"),
        ("/groupes", "Vacances à Spa"),
        ("/membres", "Chloé"),
        ("/depenses", "Courses"),
    ],
)
def test_les_pages_affichent_les_donnees_de_la_base(client, page, contenu):
    response = client.get(page)

    assert response.status_code == 200
    assert contenu.encode() in response.data


def test_page_depenses_propose_un_formulaire_complet(client):
    response = client.get("/depenses")

    assert response.status_code == 200
    assert b'name="groupe_id"' in response.data
    assert b'name="payeur_id"' in response.data
    assert b'name="participants"' in response.data
    assert b'name="type"' in response.data


def test_accueil_calcule_les_soldes_du_groupe(client):
    contexte = {}

    def capturer_contexte(sender, template, context):
        contexte.update(context)

    template_rendered.connect(capturer_contexte, app)
    try:
        response = client.get("/")
    finally:
        template_rendered.disconnect(capturer_contexte, app)

    assert response.status_code == 200
    assert [solde["solde_centimes"] for solde in contexte["soldes"]] == [
        2000,
        -1000,
        -1000,
    ]


def test_creer_groupe_et_ajouter_un_membre(client):
    response = client.post(
        "/groupes",
        data={
            "nom": "Weekend",
            "date_debut": "2026-07-01",
            "date_fin": "2026-07-03",
        },
    )
    assert response.status_code == 302
    assert "groupe_id=2" in response.headers["Location"]

    response = client.post(
        "/groupes/2/membres",
        data={"nom": "Dana"},
    )
    assert response.status_code == 302

    with base.ouvrir_base() as conn:
        membre = conn.execute(
            "SELECT nom, groupe_id FROM membres WHERE nom = 'Dana'"
        ).fetchone()
    assert tuple(membre) == ("Dana", 2)


def test_ajouter_puis_supprimer_une_depense(client):
    response = client.post(
        "/depenses",
        data={
            "groupe_id": "1",
            "libelle": "Diner",
            "montant": "10.00",
            "date": "2026-07-02",
            "payeur_id": "1",
            "participants": ["1", "2", "3"],
        },
    )
    assert response.status_code == 302

    with base.ouvrir_base() as conn:
        depense = conn.execute(
            "SELECT id, montant_centimes FROM depenses WHERE libelle = 'Diner'"
        ).fetchone()
        participants = conn.execute(
            "SELECT membre_id FROM participants WHERE depense_id = ? ORDER BY rowid",
            (depense["id"],),
        ).fetchall()
    assert tuple(depense)[1] == 1000
    assert [participant["membre_id"] for participant in participants] == [1, 2, 3]

    response = client.post(f"/depenses/{depense['id']}/supprimer")
    assert response.status_code == 302
    with base.ouvrir_base() as conn:
        assert conn.execute(
            "SELECT 1 FROM depenses WHERE id = ?", (depense["id"],)
        ).fetchone() is None


def test_ajout_depense_depuis_sa_page_affiche_la_nouvelle_depense(client):
    response = client.post(
        "/depenses",
        data={
            "groupe_id": "1",
            "libelle": "Diner",
            "montant": "10.00",
            "date": "2026-07-02",
            "payeur_id": "1",
            "participants": ["1", "2"],
        },
    )

    assert response.status_code == 302
    assert "/depenses?groupe_id=1" in response.headers["Location"]
    response = client.get(response.headers["Location"])
    assert b"Diner" in response.data
    assert b"Alice, Bob" in response.data


@pytest.mark.parametrize(
    ("montant", "jour"),
    [("0.00", "2026-07-02"), ("10.00", "2026-07-09"), ("1.001", "2026-07-02")],
)
def test_depense_invalide_n_est_pas_enregistree(client, montant, jour):
    response = client.post(
        "/depenses",
        data={
            "groupe_id": "1",
            "libelle": "Invalide",
            "montant": montant,
            "date": jour,
            "payeur_id": "1",
            "participants": ["1", "2", "3"],
        },
    )

    assert response.status_code == 302
    assert "erreur=" in response.headers["Location"]
    with base.ouvrir_base() as conn:
        assert conn.execute(
            "SELECT 1 FROM depenses WHERE libelle = 'Invalide'"
        ).fetchone() is None


def test_erreur_depense_est_affichee_sur_la_page_depenses(client):
    response = client.post(
        "/depenses",
        data={
            "groupe_id": "1",
            "libelle": "Invalide",
            "montant": "0",
            "date": "2026-07-02",
            "payeur_id": "1",
            "participants": ["1"],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Le montant doit être supérieur à 0 €.".encode() in response.data


def test_groupe_inexistant_affiche_une_erreur_sur_la_page_depenses(client):
    response = client.post(
        "/depenses",
        data={
            "groupe_id": "999",
            "libelle": "Courses",
            "montant": "10.00",
            "date": "2026-07-02",
            "payeur_id": "1",
            "participants": ["1"],
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Sélectionnez un groupe existant.".encode() in response.data


def test_refuse_un_payeur_d_un_autre_groupe(client):
    client.post(
        "/groupes",
        data={
            "nom": "Autre groupe",
            "date_debut": "2026-07-01",
            "date_fin": "2026-07-08",
        },
    )
    response = client.post(
        "/depenses",
        data={
            "groupe_id": "2",
            "libelle": "Mauvaise association",
            "montant": "10.00",
            "date": "2026-07-02",
            "payeur_id": "1",
            "participants": ["1"],
        },
    )

    assert "erreur=" in response.headers["Location"]
    with base.ouvrir_base() as conn:
        assert conn.execute(
            "SELECT 1 FROM depenses WHERE libelle = 'Mauvaise association'"
        ).fetchone() is None


def test_refuse_un_participant_choisi_plusieurs_fois(client):
    response = client.post(
        "/depenses",
        data={
            "groupe_id": "1",
            "libelle": "Participant duplique",
            "montant": "10.00",
            "date": "2026-07-02",
            "payeur_id": "1",
            "participants": ["1", "1"],
        },
    )

    assert "erreur=" in response.headers["Location"]
    with base.ouvrir_base() as conn:
        assert conn.execute(
            "SELECT 1 FROM depenses WHERE libelle = 'Participant duplique'"
        ).fetchone() is None

def test_ajouter_depense_avec_type_enregistre_et_affiche_le_type(client):
    # 1. Envoi d'une dépense avec un type spécifique
    response = client.post(
        "/depenses",
        data={
            "groupe_id": "1",
            "libelle": "Billets de train",
            "montant": "45.00",
            "date": "2026-07-03",
            "payeur_id": "1",
            "participants": ["1", "2"],
            "type": "Transport",
        },
    )
    assert response.status_code == 302

    # 2. Vérification de la persistance en base de données
    with base.ouvrir_base() as conn:
        depense = conn.execute(
            "SELECT type FROM depenses WHERE libelle = 'Billets de train'"
        ).fetchone()
    assert depense is not None
    assert depense["type"] == "Transport"

    # 3. Vérification de l'affichage sur la page des dépenses et à l'accueil
    page_depenses = client.get("/depenses?groupe_id=1")
    assert b"Transport" in page_depenses.data

    page_accueil = client.get("/?groupe_id=1")
    assert b"Transport" in page_accueil.data


def test_ajouter_depense_sans_type_utilise_la_valeur_par_defaut(client):
    # Envoi d'une dépense sans spécifier le champ 'type'
    response = client.post(
        "/depenses",
        data={
            "groupe_id": "1",
            "libelle": "Imprévu",
            "montant": "15.00",
            "date": "2026-07-04",
            "payeur_id": "1",
            "participants": ["1"],
        },
    )
    assert response.status_code == 302

    # Vérification que le fallback 'Autre' a bien été enregistré
    with base.ouvrir_base() as conn:
        depense = conn.execute(
            "SELECT type FROM depenses WHERE libelle = 'Imprévu'"
        ).fetchone()
    assert depense is not None
    assert depense["type"] == "Autre"