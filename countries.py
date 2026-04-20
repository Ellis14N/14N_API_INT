# African country reference data.
# ACLED_NAME is the exact string the ACLED API accepts.
# ALTERNATES covers common alternate spellings, abbreviations, and historical names
# that a user might type when prompting Claude.

AFRICAN_COUNTRIES: list[dict] = [
    {
        "acled_name": "Algeria",
        "iso2": "DZ",
        "iso3": "DZA",
        "alternates": ["algerie", "algérie", "arab republic of algeria"],
    },
    {
        "acled_name": "Angola",
        "iso2": "AO",
        "iso3": "AGO",
        "alternates": ["republic of angola"],
    },
    {
        "acled_name": "Benin",
        "iso2": "BJ",
        "iso3": "BEN",
        "alternates": ["republic of benin", "dahomey"],
    },
    {
        "acled_name": "Botswana",
        "iso2": "BW",
        "iso3": "BWA",
        "alternates": ["republic of botswana", "bechuanaland"],
    },
    {
        "acled_name": "Burkina Faso",
        "iso2": "BF",
        "iso3": "BFA",
        "alternates": ["burkina", "upper volta"],
    },
    {
        "acled_name": "Burundi",
        "iso2": "BI",
        "iso3": "BDI",
        "alternates": ["republic of burundi"],
    },
    {
        "acled_name": "Cabo Verde",
        "iso2": "CV",
        "iso3": "CPV",
        "alternates": ["cape verde", "republic of cabo verde", "republic of cape verde"],
    },
    {
        "acled_name": "Cameroon",
        "iso2": "CM",
        "iso3": "CMR",
        "alternates": ["cameroun", "republic of cameroon"],
    },
    {
        "acled_name": "Central African Republic",
        "iso2": "CF",
        "iso3": "CAF",
        "alternates": ["car", "central africa", "rca", "republique centrafricaine"],
    },
    {
        "acled_name": "Chad",
        "iso2": "TD",
        "iso3": "TCD",
        "alternates": ["republic of chad", "tchad"],
    },
    {
        "acled_name": "Comoros",
        "iso2": "KM",
        "iso3": "COM",
        "alternates": ["comoro islands", "union of the comoros", "comores"],
    },
    {
        "acled_name": "Democratic Republic of the Congo",
        "iso2": "CD",
        "iso3": "COD",
        "alternates": [
            "drc", "dr congo", "congo-kinshasa", "congo kinshasa",
            "democratic republic of congo", "congo (democratic)",
            "congo (drc)", "zaire", "rd congo",
        ],
    },
    {
        "acled_name": "Djibouti",
        "iso2": "DJ",
        "iso3": "DJI",
        "alternates": ["republic of djibouti", "french somaliland", "territoire français des afars et des issas"],
    },
    {
        "acled_name": "Egypt",
        "iso2": "EG",
        "iso3": "EGY",
        "alternates": ["arab republic of egypt", "egypt arab republic"],
    },
    {
        "acled_name": "Equatorial Guinea",
        "iso2": "GQ",
        "iso3": "GNQ",
        "alternates": ["guinea ecuatorial", "republic of equatorial guinea", "eq guinea", "eq. guinea"],
    },
    {
        "acled_name": "Eritrea",
        "iso2": "ER",
        "iso3": "ERI",
        "alternates": ["state of eritrea"],
    },
    {
        "acled_name": "Eswatini",
        "iso2": "SZ",
        "iso3": "SWZ",
        "alternates": ["swaziland", "kingdom of eswatini", "kingdom of swaziland"],
    },
    {
        "acled_name": "Ethiopia",
        "iso2": "ET",
        "iso3": "ETH",
        "alternates": ["abyssinia", "federal democratic republic of ethiopia"],
    },
    {
        "acled_name": "Gabon",
        "iso2": "GA",
        "iso3": "GAB",
        "alternates": ["gabonese republic", "republique gabonaise"],
    },
    {
        "acled_name": "Gambia",
        "iso2": "GM",
        "iso3": "GMB",
        "alternates": ["the gambia", "republic of the gambia"],
    },
    {
        "acled_name": "Ghana",
        "iso2": "GH",
        "iso3": "GHA",
        "alternates": ["republic of ghana", "gold coast"],
    },
    {
        "acled_name": "Guinea",
        "iso2": "GN",
        "iso3": "GIN",
        "alternates": ["republic of guinea", "guinea (republic)", "guinea-conakry", "guinea conakry"],
    },
    {
        "acled_name": "Guinea-Bissau",
        "iso2": "GW",
        "iso3": "GNB",
        "alternates": ["guinea bissau", "portuguese guinea", "republic of guinea-bissau"],
    },
    {
        "acled_name": "Ivory Coast",
        "iso2": "CI",
        "iso3": "CIV",
        "alternates": ["cote d'ivoire", "côte d'ivoire", "cote divoire", "republic of cote d'ivoire"],
    },
    {
        "acled_name": "Kenya",
        "iso2": "KE",
        "iso3": "KEN",
        "alternates": ["republic of kenya"],
    },
    {
        "acled_name": "Lesotho",
        "iso2": "LS",
        "iso3": "LSO",
        "alternates": ["kingdom of lesotho", "basutoland"],
    },
    {
        "acled_name": "Liberia",
        "iso2": "LR",
        "iso3": "LBR",
        "alternates": ["republic of liberia"],
    },
    {
        "acled_name": "Libya",
        "iso2": "LY",
        "iso3": "LBY",
        "alternates": ["libyan arab jamahiriya", "state of libya", "great socialist people's libyan arab jamahiriya"],
    },
    {
        "acled_name": "Madagascar",
        "iso2": "MG",
        "iso3": "MDG",
        "alternates": ["republic of madagascar", "malagasy republic"],
    },
    {
        "acled_name": "Malawi",
        "iso2": "MW",
        "iso3": "MWI",
        "alternates": ["republic of malawi", "nyasaland"],
    },
    {
        "acled_name": "Mali",
        "iso2": "ML",
        "iso3": "MLI",
        "alternates": ["republic of mali", "french sudan"],
    },
    {
        "acled_name": "Mauritania",
        "iso2": "MR",
        "iso3": "MRT",
        "alternates": ["islamic republic of mauritania", "mauritanie"],
    },
    {
        "acled_name": "Mauritius",
        "iso2": "MU",
        "iso3": "MUS",
        "alternates": ["republic of mauritius", "ile maurice", "île maurice"],
    },
    {
        "acled_name": "Morocco",
        "iso2": "MA",
        "iso3": "MAR",
        "alternates": ["kingdom of morocco", "maroc", "al-maghrib"],
    },
    {
        "acled_name": "Mozambique",
        "iso2": "MZ",
        "iso3": "MOZ",
        "alternates": ["republic of mozambique", "mocambique", "moçambique"],
    },
    {
        "acled_name": "Namibia",
        "iso2": "NA",
        "iso3": "NAM",
        "alternates": ["republic of namibia", "south-west africa", "southwest africa"],
    },
    {
        "acled_name": "Niger",
        "iso2": "NE",
        "iso3": "NER",
        "alternates": ["republic of niger"],
    },
    {
        "acled_name": "Nigeria",
        "iso2": "NG",
        "iso3": "NGA",
        "alternates": ["federal republic of nigeria"],
    },
    {
        "acled_name": "Republic of the Congo",
        "iso2": "CG",
        "iso3": "COG",
        "alternates": [
            "congo", "congo-brazzaville", "congo brazzaville",
            "congo (republic)", "congo (brazzaville)", "republic of congo",
        ],
    },
    {
        "acled_name": "Rwanda",
        "iso2": "RW",
        "iso3": "RWA",
        "alternates": ["republic of rwanda"],
    },
    {
        "acled_name": "Sao Tome and Principe",
        "iso2": "ST",
        "iso3": "STP",
        "alternates": ["são tomé and príncipe", "sao tome & principe", "democratic republic of sao tome and principe"],
    },
    {
        "acled_name": "Senegal",
        "iso2": "SN",
        "iso3": "SEN",
        "alternates": ["republic of senegal"],
    },
    {
        "acled_name": "Seychelles",
        "iso2": "SC",
        "iso3": "SYC",
        "alternates": ["republic of seychelles"],
    },
    {
        "acled_name": "Sierra Leone",
        "iso2": "SL",
        "iso3": "SLE",
        "alternates": ["republic of sierra leone"],
    },
    {
        "acled_name": "Somalia",
        "iso2": "SO",
        "iso3": "SOM",
        "alternates": ["federal republic of somalia", "somali democratic republic"],
    },
    {
        "acled_name": "South Africa",
        "iso2": "ZA",
        "iso3": "ZAF",
        "alternates": ["republic of south africa", "rsa", "south african republic"],
    },
    {
        "acled_name": "South Sudan",
        "iso2": "SS",
        "iso3": "SSD",
        "alternates": ["republic of south sudan", "s. sudan", "s sudan"],
    },
    {
        "acled_name": "Sudan",
        "iso2": "SD",
        "iso3": "SDN",
        "alternates": ["republic of the sudan", "north sudan"],
    },
    {
        "acled_name": "Tanzania",
        "iso2": "TZ",
        "iso3": "TZA",
        "alternates": ["united republic of tanzania", "tanganyika", "zanzibar"],
    },
    {
        "acled_name": "Togo",
        "iso2": "TG",
        "iso3": "TGO",
        "alternates": ["togolese republic", "togoland"],
    },
    {
        "acled_name": "Tunisia",
        "iso2": "TN",
        "iso3": "TUN",
        "alternates": ["republic of tunisia", "tunisie"],
    },
    {
        "acled_name": "Uganda",
        "iso2": "UG",
        "iso3": "UGA",
        "alternates": ["republic of uganda"],
    },
    {
        "acled_name": "Zambia",
        "iso2": "ZM",
        "iso3": "ZMB",
        "alternates": ["republic of zambia", "northern rhodesia"],
    },
    {
        "acled_name": "Zimbabwe",
        "iso2": "ZW",
        "iso3": "ZWE",
        "alternates": ["republic of zimbabwe", "rhodesia", "southern rhodesia"],
    },
]

# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

# Build a flat lookup: any name/alias (lowercased) → ACLED canonical name
_LOOKUP: dict[str, str] = {}
for _c in AFRICAN_COUNTRIES:
    _LOOKUP[_c["acled_name"].lower()] = _c["acled_name"]
    _LOOKUP[_c["iso2"].lower()] = _c["acled_name"]
    _LOOKUP[_c["iso3"].lower()] = _c["acled_name"]
    for _alt in _c["alternates"]:
        _LOOKUP[_alt.lower()] = _c["acled_name"]

# Ordered list of canonical ACLED names for bulk queries
ACLED_NAMES: list[str] = [c["acled_name"] for c in AFRICAN_COUNTRIES]

# Independent canonical list of African country names for non-ACLED uses
# (e.g., travel advisory fetchers and caches). This is intentionally named
# to avoid implying any dependency on the ACLED dataset.
AFRICAN_CANONICAL_NAMES: list[str] = [c["acled_name"] for c in AFRICAN_COUNTRIES]


def resolve_country(name: str) -> str | None:
    """Return the canonical ACLED country name for any input string, or None if not found."""
    return _LOOKUP.get(name.strip().lower())
