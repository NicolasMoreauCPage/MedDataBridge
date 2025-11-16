"""Vérifier les structures créées pour le message 20250206141011."""
from app.db import get_session
from app.models_structure import EntiteJuridique, EntiteGeographique, Pole
from app.models_structure import Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
from sqlmodel import select

s = next(get_session())

# Récupérer l'EJ du GHT TEST Nico créée par l'import
ej = s.exec(
    select(EntiteJuridique)
    .where(
        EntiteJuridique.finess_ej == '700004591',
        EntiteJuridique.ght_context_id == 2
    )
).first()

if not ej:
    print("❌ EJ non trouvée!")
    exit(1)

print(f"EJ: {ej.name} (FINESS: {ej.finess_ej}, GHT_ID: {ej.ght_context_id})")
print(f"EJ ID: {ej.id}\n")

# EG liées à cette EJ
egs = s.exec(select(EntiteGeographique).where(EntiteGeographique.entite_juridique_id == ej.id)).all()
print(f"📊 Entités Géographiques: {len(egs)}")
for eg in egs[:3]:
    print(f"  - {eg.name} (ID: {eg.id})")
if len(egs) > 3:
    print(f"  ... et {len(egs) - 3} autres")

# Pôles
poles = s.exec(
    select(Pole)
    .join(EntiteGeographique)
    .where(EntiteGeographique.entite_juridique_id == ej.id)
).all()
print(f"\n🏢 Pôles: {len(poles)}")
for pole in poles[:3]:
    print(f"  - {pole.name} (ID: {pole.id}, EG_ID: {pole.entite_geo_id})")

# Services
services = s.exec(
    select(Service)
    .join(Pole)
    .join(EntiteGeographique)
    .where(EntiteGeographique.entite_juridique_id == ej.id)
).all()
print(f"\n🏥 Services: {len(services)}")
for srv in services[:5]:
    print(f"  - {srv.name} (ID: {srv.id}, Pole_ID: {srv.pole_id})")
if len(services) > 5:
    print(f"  ... et {len(services) - 5} autres")

# UF
ufs = s.exec(
    select(UniteFonctionnelle)
    .join(Service)
    .join(Pole)
    .join(EntiteGeographique)
    .where(EntiteGeographique.entite_juridique_id == ej.id)
).all()
print(f"\n🔬 Unités Fonctionnelles: {len(ufs)}")
for uf in ufs[:5]:
    print(f"  - {uf.name} (ID: {uf.id}, Service_ID: {uf.service_id})")
if len(ufs) > 5:
    print(f"  ... et {len(ufs) - 5} autres")

# UH
uhs = s.exec(
    select(UniteHebergement)
    .join(UniteFonctionnelle)
    .join(Service)
    .join(Pole)
    .join(EntiteGeographique)
    .where(EntiteGeographique.entite_juridique_id == ej.id)
).all()
print(f"\n🏠 Unités d'Hébergement: {len(uhs)}")

# Chambres
chambres = s.exec(
    select(Chambre)
    .join(UniteHebergement)
    .join(UniteFonctionnelle)
    .join(Service)
    .join(Pole)
    .join(EntiteGeographique)
    .where(EntiteGeographique.entite_juridique_id == ej.id)
).all()
print(f"\n🚪 Chambres: {len(chambres)}")

# Lits
lits = s.exec(
    select(Lit)
    .join(Chambre)
    .join(UniteHebergement)
    .join(UniteFonctionnelle)
    .join(Service)
    .join(Pole)
    .join(EntiteGeographique)
    .where(EntiteGeographique.entite_juridique_id == ej.id)
).all()
print(f"\n🛏️  Lits: {len(lits)}")

print("\n" + "="*50)
print(f"TOTAL STRUCTURES CRÉÉES:")
print(f"  EG: {len(egs)}")
print(f"  Pôles: {len(poles)}")
print(f"  Services: {len(services)}")
print(f"  UF: {len(ufs)}")
print(f"  UH: {len(uhs)}")
print(f"  Chambres: {len(chambres)}")
print(f"  Lits: {len(lits)}")
