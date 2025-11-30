import os
from fastapi.testclient import TestClient
os.environ.setdefault('TESTING','1')
from app.app import app
client = TestClient(app)

# Generated tests - tolerant assertions (200/204/302/400/404/422)
OK_CODES = (200, 204, 302, 400, 404, 422)

def test_generated_url_0_root():
    r = client.get('/')
    assert r.status_code in OK_CODES

def test_generated_url_1_admin():
    r = client.get('/admin')
    assert r.status_code in OK_CODES

def test_generated_url_2_admin_ght():
    r = client.get('/admin/ght')
    assert r.status_code in OK_CODES

def test_generated_url_3_admin_ght_new():
    r = client.get('/admin/ght/new')
    assert r.status_code in OK_CODES

def test_generated_url_4_api_docs():
    r = client.get('/api-docs')
    assert r.status_code in OK_CODES

def test_generated_url_5_api_docs():
    r = client.get('/api/docs')
    assert r.status_code in OK_CODES

def test_generated_url_6_api_metrics_cache():
    r = client.get('/api/metrics/cache')
    assert r.status_code in OK_CODES

def test_generated_url_7_api_metrics_dashboard():
    r = client.get('/api/metrics/dashboard')
    assert r.status_code in OK_CODES

def test_generated_url_8_cache_dashboard():
    r = client.get('/cache-dashboard')
    assert r.status_code in OK_CODES

def test_generated_url_9_conformity():
    r = client.get('/conformity')
    assert r.status_code in OK_CODES

def test_generated_url_10_context_clear_kind_dossier():
    r = client.get('/context/clear?kind=dossier')
    assert r.status_code in OK_CODES

def test_generated_url_11_context_clear_kind_ej():
    r = client.get('/context/clear?kind=ej')
    assert r.status_code in OK_CODES

def test_generated_url_12_context_clear_kind_patient():
    r = client.get('/context/clear?kind=patient')
    assert r.status_code in OK_CODES

def test_generated_url_13_context_select():
    r = client.get('/context/select')
    assert r.status_code in OK_CODES

def test_generated_url_14_dashboard():
    r = client.get('/dashboard')
    assert r.status_code in OK_CODES

def test_generated_url_15_documentation():
    r = client.get('/documentation')
    assert r.status_code in OK_CODES

def test_generated_url_16_documentation_search():
    r = client.get('/documentation/search')
    assert r.status_code in OK_CODES

def test_generated_url_17_dossiers():
    r = client.get('/dossiers')
    assert r.status_code in OK_CODES

def test_generated_url_18_endpoints():
    r = client.get('/endpoints')
    assert r.status_code in OK_CODES

def test_generated_url_19_endpoints_admin():
    r = client.get('/endpoints/admin')
    assert r.status_code in OK_CODES

def test_generated_url_20_forms():
    r = client.get('/forms')
    assert r.status_code in OK_CODES

def test_generated_url_21_ght():
    r = client.get('/ght')
    assert r.status_code in OK_CODES

def test_generated_url_22_guide():
    r = client.get('/guide')
    assert r.status_code in OK_CODES

def test_generated_url_23_guide_dossiers_types():
    r = client.get('/guide#dossiers-types')
    assert r.status_code in OK_CODES

def test_generated_url_24_guide_endpoints_config():
    r = client.get('/guide#endpoints-config')
    assert r.status_code in OK_CODES

def test_generated_url_25_guide_messages_integration():
    r = client.get('/guide#messages-integration')
    assert r.status_code in OK_CODES

def test_generated_url_26_guide_patients_management():
    r = client.get('/guide#patients-management')
    assert r.status_code in OK_CODES

def test_generated_url_27_guide_scenarios_ihe():
    r = client.get('/guide#scenarios-ihe')
    assert r.status_code in OK_CODES

def test_generated_url_28_guide_standards_conformite():
    r = client.get('/guide#standards-conformite')
    assert r.status_code in OK_CODES

def test_generated_url_29_guide_structure_org():
    r = client.get('/guide#structure-org')
    assert r.status_code in OK_CODES

def test_generated_url_30_guide_validation_datatypes():
    r = client.get('/guide#validation-datatypes')
    assert r.status_code in OK_CODES

def test_generated_url_31_guide_validation_dossier_doc():
    r = client.get('/guide#validation-dossier-doc')
    assert r.status_code in OK_CODES

def test_generated_url_32_guide_validation_regles():
    r = client.get('/guide#validation-regles')
    assert r.status_code in OK_CODES

def test_generated_url_33_guide_vocabularies_tables():
    r = client.get('/guide#vocabularies-tables')
    assert r.status_code in OK_CODES

def test_generated_url_34_messages():
    r = client.get('/messages')
    assert r.status_code in OK_CODES

def test_generated_url_35_messages_by_dossier():
    r = client.get('/messages/by-dossier')
    assert r.status_code in OK_CODES

def test_generated_url_36_messages_rejections():
    r = client.get('/messages/rejections')
    assert r.status_code in OK_CODES

def test_generated_url_37_messages_status_error():
    r = client.get('/messages?status=error')
    assert r.status_code in OK_CODES

def test_generated_url_38_metrics_dashboard():
    r = client.get('/metrics/dashboard')
    assert r.status_code in OK_CODES

def test_generated_url_39_patients():
    r = client.get('/patients')
    assert r.status_code in OK_CODES

def test_generated_url_40_scenarios():
    r = client.get('/scenarios')
    assert r.status_code in OK_CODES

def test_generated_url_41_scenarios_runs():
    r = client.get('/scenarios/runs')
    assert r.status_code in OK_CODES

def test_generated_url_42_scenarios_templates():
    r = client.get('/scenarios/templates')
    assert r.status_code in OK_CODES

def test_generated_url_43_sqladmin():
    r = client.get('/sqladmin')
    assert r.status_code in OK_CODES

def test_generated_url_44_sqladmin():
    r = client.get('/sqladmin/')
    assert r.status_code in OK_CODES

def test_generated_url_45_standards():
    r = client.get('/standards')
    assert r.status_code in OK_CODES

def test_generated_url_46_standards_docs():
    r = client.get('/standards-docs')
    assert r.status_code in OK_CODES

def test_generated_url_47_structure():
    r = client.get('/structure')
    assert r.status_code in OK_CODES

def test_generated_url_48_structure___details_type____details_id__edit():
    r = client.get('/structure/${details.type}/${details.id}/edit')
    assert r.status_code in OK_CODES

def test_generated_url_49_structure___details_type____details_id__map():
    r = client.get('/structure/${details.type}/${details.id}/map')
    assert r.status_code in OK_CODES

def test_generated_url_50_structure_chambres():
    r = client.get('/structure/chambres')
    assert r.status_code in OK_CODES

def test_generated_url_51_structure_eg():
    r = client.get('/structure/eg')
    assert r.status_code in OK_CODES

def test_generated_url_52_structure_lits():
    r = client.get('/structure/lits')
    assert r.status_code in OK_CODES

def test_generated_url_53_structure_poles():
    r = client.get('/structure/poles')
    assert r.status_code in OK_CODES

def test_generated_url_54_structure_search():
    r = client.get('/structure/search')
    assert r.status_code in OK_CODES

def test_generated_url_55_structure_services():
    r = client.get('/structure/services')
    assert r.status_code in OK_CODES

def test_generated_url_56_structure_ufs():
    r = client.get('/structure/ufs')
    assert r.status_code in OK_CODES

def test_generated_url_57_structure_uh():
    r = client.get('/structure/uh')
    assert r.status_code in OK_CODES

def test_generated_url_58_structure_uh_new():
    r = client.get('/structure/uh/new')
    assert r.status_code in OK_CODES

def test_generated_url_59_transport_injection():
    r = client.get('/transport/injection')
    assert r.status_code in OK_CODES

def test_generated_url_60_transport_injection_type_PDQ():
    r = client.get('/transport/injection?type=PDQ')
    assert r.status_code in OK_CODES

def test_generated_url_61_transport_injection_type_PIX():
    r = client.get('/transport/injection?type=PIX')
    assert r.status_code in OK_CODES

def test_generated_url_62_validation():
    r = client.get('/validation')
    assert r.status_code in OK_CODES

def test_generated_url_63_venues():
    r = client.get('/venues')
    assert r.status_code in OK_CODES

def test_generated_url_64_vocabularies():
    r = client.get('/vocabularies')
    assert r.status_code in OK_CODES

def test_generated_url_65_vocabularies_new():
    r = client.get('/vocabularies/new')
    assert r.status_code in OK_CODES
