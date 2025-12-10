from __future__ import annotations

"""Utility helpers to build realistic patient identities for scenario runs."""

import random
import re
import secrets
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Dict, Optional


# Static datasets intentionally short but representative of common French data.
FAMILY_NAMES = [
    "Martin",
    "Bernard",
    "Dubois",
    "Thomas",
    "Robert",
    "Richard",
    "Petit",
    "Durand",
    "Leroy",
    "Moreau",
    "Lefebvre",
    "Michel",
    "Garcia",
    "David",
    "Fournier",
    "Roussel",
    "Renard",
    "Faure",
    "Lopez",
    "Blanc",
]

GIVEN_NAMES_FEMALE = [
    "Emma",
    "Louise",
    "Chloe",
    "Camille",
    "Ines",
    "Manon",
    "Lea",
    "Sarah",
    "Julie",
    "Sophie",
    "Anna",
    "Lena",
]

GIVEN_NAMES_MALE = [
    "Lucas",
    "Hugo",
    "Louis",
    "Gabriel",
    "Arthur",
    "Jules",
    "Leo",
    "Nathan",
    "Tom",
    "Noah",
    "Enzo",
    "Theo",
]

STREET_NAMES = [
    "Victor Hugo",
    "Jean Jaures",
    "de la Republique",
    "du General de Gaulle",
    "de la Liberte",
    "des Acacias",
    "du Faubourg",
    "des Cerisiers",
    "des Lilas",
    "des Primeveres",
]

CITY_DATA = [
    ("Paris", "Ile-de-France", "750"),
    ("Lyon", "Auvergne-Rhone-Alpes", "690"),
    ("Marseille", "Provence-Alpes-Cote d'Azur", "130"),
    ("Lille", "Hauts-de-France", "590"),
    ("Toulouse", "Occitanie", "310"),
    ("Nantes", "Pays de la Loire", "440"),
    ("Bordeaux", "Nouvelle-Aquitaine", "330"),
    ("Rennes", "Bretagne", "350"),
    ("Strasbourg", "Grand Est", "670"),
    ("Dijon", "Bourgogne-Franche-Comte", "210"),
]

COUNTRY_CODES = ["FRA", "BEL", "CHE", "LUX"]
MARITAL_STATUS_CODES = ["S", "M", "D", "W", "P", "A", "U"]
IDENTITY_RELIABILITY_CODES = [
    "VALI",
    "PROV",
    "IDVER",
    "VIDE",
    "CACH",
    "DPOT",
]


def _random_birth_date(rng: random.Random) -> date:
    """Return a birth date between 1935 and 2010."""
    start = date(1935, 1, 1)
    end = date(2010, 12, 31)
    return start + timedelta(days=rng.randint(0, (end - start).days))


def _random_maiden_name(rng: random.Random) -> str:
    return rng.choice(FAMILY_NAMES)


def _random_phone(rng: random.Random, prefix: str = "0") -> str:
    digits = [prefix]
    for _ in range(9):
        digits.append(str(rng.randint(0, 9)))
    return ''.join(digits)


def _random_nir(rng: random.Random, gender: str, birth_date: date) -> str:
    # Simplified French NIR: S YY MM BB OOO CC
    sex_digit = '1' if gender == 'M' else '2'
    year = birth_date.strftime('%y')
    month = birth_date.strftime('%m')
    insee_prefix = rng.randint(1, 95)
    commune = rng.randint(1, 990)
    order_number = rng.randint(1, 999)
    core = f"{sex_digit}{year}{month}{insee_prefix:02d}{commune:03d}{order_number:03d}"
    # Key (controle) simplified: mod 97
    check = 97 - (int(core) % 97)
    return f"{core}{check:02d}"


def _sanitize_phone(number: str) -> str:
    return re.sub(r"[^0-9]", "", number)


@dataclass
class PatientIdentity:
    prefix: str
    family: str
    given: str
    middle: Optional[str]
    suffix: Optional[str]
    birth_family: Optional[str]
    gender: str
    birth_date: date
    address: str
    city: str
    state: str
    postal_code: str
    country: str
    phone: str
    mobile: str
    work_phone: Optional[str]
    email: str
    birth_address: Optional[str]
    birth_city: str
    birth_state: str
    birth_postal_code: str
    birth_country: str
    nir: str
    marital_status: str
    nationality: str
    mothers_maiden_name: str
    identity_reliability_code: str
    primary_care_provider: str

    def as_dict(self) -> Dict[str, str]:
        data = asdict(self)
        data['birth_date'] = self.birth_date.isoformat()
        return data


def generate_patient_identity(seed: Optional[int] = None) -> PatientIdentity:
    """Generate a new patient identity with realistic-looking French data."""
    rng = random.Random(seed if seed is not None else secrets.randbits(64))

    gender = rng.choice(['M', 'F'])
    if gender == 'M':
        given = rng.choice(GIVEN_NAMES_MALE)
        prefix = 'M.'
    else:
        given = rng.choice(GIVEN_NAMES_FEMALE)
        prefix = rng.choice(['Mme', 'Mlle'])

    birth_date = _random_birth_date(rng)
    family = rng.choice(FAMILY_NAMES)
    middle = rng.choice(GIVEN_NAMES_MALE + GIVEN_NAMES_FEMALE) if rng.random() < 0.35 else None
    suffix = 'Jr' if rng.random() < 0.05 else None
    birth_family = rng.choice(FAMILY_NAMES) if rng.random() < 0.25 else None

    city, state, postal_prefix = rng.choice(CITY_DATA)
    postal_code = f"{postal_prefix}{rng.randint(0, 99):02d}"
    street_number = rng.randint(1, 180)
    address = f"{street_number} rue {rng.choice(STREET_NAMES)}"

    birth_city, birth_state, birth_postal_prefix = rng.choice(CITY_DATA)
    birth_postal_code = f"{birth_postal_prefix}{rng.randint(0, 99):02d}"
    birth_address = f"Clinique {rng.choice(FAMILY_NAMES)}"

    mobile = _random_phone(rng, '06')
    phone = _random_phone(rng, '01')
    work_phone = _random_phone(rng, '04') if rng.random() < 0.6 else None

    email = f"{given}.{family}@example.org".lower()
    nationality = rng.choice(COUNTRY_CODES)
    marital_status = rng.choice(MARITAL_STATUS_CODES)
    mothers_maiden_name = _random_maiden_name(rng)
    identity_reliability_code = rng.choice(IDENTITY_RELIABILITY_CODES)
    primary_care_provider = f"Dr {rng.choice(FAMILY_NAMES)}"
    nir = _random_nir(rng, gender, birth_date)

    return PatientIdentity(
        prefix=prefix,
        family=family,
        given=given,
        middle=middle,
        suffix=suffix,
        birth_family=birth_family,
        gender=gender,
        birth_date=birth_date,
        address=address,
        city=city,
        state=state,
        postal_code=postal_code,
        country='FRA',
        phone=phone,
        mobile=mobile,
        work_phone=work_phone,
        email=email,
        birth_address=birth_address,
        birth_city=birth_city,
        birth_state=birth_state,
        birth_postal_code=birth_postal_code,
        birth_country='FRA',
        nir=nir,
        marital_status=marital_status,
        nationality=nationality,
        mothers_maiden_name=mothers_maiden_name,
        identity_reliability_code=identity_reliability_code,
        primary_care_provider=primary_care_provider,
    )


def apply_patient_identity_to_hl7(message: str, identity: PatientIdentity) -> str:
    """Inject the generated identity into PID-related fields of an HL7 message."""
    if not message:
        return message

    preferred_sep = '\r' if '\r' in message else '\n'
    lines = message.replace('\r', '\n').split('\n')

    new_lines = []
    for line in lines:
        if line.startswith('PID|'):
            new_lines.append(_update_pid_segment(line, identity))
        else:
            new_lines.append(line)

    return preferred_sep.join(new_lines)


def _update_pid_segment(pid_segment: str, identity: PatientIdentity) -> str:
    fields = pid_segment.split('|')
    while len(fields) <= 34:
        fields.append('')

    name_components = [
        identity.family,
        identity.given,
        identity.middle or '',
        identity.suffix or '',
        identity.prefix or '',
        identity.birth_family or '',
        '',
        'L',
    ]
    fields[5] = '^'.join(name_components)
    fields[6] = identity.mothers_maiden_name or fields[6]
    fields[7] = identity.birth_date.strftime('%Y%m%d')
    fields[8] = identity.gender

    address_home = f"{identity.address}^^{identity.city}^{identity.state}^{identity.postal_code}^{identity.country}"
    address_birth = (
        f"{identity.birth_address or ''}^^{identity.birth_city}^{identity.birth_state}"
        f"^{identity.birth_postal_code}^{identity.birth_country}"
    )
    fields[11] = address_home if not identity.birth_address else f"{address_home}~{address_birth}"

    def _format_phone(number: Optional[str], usage: str) -> Optional[str]:
        if not number:
            return None
        return f"^PRN^PH^^^{_sanitize_phone(number)}^{usage}"

    phone_entries = list(filter(None, [
        _format_phone(identity.phone, 'HOME'),
        _format_phone(identity.mobile, 'MOBILE'),
    ]))
    fields[13] = '~'.join(phone_entries)
    fields[14] = _format_phone(identity.work_phone, 'WORK') or ''

    fields[16] = identity.marital_status
    fields[19] = identity.nir
    fields[23] = identity.birth_city
    fields[28] = identity.nationality
    fields[32] = identity.identity_reliability_code

    return '|'.join(fields)


def identity_to_sample_data(identity: PatientIdentity) -> Dict[str, str]:
    """Return a dict compatible with patient_form.html expected sample_data keys."""
    return {
        'prefix': identity.prefix,
        'family': identity.family,
        'given': identity.given,
        'middle': identity.middle or '',
        'suffix': identity.suffix or '',
        'birth_family': identity.birth_family or '',
        'birth_date': identity.birth_date.isoformat(),
        'gender': 'male' if identity.gender == 'M' else 'female',
        'address': identity.address,
        'city': identity.city,
        'state': identity.state,
        'postal_code': identity.postal_code,
        'country': identity.country,
        'phone': identity.phone,
        'mobile': identity.mobile,
        'work_phone': identity.work_phone or '',
        'email': identity.email,
        'birth_address': identity.birth_address or '',
        'birth_city': identity.birth_city,
        'birth_state': identity.birth_state,
        'birth_postal_code': identity.birth_postal_code,
        'birth_country': identity.birth_country,
        'nir': identity.nir,
        'marital_status': identity.marital_status,
        'nationality': identity.nationality,
        'mothers_maiden_name': identity.mothers_maiden_name,
        'identity_reliability_code': identity.identity_reliability_code,
        'primary_care_provider': identity.primary_care_provider,
    }
