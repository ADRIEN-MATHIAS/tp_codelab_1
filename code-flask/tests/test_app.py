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
