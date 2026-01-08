from typing import Tuple, List, Dict
from sqlmodel import Session
from app.models_structure import (
    EntiteGeographique, Pole, Service, UniteFonctionnelle,
    UniteHebergement, Chambre, Lit, LocationStatus,
)


def build_structure_tree_for_template(session: Session, eg: EntiteGeographique) -> Tuple[List[dict], Dict[str,int], int]:
    """Build a structure_tree shaped for templates (nodes with 'entity' and nested lists).

    Returns: (structure_tree, lit_operational, lits_actifs)
    """
    structure_tree = []
    lit_operational: Dict[str, int] = {}
    lits_actifs = 0

    # Iterate ORM relationships available on eg. This keeps behavior simple and lazy-friendly.
    for pole in getattr(eg, "poles", []) or []:
        pole_node = {"entity": pole, "services": []}
        for service in getattr(pole, "services", []) or []:
            service_node = {"entity": service, "ufs": []}
            for uf in getattr(service, "unites_fonctionnelles", []) or []:
                uf_node = {"entity": uf, "uhs": []}
                for uh in getattr(uf, "unites_hebergement", []) or []:
                    uh_node = {"entity": uh, "chambres": []}
                    for chambre in getattr(uh, "chambres", []) or []:
                        chambre_node = {"entity": chambre, "lits": []}
                        for lit in getattr(chambre, "lits", []) or []:
                            lit_node = {"id": lit.id, "name": lit.name, "identifier": getattr(lit, "identifier", None)}
                            chambre_node["lits"].append(lit_node)
                            op = getattr(lit, "operational_status", None) or "unknown"
                            lit_operational[op] = lit_operational.get(op, 0) + 1
                            if getattr(lit, "status", None) == LocationStatus.ACTIVE:
                                lits_actifs += 1
                        uh_node["chambres"].append(chambre_node)
                    uf_node["uhs"].append(uh_node)
                service_node["ufs"].append(uf_node)
            pole_node["services"].append(service_node)
        structure_tree.append(pole_node)

    return structure_tree, lit_operational, lits_actifs
