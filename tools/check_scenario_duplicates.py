import importlib.util

def load_scenarios(path):
    spec = importlib.util.spec_from_file_location('scenarios', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.scenarios

ihe = load_scenarios('data/scenarios_ihe_pam_seed.py')
hl7 = load_scenarios('data/scenarios_hl7_seed.py')

ihe_keys = set(s['key'] for s in ihe)
hl7_keys = set(s['key'] for s in hl7)
dups = ihe_keys & hl7_keys

if dups:
    print('DUPLICATE KEYS:')
    for key in sorted(dups):
        print(key)
else:
    print('NO DUPLICATE KEYS')
