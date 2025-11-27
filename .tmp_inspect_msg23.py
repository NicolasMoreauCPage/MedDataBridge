from app.db import session_factory
from app.models_endpoints import MessageLog
from sqlmodel import select
s=session_factory()
ml=s.exec(select(MessageLog).where(MessageLog.id==23)).first()
print('ML record found:', bool(ml))
if ml:
    print('id=', ml.id, 'kind=', ml.kind, 'status=', ml.status)
    print('payload (repr, first 500):')
    print(repr(ml.payload)[:500])
    print('ack_payload (repr):', repr(ml.ack_payload)[:500])
    print('pam_validation_issues:', ml.pam_validation_issues)
else:
    print('No MessageLog #23')
