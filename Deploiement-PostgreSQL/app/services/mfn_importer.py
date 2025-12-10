"""
Importeur HL7 MFN^M05 pour structure hospitalière (LOC/LCH/LRL).

- Supporte Entité Juridique (M), Entité Géographique (ETBL_GRPQ), Service (D)
- Utilise les segments:
  * MSH/MFI/MFE: gestion de lots (informative)
  * LOC: type d'entité et clé source
  * LCH: caractéristiques (ID_GLBL, CD, LBL, LBL_CRT, FNS, etc.)
  * LRL: relation vers le parent (ETBLSMNT/LCLSTN)

Hypothèses (POC):
- On importe dans le GHT courant (fourni par le routeur); pour EG/EJ, liaison via LRL ETBLSMNT.
- Les Services (D) sont rattachés à un Pôle par défaut de l'EG parent.
"""
from __future__ import annotations


from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from sqlmodel import Session, select

from app.models_structure import GHTContext, EntiteJuridique
from app.models_structure import EntiteGeographique
from app.models_structure import (
    Pole, Service, UniteFonctionnelle, UniteHebergement, Chambre, Lit,
    LocationServiceType, LocationStatus, LocationMode, LocationPhysicalType
)


@dataclass
class RawEntity:
    """Représente une entité MFN collectée entre MFE/LOC/LCH/LRL."""
    type_code: str  # ex: "M", "ETBL_GRPQ", "D"
    key_composite: str  # valeur LOC-1 pour réconciliation si besoin
    props: Dict[str, str] = field(default_factory=dict)
    parent_refs: List[Tuple[str, str]] = field(default_factory=list)  # Liste de (parent_type_code, parent_code)

    def get(self, key: str, default: str = "") -> str:
        return self.props.get(key, default)
    
    @property
    def parent_ref(self) -> Optional[Tuple[str, str]]:
        """Compatibilité: retourne le premier parent."""
        return self.parent_refs[0] if self.parent_refs else None


def _parse_loc_composite(value: str) -> Tuple[Optional[str], Optional[str]]:
    """Extrait (type_code, code) d'une valeur composite de LOC/LRL style ^^^^^D^^^^0200&CPAGE&..&FINEJ
    Retourne (None, None) si non décodable.
    
    Format: ^^^^^TYPE^^^^CODE&...
    - Position 5 (après 5 ^) = TYPE
    - Position 9 (après 9 ^) = CODE&autres
    """
    if not value:
        return None, None
    # Retirer séparateurs CR/LF
    v = value.replace("\r", "").replace("\n", "")
    parts = v.split("^")
    try:
        type_code = parts[5] if len(parts) > 5 else None
        # Le code est à la position 9, avant le premier &
        code_part = parts[9] if len(parts) > 9 else None
        if code_part:
            code = code_part.split("&")[0]
        else:
            code = None
        return (type_code or None), (code or None)
    except Exception:
        return None, None


def parse_mfn_message(text: str) -> List[RawEntity]:
    """Parse le message MFN et retourne une liste d'entités brutes."""
    text = text.replace("\r", "\n")
    lines = [ln for ln in text.split("\n") if ln.strip()]

    entities: List[RawEntity] = []
    current: Optional[RawEntity] = None

    for line in lines:
        seg = line.split("|", 1)[0]
        fields = line.split("|")
        if seg == "MFE":
            # Démarre une nouvelle entité
            if current:
                entities.append(current)
            current = None
        elif seg == "LOC":
            # LOC-1 composite, LOC-3 type court/libellé
            comp = fields[1] if len(fields) > 1 else ""
            type_short = fields[3] if len(fields) > 3 else ""
            label = fields[4] if len(fields) > 4 else ""
            type_code, code = _parse_loc_composite(comp)
            # Certains messages mettent le code court en LOC-3 (ex: "D"); on privilégie composite
            t = type_code or type_short or ""
            current = RawEntity(type_code=t, key_composite=comp)
            if label:
                current.props["TYPE_LABEL"] = label
            if code:
                current.props["CD"] = code
        elif seg == "LCH" and current is not None:
            # LCH|composite|||KEY^Libellé^L|^VALUE
            # fields[4] contient KEY^Libellé^L, fields[5] contient ^VALUE
            key_field = fields[4] if len(fields) > 4 else ""
            val_field = fields[5] if len(fields) > 5 else ""
            # Extraire le premier élément avant ^ comme clé
            key_parts = key_field.split("^")
            key = key_parts[0] if key_parts else ""
            value = val_field[1:] if val_field.startswith("^") else val_field
            if key:
                current.props[key.strip()] = value.strip()
        elif seg == "LRL" and current is not None:
            # LRL|composite|||RELAT^...^L||PARENT_COMPOSITE
            # fields[4] contient RELAT^...^L, fields[6] contient le composite parent
            relation = fields[4] if len(fields) > 4 else ""
            parent_comp = fields[6] if len(fields) > 6 else ""
            import logging
            logger = logging.getLogger("app.services.mfn_importer")
            logger.info(f"[MFN-IMPORTER] Parsing LRL: ent_type={getattr(current, 'type_code', None)}, ent_code={current.props.get('CD', None)}, parent_comp='{parent_comp}'")
            p_type, p_code = _parse_loc_composite(parent_comp)
            if not p_type or not p_code:
                logger.warning(f"[MFN-IMPORTER] LRL parent non reconnu: composite='{parent_comp}', extrait: type='{p_type}', code='{p_code}' (ent_type={getattr(current, 'type_code', None)}, ent_code={current.props.get('CD', None)})")
            if p_type and p_code:
                current.parent_refs.append((p_type, p_code))
        # autres segments ignorés (MSH/MFI/NTE)

    if current:
        entities.append(current)

    return entities


def _get_or_create_default_pole(session: Session, eg: EntiteGeographique) -> Pole:
    pole = session.exec(select(Pole).where(Pole.entite_geo_id == eg.id).limit(1)).first()
    if pole:
        return pole
    pole = Pole(
        identifier=f"{eg.identifier}-POLE",
        name="Pôle par défaut",
        short_name="DEF",
        description="Pôle généré automatiquement lors de l'import MFN",
        status=LocationStatus.ACTIVE,
        mode=LocationMode.INSTANCE,
        physical_type=LocationPhysicalType.AREA,
        entite_geo_id=eg.id,
    )
    session.add(pole); session.commit(); session.refresh(pole)
    return pole


def import_mfn(text: str, session: Session, ght: GHTContext) -> Dict[str, int]:
    """Importe le message MFN dans la base pour le GHT donné.
    Retourne un résumé des entités créées/trouvées.
    """
    print("[MFN-IMPORTER] import_mfn called (print test)")
    import logging
    logger = logging.getLogger("app.services.mfn_importer")
    raw = parse_mfn_message(text)

    # Index existants par (type_code, code)
    index: Dict[Tuple[str, str], object] = {}

    created = {"ej": 0, "eg": 0, "service": 0, "uf": 0, "uh": 0, "chambre": 0, "lit": 0}
    updated = {"ej": 0, "eg": 0, "service": 0, "uf": 0, "uh": 0, "chambre": 0, "lit": 0}
    ignored = 0
    created_ids = {"ej": [], "eg": [], "service": [], "uf": [], "uh": [], "chambre": [], "lit": []}
    updated_ids = {"ej": [], "eg": [], "service": [], "uf": [], "uh": [], "chambre": [], "lit": []}

    # 1ère passe: créer EJ / EG sans relations
    # On itère pour créer EJ et EG, et indexer par (type, code)
    for ent in raw:
        t = (ent.type_code or "").upper()
        code = ent.get("CD")
        if not t or not code:
            ignored += 1
            continue
        if t == "M":
            # Entité Juridique
            finess_ej = ent.get("FNS")
            name = ent.get("LBL") or ent.get("TYPE_LABEL") or f"EJ {code}"
            short = ent.get("LBL_CRT") or None
            # Rechercher l'EJ existante DANS LE GHT ACTUEL
            existing = session.exec(
                select(EntiteJuridique).where(
                    EntiteJuridique.finess_ej == finess_ej,
                    EntiteJuridique.ght_context_id == ght.id
                )
            ).first() if finess_ej else None
            if existing:
                ej = existing
                updated["ej"] += 1
                updated_ids["ej"].append(code)
            else:
                created["ej"] += 1
                created_ids["ej"].append(code)
                ej = EntiteJuridique(
                    name=name,
                    short_name=short,
                    finess_ej=finess_ej or code,
                    address_line=ent.get("ADRS_1") or None,
                    postal_code=ent.get("CD_PSTL") or None,
                    city=ent.get("VL") or None,
                    ght_context_id=ght.id,
                )
                session.add(ej); session.commit(); session.refresh(ej)
            index[(t, code)] = ej
        elif t in {"ETBL_GRPQ"}:
            # Entité géographique
            finess = ent.get("FNS")
            identifier = ent.get("ID_GLBL") or f"EG-{code}"
            name = ent.get("LBL") or ent.get("TYPE_LABEL") or f"EG {code}"
            short = ent.get("LBL_CRT") or None
            # Rechercher l'EG existante par identifier (plus fiable que FINESS qui peut être partagé)
            # On ne filtre pas par GHT ici car l'EG sera liée à l'EJ qui elle est dans le bon GHT
            existing = session.exec(select(EntiteGeographique).where(EntiteGeographique.identifier == identifier)).first()
            if existing:
                eg = existing
                # Mettre à jour les infos si nécessaire
                eg.name = name
                eg.short_name = short
                eg.finess = finess or code
                session.add(eg)
                session.commit()
                session.refresh(eg)
                updated["eg"] += 1
                updated_ids["eg"].append(identifier)
            else:
                created["eg"] += 1
                created_ids["eg"].append(identifier)
                eg = EntiteGeographique(
                    identifier=identifier,
                    name=name,
                    short_name=short,
                    finess=finess or code,
                    address_line1=ent.get("ADRS_1") or None,
                    address_line2=ent.get("ADRS_2") or None,
                    address_line3=ent.get("ADRS_3") or None,
                    address_postalcode=ent.get("CD_PSTL") or None,
                    address_city=ent.get("VL") or None,
                )
                session.add(eg); session.commit(); session.refresh(eg)
                created["eg"] += 1
            index[(t, code)] = eg
        # Services et autres seront faits en 2e passe (besoin de parent)

    # 2e passe: relier EG -> EJ et créer Services sous EG
    for ent in raw:
        t = (ent.type_code or "").upper()
        code = ent.get("CD")
        if not t or not code:
            continue
        if t == "ETBL_GRPQ":
            eg = index.get((t, code))
            if not eg:
                continue
            # Chercher un parent EntiteJuridique parmi tous les parents possibles
            for p_type, p_code in ent.parent_refs:
                parent_ej = index.get((p_type, p_code))
                if not parent_ej and p_type == "M":
                    parent_ej = session.exec(select(EntiteJuridique).where(EntiteJuridique.identifier == p_code)).first()
                    if parent_ej:
                        logger.info(f"[MFN-IMPORTER] Parent EJ trouvé en BDD pour EG: code={code}, parent_code={p_code}")
                if isinstance(parent_ej, EntiteJuridique):
                    eg.entite_juridique_id = parent_ej.id
                    session.add(eg); session.commit(); session.refresh(eg)
                    break
        elif t in {"D", "SERV"}:
            # Créer Service sous EG parent (via LRL LCLSTN)
            parent_eg = None
            for p_type, p_code in ent.parent_refs:
                obj = index.get((p_type, p_code))
                if not obj and p_type == "ETBL_GRPQ":
                    db_eg = session.exec(select(EntiteGeographique).where(EntiteGeographique.identifier == p_code)).first()
                    if db_eg:
                        logger.info(f"[MFN-IMPORTER] Parent EG trouvé en BDD pour Service: code={code}, parent_code={p_code}")
                        obj = db_eg
                if isinstance(obj, EntiteGeographique):
                    parent_eg = obj
                    break
            if not parent_eg:
                continue
            pole = _get_or_create_default_pole(session, parent_eg)
            identifier = ent.get("CD")
            global_identifier = ent.get("ID_GLBL") or f"SRV-{identifier}"
            name = ent.get("LBL") or ent.get("TYPE_LABEL") or f"Service {identifier}"
            short = ent.get("LBL_CRT") or None
            service_type = LocationServiceType.MCO
            srv = session.exec(select(Service).where(Service.identifier == identifier)).first()
            if srv:
                srv.name = name
                srv.short_name = short
                srv.pole_id = pole.id
                srv.global_identifier = global_identifier
                updated["service"] += 1
                updated_ids["service"].append(identifier)
            else:
                created["service"] += 1
                created_ids["service"].append(identifier)
                srv = Service(
                    identifier=identifier,
                    global_identifier=global_identifier,
                    name=name,
                    short_name=short,
                    status=LocationStatus.ACTIVE,
                    mode=LocationMode.INSTANCE,
                    physical_type=LocationPhysicalType.SI,
                    service_type=service_type,
                    pole_id=pole.id,
                )
            session.add(srv); session.commit(); session.refresh(srv)
            index[(t, code)] = srv
        elif t in {"N", "UF"}:
            # Créer UniteFonctionnelle sous Service parent
            parent_srv = None
            for p_type, p_code in ent.parent_refs:
                obj = index.get((p_type, p_code))
                # Log détaillé sur la recherche du parent Service
                logger.info(f"[MFN-IMPORTER] Recherche parent Service pour UF: code={ent.get('CD')}, parent_type={p_type}, parent_code={p_code}, index_result={'FOUND' if isinstance(obj, Service) else 'None'}")
                if isinstance(obj, Service):
                    parent_srv = obj
                    break
            if not parent_srv:
                logger.warning(f"[MFN-IMPORTER] UF ignorée: code={ent.get('CD')}, type={t}, parent Service absent (codes parents: {[pr for pr in ent.parent_refs]})")
                ignored += 1
                continue
            identifier = ent.get("CD")
            global_identifier = ent.get("ID_GLBL") or f"UF-{identifier}"
            name = ent.get("LBL") or ent.get("TYPE_LABEL") or f"UF {identifier}"
            short = ent.get("LBL_CRT") or None
            uf = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == identifier)).first()
            if uf:
                uf.name = name
                uf.short_name = short
                uf.service_id = parent_srv.id
                uf.global_identifier = global_identifier
            else:
                uf = UniteFonctionnelle(
                    identifier=identifier,
                    global_identifier=global_identifier,
                    name=name,
                    short_name=short,
                    status=LocationStatus.ACTIVE,
                    mode=LocationMode.INSTANCE,
                    physical_type=LocationPhysicalType.WI,  # Aile
                    service_id=parent_srv.id,
                )
            session.add(uf); session.commit(); session.refresh(uf)
            index[(t, code)] = uf
        # Si absent de l'index, chercher dans la base
        if t in {"N", "UF"} and not parent_srv:
            for p_type, p_code in ent.parent_refs:
                if p_type == "D":
                    db_srv = session.exec(select(Service).where(Service.identifier == p_code)).first()
                    if db_srv:
                        logger.info(f"[MFN-IMPORTER] Parent Service trouvé en BDD pour UF: code={ent.get('CD')}, parent_code={p_code}")
                        parent_srv = db_srv
                        break
        elif t in {"R", "CHAMBRE"}:
            # Créer Chambre - parent peut être UF ou UniteHebergement
            parent_obj = None
            for p_type, p_code in ent.parent_refs:
                obj = index.get((p_type, p_code))
                if not obj and p_type in {"N", "UF"}:
                    db_uf = session.exec(select(UniteFonctionnelle).where(UniteFonctionnelle.identifier == p_code)).first()
                    if db_uf:
                        logger.info(f"[MFN-IMPORTER] Parent UF trouvé en BDD pour Chambre: code={code}, parent_code={p_code}")
                        obj = db_uf
                if not obj and p_type == "UH":
                    db_uh = session.exec(select(UniteHebergement).where(UniteHebergement.identifier == p_code)).first()
                    if db_uh:
                        logger.info(f"[MFN-IMPORTER] Parent UH trouvé en BDD pour Chambre: code={code}, parent_code={p_code}")
                        obj = db_uh
                if isinstance(obj, (UniteFonctionnelle, UniteHebergement)):
                    parent_obj = obj
                    break
            if not parent_obj:
                logger.warning(f"[MFN-IMPORTER] Chambre ignorée: code={code}, type={t}, parent absent (codes parents: {[pr for pr in ent.parent_refs]})")
                ignored += 1
                continue
            if isinstance(parent_obj, UniteFonctionnelle):
                uh_identifier = f"UH-{parent_obj.identifier}"
                uh = session.exec(select(UniteHebergement).where(UniteHebergement.identifier == uh_identifier)).first()
                if not uh:
                    uh = UniteHebergement(
                        identifier=uh_identifier,
                        name=f"Unité d'hébergement - {parent_obj.name}",
                        status=LocationStatus.ACTIVE,
                        mode=LocationMode.INSTANCE,
                        physical_type=LocationPhysicalType.FL,  # Étage
                        unite_fonctionnelle_id=parent_obj.id,
                    )
                    session.add(uh); session.commit(); session.refresh(uh)
                    created["uh"] += 1
                    created_ids["uh"].append(uh_identifier)
                parent_uh = uh
            elif isinstance(parent_obj, UniteHebergement):
                parent_uh = parent_obj
            else:
                continue
            identifier = ent.get("CD")
            global_identifier = ent.get("ID_GLBL") or f"CH-{identifier}"
            name = ent.get("LBL") or ent.get("TYPE_LABEL") or f"Chambre {identifier}"
            short = ent.get("LBL_CRT") or None
            chambre = session.exec(select(Chambre).where(Chambre.identifier == identifier)).first()
            if chambre:
                chambre.name = name
                chambre.short_name = short
                chambre.global_identifier = global_identifier
                chambre.unite_hebergement_id = parent_uh.id if parent_uh else None
                updated["chambre"] += 1
                updated_ids["chambre"].append(identifier)
            else:
                chambre = Chambre(
                    identifier=identifier,
                    global_identifier=global_identifier,
                    name=name,
                    short_name=short,
                    status=LocationStatus.ACTIVE,
                    mode=LocationMode.INSTANCE,
                    physical_type=LocationPhysicalType.RO,  # Room
                    unite_hebergement_id=parent_uh.id if parent_uh else None,
                )
                created["chambre"] += 1
                created_ids["chambre"].append(identifier)
            session.add(chambre); session.commit(); session.refresh(chambre)
            index[(t, code)] = chambre
        elif t in {"B", "LIT"}:
            # Créer Lit sous Chambre parent
            parent_ch = None
            for p_type, p_code in ent.parent_refs:
                obj = index.get((p_type, p_code))
                if not obj and p_type == "R":
                    db_ch = session.exec(select(Chambre).where(Chambre.identifier == p_code)).first()
                    if db_ch:
                        logger.info(f"[MFN-IMPORTER] Parent Chambre trouvé en BDD pour Lit: code={code}, parent_code={p_code}")
                        obj = db_ch
                if isinstance(obj, Chambre):
                    parent_ch = obj
                    break
            if not parent_ch:
                logger.warning(f"[MFN-IMPORTER] Lit ignoré: code={code}, type={t}, parent absent (codes parents: {[pr for pr in ent.parent_refs]})")
                ignored += 1
                continue
            identifier = ent.get("CD")
            global_identifier = ent.get("ID_GLBL") or f"LIT-{identifier}"
            name = ent.get("LBL") or ent.get("TYPE_LABEL") or f"Lit {identifier}"
            short = ent.get("LBL_CRT") or None
            lit = session.exec(select(Lit).where(Lit.identifier == identifier)).first()
            if lit:
                lit.name = name
                lit.short_name = short
                lit.chambre_id = parent_ch.id
                lit.global_identifier = global_identifier
                updated["lit"] += 1
                updated_ids["lit"].append(identifier)
            else:
                lit = Lit(
                    identifier=identifier,
                    global_identifier=global_identifier,
                    name=name,
                    short_name=short,
                    status=LocationStatus.ACTIVE,
                    mode=LocationMode.INSTANCE,
                    physical_type=LocationPhysicalType.BD,  # Bed
                    chambre_id=parent_ch.id,
                )
                created["lit"] += 1
                created_ids["lit"].append(identifier)
            session.add(lit); session.commit(); session.refresh(lit)
            index[(t, code)] = lit

    logger.info(f"[MFN-IMPORTER] Résumé: Créés: {created}, Mis à jour: {updated}, Ignorés: {ignored}")
    logger.info(f"[MFN-IMPORTER] Identifiants créés: {created_ids}")
    logger.info(f"[MFN-IMPORTER] Identifiants mis à jour: {updated_ids}")
    return created


# -------------------------------------------------------------
# Compatibilité tests: fonction attendue import_mfn_structure
# -------------------------------------------------------------
def import_mfn_structure(session: Session, message: str) -> Dict[str, int]:
    """Wrapper pour compatibilité avec anciens tests.

    Cherche un contexte GHT actif et délègue à import_mfn.
    """
    ght = session.exec(select(GHTContext).where(GHTContext.is_active == True)).first()  # noqa: E712
    if not ght:
        raise ValueError("Aucun contexte GHT actif pour import MFN")
    return import_mfn(message, session, ght)
