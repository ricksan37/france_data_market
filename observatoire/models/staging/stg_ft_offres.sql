select
    offre.id as offre_id,
    offre.intitule as intitule,
    offre.dateCreation::timestamp as date_creation,
    offre.dateActualisation::timestamp as date_actualisation,
    offre.romeCode as rome_code,
    offre.romeLibelle as rome_libelle,
    offre.typeContrat as type_contrat,
    offre.experienceExige as experience_exige,
    offre.lieuTravail.codePostal as code_postal,
    offre.lieuTravail.commune as commune,
    offre.entreprise.nom as entreprise_nom,
    offre.codeNaf as code_naf,
    offre.salaire.libelle as salaire_libelle,
    offre.nombrePostes as nombre_postes
from {{ source('raw', 'ft_offres') }},
     unnest(resultats) as t(offre)
     qualify row_number() over (partition by offre_id order by date_actualisation desc) = 1