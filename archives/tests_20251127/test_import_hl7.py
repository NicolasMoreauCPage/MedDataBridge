import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlmodel import Session
from app.db import engine
from app.services.mfn_structure import process_mfn_message

# Read the HL7 file
hl7_file_path = "tests/exemples/Structure_PR205VA1.hl7"
with open(hl7_file_path, 'r', encoding='utf-8') as f:
    hl7_message = f.read()

print("HL7 message loaded, length:", len(hl7_message))

with Session(engine) as session:
    try:
        results = process_mfn_message(hl7_message, session)
        print("Import successful!")
        print("Results:", results)
    except Exception as e:
        print("Import failed with error:", str(e))
        import traceback
        traceback.print_exc()