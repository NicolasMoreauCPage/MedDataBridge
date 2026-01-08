"""
Import/Export de structure hospitalière via Excel
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Request, Form
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from typing import Optional, Literal
import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation

from app.dependencies.db_deps import get_session
from app.models_structure import (
    EntiteGeographique, Pole, Service, UniteFonctionnelle,
    UniteHebergement, Chambre, Lit
)

router = APIRouter(prefix="/api/structure", tags=["Structure Import/Export"])
ui_router = APIRouter(prefix="/structure", tags=["Structure Import/Export UI"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/export/excel")
async def export_structure_excel(
    eg_id: Optional[int] = None,
    session: Session = Depends(get_session)
):
    """Export de la structure complète en Excel avec 7 feuilles"""
    
    wb = Workbook()
    
    # Style pour les en-têtes
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="3B82F6", end_color="3B82F6", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")
    
    # === FEUILLE 1: README ===
    ws_readme = wb.active
    ws_readme.title = "README"
    
    ws_readme['A1'] = "📋 Guide d'utilisation - Import/Export Structure"
    ws_readme['A1'].font = Font(size=16, bold=True, color="3B82F6")
    ws_readme.merge_cells('A1:D1')
    
    readme_content = [
        ("", ""),
        ("Ce fichier contient la structure complète de l'établissement.", ""),
        ("Chaque feuille représente un niveau hiérarchique :", ""),
        ("", ""),
        ("1. EntitesGeographiques", "Établissements ou sites géographiques"),
        ("2. Poles", "Pôles d'activité"),
        ("3. Services", "Services médicaux ou techniques"),
        ("4. UnitésFonctionnelles", "Unités fonctionnelles (UF)"),
        ("5. UnitesHebergement", "Unités d'hébergement (UH)"),
        ("6. Chambres", "Chambres"),
        ("7. Lits", "Lits individuels"),
        ("", ""),
        ("⚠️ IMPORTANT :", ""),
        ("- Les codes doivent être uniques", ""),
        ("- Respecter les références entre niveaux (eg_code existe dans Pôles)", ""),
        ("- Ne pas supprimer les en-têtes", ""),
        ("- Sauvegarder en .xlsx uniquement", ""),
        ("", ""),
        (f"📅 Généré le {datetime.now().strftime('%d/%m/%Y %H:%M')}", ""),
    ]
    
    for idx, (col_a, col_b) in enumerate(readme_content, start=2):
        ws_readme[f'A{idx}'] = col_a
        ws_readme[f'B{idx}'] = col_b
    
    ws_readme.column_dimensions['A'].width = 40
    ws_readme.column_dimensions['B'].width = 50
    
    # === FEUILLE 2: Entités Géographiques ===
    ws_eg = wb.create_sheet("EntitesGeographiques")
    
    eg_headers = ["code", "nom", "type_eg", "adresse", "ville", "code_postal", "telephone", "finess"]
    for idx, header in enumerate(eg_headers, start=1):
        cell = ws_eg.cell(row=1, column=idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    # Données
    query_eg = select(EntiteGeographique)
    if eg_id:
        query_eg = query_eg.where(EntiteGeographique.id == eg_id)
    
    egs = session.exec(query_eg).all()
    for row_idx, eg in enumerate(egs, start=2):
        ws_eg.cell(row=row_idx, column=1, value=eg.code or f"EG{eg.id}")
        ws_eg.cell(row=row_idx, column=2, value=eg.nom)
        ws_eg.cell(row=row_idx, column=3, value=eg.type_eg or "")
        ws_eg.cell(row=row_idx, column=4, value=eg.adresse or "")
        ws_eg.cell(row=row_idx, column=5, value=eg.ville or "")
        ws_eg.cell(row=row_idx, column=6, value=eg.code_postal or "")
        ws_eg.cell(row=row_idx, column=7, value=eg.telephone or "")
        ws_eg.cell(row=row_idx, column=8, value=eg.finess or "")
    
    for col in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
        ws_eg.column_dimensions[col].width = 18
    
    # === FEUILLE 3: Pôles ===
    ws_poles = wb.create_sheet("Poles")
    
    pole_headers = ["code", "nom", "eg_code", "responsable", "telephone"]
    for idx, header in enumerate(pole_headers, start=1):
        cell = ws_poles.cell(row=1, column=idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    query_poles = select(Pole)
    if eg_id:
        query_poles = query_poles.where(Pole.eg_id == eg_id)
    
    poles = session.exec(query_poles).all()
    for row_idx, pole in enumerate(poles, start=2):
        eg = session.get(EntiteGeographique, pole.eg_id) if pole.eg_id else None
        ws_poles.cell(row=row_idx, column=1, value=pole.code or f"POL{pole.id}")
        ws_poles.cell(row=row_idx, column=2, value=pole.nom)
        ws_poles.cell(row=row_idx, column=3, value=eg.code if eg else "")
        ws_poles.cell(row=row_idx, column=4, value="")
        ws_poles.cell(row=row_idx, column=5, value="")
    
    for col in ['A', 'B', 'C', 'D', 'E']:
        ws_poles.column_dimensions[col].width = 20
    
    # === FEUILLE 4: Services ===
    ws_services = wb.create_sheet("Services")
    
    service_headers = ["code", "nom", "pole_code", "um_code", "telephone", "responsable"]
    for idx, header in enumerate(service_headers, start=1):
        cell = ws_services.cell(row=1, column=idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    query_services = select(Service)
    if eg_id:
        query_services = query_services.where(Service.eg_id == eg_id)
    
    services = session.exec(query_services).all()
    for row_idx, service in enumerate(services, start=2):
        pole = session.get(Pole, service.pole_id) if service.pole_id else None
        ws_services.cell(row=row_idx, column=1, value=service.code or f"SRV{service.id}")
        ws_services.cell(row=row_idx, column=2, value=service.nom)
        ws_services.cell(row=row_idx, column=3, value=pole.code if pole else "")
        ws_services.cell(row=row_idx, column=4, value="")
        ws_services.cell(row=row_idx, column=5, value="")
        ws_services.cell(row=row_idx, column=6, value="")
    
    for col in ['A', 'B', 'C', 'D', 'E', 'F']:
        ws_services.column_dimensions[col].width = 20
    
    # === FEUILLE 5: Unités Fonctionnelles ===
    ws_ufs = wb.create_sheet("UnitésFonctionnelles")
    
    uf_headers = ["code", "nom", "service_code", "um_code", "type_uf", "capacite"]
    for idx, header in enumerate(uf_headers, start=1):
        cell = ws_ufs.cell(row=1, column=idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    query_ufs = select(UniteFonctionnelle)
    if eg_id:
        query_ufs = query_ufs.where(UniteFonctionnelle.eg_id == eg_id)
    
    ufs = session.exec(query_ufs).all()
    for row_idx, uf in enumerate(ufs, start=2):
        service = session.get(Service, uf.service_id) if uf.service_id else None
        ws_ufs.cell(row=row_idx, column=1, value=uf.code or f"UF{uf.id}")
        ws_ufs.cell(row=row_idx, column=2, value=uf.nom)
        ws_ufs.cell(row=row_idx, column=3, value=service.code if service else "")
        ws_ufs.cell(row=row_idx, column=4, value=uf.um_code or "")
        ws_ufs.cell(row=row_idx, column=5, value=uf.type_uf or "")
        ws_ufs.cell(row=row_idx, column=6, value="")
    
    for col in ['A', 'B', 'C', 'D', 'E', 'F']:
        ws_ufs.column_dimensions[col].width = 20
    
    # === FEUILLE 6: Unités d'Hébergement ===
    ws_uhs = wb.create_sheet("UnitesHebergement")
    
    uh_headers = ["code", "nom", "uf_code", "etage", "batiment", "capacite"]
    for idx, header in enumerate(uh_headers, start=1):
        cell = ws_uhs.cell(row=1, column=idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    query_uhs = select(UniteHebergement)
    if eg_id:
        query_uhs = query_uhs.where(UniteHebergement.eg_id == eg_id)
    
    uhs = session.exec(query_uhs).all()
    for row_idx, uh in enumerate(uhs, start=2):
        uf = session.get(UniteFonctionnelle, uh.uf_id) if uh.uf_id else None
        ws_uhs.cell(row=row_idx, column=1, value=uh.code or f"UH{uh.id}")
        ws_uhs.cell(row=row_idx, column=2, value=uh.nom)
        ws_uhs.cell(row=row_idx, column=3, value=uf.code if uf else "")
        ws_uhs.cell(row=row_idx, column=4, value=uh.etage or "")
        ws_uhs.cell(row=row_idx, column=5, value=uh.batiment or "")
        ws_uhs.cell(row=row_idx, column=6, value="")
    
    for col in ['A', 'B', 'C', 'D', 'E', 'F']:
        ws_uhs.column_dimensions[col].width = 20
    
    # === FEUILLE 7: Chambres ===
    ws_chambres = wb.create_sheet("Chambres")
    
    chambre_headers = ["numero", "uh_code", "capacite", "type_chambre"]
    for idx, header in enumerate(chambre_headers, start=1):
        cell = ws_chambres.cell(row=1, column=idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    query_chambres = select(Chambre)
    if eg_id:
        query_chambres = query_chambres.where(Chambre.eg_id == eg_id)
    
    chambres = session.exec(query_chambres).all()
    for row_idx, chambre in enumerate(chambres, start=2):
        uh = session.get(UniteHebergement, chambre.uh_id) if chambre.uh_id else None
        ws_chambres.cell(row=row_idx, column=1, value=chambre.numero)
        ws_chambres.cell(row=row_idx, column=2, value=uh.code if uh else "")
        ws_chambres.cell(row=row_idx, column=3, value=chambre.capacite or 1)
        ws_chambres.cell(row=row_idx, column=4, value=chambre.type_chambre or "")
    
    for col in ['A', 'B', 'C', 'D']:
        ws_chambres.column_dimensions[col].width = 20
    
    # === FEUILLE 8: Lits ===
    ws_lits = wb.create_sheet("Lits")
    
    lit_headers = ["numero", "chambre_numero", "uh_code", "type_lit", "statut"]
    for idx, header in enumerate(lit_headers, start=1):
        cell = ws_lits.cell(row=1, column=idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    query_lits = select(Lit)
    if eg_id:
        query_lits = query_lits.where(Lit.eg_id == eg_id)
    
    lits = session.exec(query_lits).all()
    for row_idx, lit in enumerate(lits, start=2):
        chambre = session.get(Chambre, lit.chambre_id) if lit.chambre_id else None
        uh = session.get(UniteHebergement, lit.uh_id) if lit.uh_id else None
        ws_lits.cell(row=row_idx, column=1, value=lit.numero)
        ws_lits.cell(row=row_idx, column=2, value=chambre.numero if chambre else "")
        ws_lits.cell(row=row_idx, column=3, value=uh.code if uh else "")
        ws_lits.cell(row=row_idx, column=4, value=lit.type_lit or "")
        ws_lits.cell(row=row_idx, column=5, value=lit.statut or "")
    
    for col in ['A', 'B', 'C', 'D', 'E']:
        ws_lits.column_dimensions[col].width = 20
    
    # Sauvegarder dans buffer
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    filename = f"structure_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/template")
async def export_template():
    """Télécharge un template Excel vierge avec exemples"""
    
    wb = Workbook()
    
    # Style en-têtes
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center")
    
    # Créer les feuilles avec une ligne d'exemple
    ws_eg = wb.active
    ws_eg.title = "EntitesGeographiques"
    eg_headers = ["code", "nom", "type_eg", "adresse", "ville", "code_postal", "telephone", "finess"]
    for idx, header in enumerate(eg_headers, start=1):
        cell = ws_eg.cell(row=1, column=idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
    
    # Exemple
    ws_eg['A2'] = "EG01"
    ws_eg['B2'] = "Centre Hospitalier Nord"
    ws_eg['C2'] = "CH"
    ws_eg['D2'] = "1 rue de la Santé"
    ws_eg['E2'] = "Paris"
    ws_eg['F2'] = "75001"
    ws_eg['G2'] = "01 23 45 67 89"
    ws_eg['H2'] = "750001234"
    
    for col in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
        ws_eg.column_dimensions[col].width = 18
    
    # Autres feuilles similaires...
    # (Code similaire pour Poles, Services, etc.)
    
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    
    filename = "template_structure.xlsx"
    
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# === UI Routes ===

@ui_router.get("/import", response_class=HTMLResponse)
async def structure_import_page(request: Request):
    """Page d'import de structure"""
    return templates.TemplateResponse(
        "structure_import.html",
        {"request": request}
    )
