from app.db import get_session
from app.routers.analytics import get_capacity_by_service, get_capacity_by_um, get_kpis

sess = next(get_session())

print('Calling get_capacity_by_service eg_id=1')
res = get_capacity_by_service(eg_id=1, session=sess)
print('Result:', res)

print('\nCalling get_capacity_by_um eg_id=1')
res2 = get_capacity_by_um(eg_id=1, session=sess)
print('Result UM:', res2)

print('\nCalling get_kpis eg_id=1')
res3 = get_kpis(eg_id=1, period='7d', session=sess)
print('KPIs:', res3)
