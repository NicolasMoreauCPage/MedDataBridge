#!/usr/bin/env python3
"""Script rapide de vérification des namespaces créés."""
from sqlmodel import Session, select
from app.db import engine
from app.models_structure_fhir import IdentifierNamespace, EntiteJuridique

with Session(engine) as s:
    ns_list = s.exec(select(IdentifierNamespace)).all()
    ej_list = s.exec(select(EntiteJuridique)).all()
    
    print(f"Namespaces créés: {len(ns_list)}")
    print(f"Entités juridiques: {len(ej_list)}")
    print("\nNamespaces par type:")
    for n in ns_list:
        ej_info = f" (EJ: {n.entite_juridique_id})" if n.entite_juridique_id else ""
        print(f"  - {n.name} | type={n.type} | OID={n.oid}{ej_info}")
