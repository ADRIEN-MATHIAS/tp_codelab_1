from collections.abc import Iterable, Sequence
from datetime import date


def _lire_date_iso(valeur: str) -> date:
    
    jour = date.fromisoformat(valeur)
    if jour.isoformat() != valeur:
        raise ValueError("La date doit être au format AAAA-MM-JJ.")
    return jour



# Répartit un montant en centimes; le reste revient au premier participant
def repartir_centimes(montant_centimes: int, participants: Sequence[int]) -> dict[int, int]: #Sequence[int] est un type générique qui représente une séquence d'entiers (comme une liste ou un tuple) -> moins restrictif que demander une liste ou un tuple spécifique
    
    if not isinstance(montant_centimes, int) or montant_centimes < 0:
        raise ValueError("Le montant doit être un nombre entier positif ou nul.")
    if not participants:
        raise ValueError("Il faut au moins un participant.")
    if len(set(participants)) != len(participants):
        raise ValueError("Un participant ne peut apparaître qu'une fois.")

    part, reste = divmod(montant_centimes, len(participants)) #divmod renvoie le quotient et le reste de la division entière
    return {
        membre_id: part + (index < reste) #membre_id est la clé, part + (index < reste) est la valeur
        for index, membre_id in enumerate(participants)
    }



#Rappel de pq utiliser Iterable ou Sequence:
    #Si tu dois juste boucler dessus ➔ Iterable
    # Si tu dois boucler + connaître la taille + conserver l'ordre ➔ Sequence
    # Si tu dois modifier les données (ajouter/supprimer des éléments avec .append()) ➔ list ou MutableSequence


# Retourne les soldes nets en centimes (montant payé moins montant dû)
def calculer_soldes(
    membres: Iterable[int], #Iterable[int] est un type générique qui représente une séquence d'entiers (comme une liste ou un tuple)
    depenses: Iterable[tuple[int, int, Sequence[int]]], 
) -> dict[int, int]:
    
    soldes = {membre_id: 0 for membre_id in membres} # soldes = dictionnaire où chaque membre du groupe a un solde initial de 0 centimes

    for montant_centimes, payeur_id, participants in depenses:
        if payeur_id not in soldes:
            raise ValueError("Le payeur ne fait pas partie du groupe.")
        if any(membre_id not in soldes for membre_id in participants):
            raise ValueError("Un participant ne fait pas partie du groupe.")

        soldes[payeur_id] += montant_centimes
        for membre_id, part in repartir_centimes(montant_centimes, participants).items():
            soldes[membre_id] -= part # le solde du membre est diminué de sa part de la dépense

    return soldes



# Vérifie les dates ISO d'un séjour et leur ordre chronologique.
def valider_sejour(date_debut: str, date_fin: str) -> None:
    try:
        debut = _lire_date_iso(date_debut)
        fin = _lire_date_iso(date_fin)
    except ValueError as erreur:
        raise ValueError("Les dates du séjour sont invalides.") from erreur

    if debut > fin:
        raise ValueError("La date de début doit précéder ou égaler la date de fin.")



def valider_depense(
    montant_centimes: int,
    date_depense: str,
    date_debut: str,
    date_fin: str,
    participants: Sequence[int],
) -> None:
    """Vérifie les règles métier d'une dépense."""
    if montant_centimes <= 0:
        raise ValueError("Le montant doit être supérieur à 0 €.")
    if not participants:
        raise ValueError("Sélectionnez au moins un participant.")
    if len(set(participants)) != len(participants):
        raise ValueError("Un participant ne peut apparaître qu'une fois.")

    valider_sejour(date_debut, date_fin)
    try:
        jour_depense = _lire_date_iso(date_depense)
        debut = _lire_date_iso(date_debut)
        fin = _lire_date_iso(date_fin)
    except ValueError as erreur:
        raise ValueError("La date de la dépense est invalide.") from erreur

    if not debut <= jour_depense <= fin:
        raise ValueError("La date de la dépense doit être comprise dans le séjour.")
