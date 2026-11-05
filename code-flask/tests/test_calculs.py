import pytest

from calculs import calculer_soldes, repartir_centimes, valider_depense, valider_sejour


MEMBRES = [1, 2, 3]


def test_soldes_pour_trente_euros():
    depenses = [(3000, 1, [1, 2, 3])]

    assert calculer_soldes(MEMBRES, depenses) == {1: 2000, 2: -1000, 3: -1000}


def test_soldes_repartissent_exactement_les_centimes():
    depenses = [(1000, 1, [1, 2, 3])]

    assert calculer_soldes(MEMBRES, depenses) == {1: 666, 2: -333, 3: -333}


def test_reste_attribue_au_premier_participant_dans_l_ordre_recu():
    assert repartir_centimes(1000, [3, 1, 2]) == {3: 334, 1: 333, 2: 333}


def test_somme_des_soldes_est_nulle_pour_plusieurs_depenses():
    depenses = [(1001, 1, [1, 2, 3]), (500, 2, [1, 2])]

    assert sum(calculer_soldes(MEMBRES, depenses).values()) == 0


@pytest.mark.parametrize(
    ("montant", "jour", "participants"),
    [
        (0, "2026-07-02", [1]),
        (-1, "2026-07-02", [1]),
        (100, "2026-06-30", [1]),
        (100, "2026-07-09", [1]),
        (100, "2026-07-02", []),
        (100, "date invalide", [1]),
    ],
)
def test_depenses_invalides_sont_refusees(montant, jour, participants):
    with pytest.raises(ValueError):
        valider_depense(
            montant, jour, "2026-07-01", "2026-07-08", participants
        )


def test_bornes_du_sejour_sont_incluses():
    valider_depense(100, "2026-07-01", "2026-07-01", "2026-07-08", [1])
    valider_depense(100, "2026-07-08", "2026-07-01", "2026-07-08", [1])


def test_refuse_les_dates_non_iso():
    with pytest.raises(ValueError):
        valider_sejour("2026W27-3", "2026-07-08")


@pytest.mark.parametrize(
    ("debut", "fin"),
    [("2026-07-09", "2026-07-01"), ("date invalide", "2026-07-08")],
)
def test_sejour_invalide(debut, fin):
    with pytest.raises(ValueError):
        valider_sejour(debut, fin)


def test_calcul_refuse_un_payeur_hors_du_groupe():
    with pytest.raises(ValueError, match="payeur"):
        calculer_soldes(MEMBRES, [(100, 4, [1])])


def test_calcul_refuse_un_participant_hors_du_groupe():
    with pytest.raises(ValueError, match="participant"):
        calculer_soldes(MEMBRES, [(100, 1, [4])])
