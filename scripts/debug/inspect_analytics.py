from sqlmodel import select
from app.db import get_session
from app.models_structure import (
    EntiteGeographique, Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit
)

sess = next(get_session())

egs = sess.exec(select(EntiteGeographique)).all()
print('Entités géographiques:', [(e.id, getattr(e, 'name', None), getattr(e, 'identifier', None)) for e in egs])
if not egs:
    print('No EntiteGeographique found; analytics will be empty')
    raise SystemExit(0)

eg_id = egs[0].id
print('\nUsing EG id:', eg_id)

poles = sess.exec(select(Pole).where(Pole.entite_geo_id == eg_id)).all()
print('Pôles:', [(p.id, getattr(p, 'name', None)) for p in poles])

service_ids = [p.id for p in poles]
services = sess.exec(select(Service).where(Service.pole_id.in_([p.id for p in poles]))).all() if poles else []
print('Services:', [(s.id, getattr(s, 'name', None), getattr(s, 'identifier', None)) for s in services])

for service in services:
    print('\nService:', service.id, getattr(service, 'name', None))
    ufs = sess.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.service_id == service.id)).all()
    print('  UFs:', [(uf.id, getattr(uf, 'name', None), getattr(uf, 'um_code', None)) for uf in ufs])
    for uf in ufs:
        uhs = sess.exec(select(UniteHebergement).where(UniteHebergement.unite_fonctionnelle_id == uf.id)).all()
        print('    UH count:', len(uhs))
        for uh in uhs:
            chs = sess.exec(select(Chambre).where(Chambre.unite_hebergement_id == uh.id)).all()
            print('      UH:', uh.id, getattr(uh, 'name', None), 'Chambres:', [(c.id, getattr(c,'name',None)) for c in chs])
            for ch in chs:
                lits = sess.exec(select(Lit).where(Lit.chambre_id == ch.id)).all()
                print('        Chambre', ch.id, getattr(ch,'name',None), 'lits:', [(l.id, getattr(l,'name',None) or getattr(l,'identifier',None)) for l in lits])

# Summary counts
beds_total = sess.exec(select(Lit)).all()
print('\nTotal lits in DB:', len(beds_total))

print('\nDone')
