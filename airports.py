# African airport reference data.
# ICAO codes mapped to country (using exact ACLED names), city, and airport name.
# Used for OpenSky API queries scoped to Africa.

AFRICAN_AIRPORTS: list[dict] = [
    # Algeria
    {"icao": "DAAG", "name": "Houari Boumediene Airport", "city": "Algiers", "country": "Algeria"},
    {"icao": "DAOO", "name": "Ahmed Ben Bella Airport", "city": "Oran", "country": "Algeria"},
    {"icao": "DABB", "name": "Rabah Bitat Airport", "city": "Annaba", "country": "Algeria"},
    # Angola
    {"icao": "FNLU", "name": "Quatro de Fevereiro Airport", "city": "Luanda", "country": "Angola"},
    {"icao": "FNHU", "name": "Nova Lisboa Airport", "city": "Huambo", "country": "Angola"},
    # Benin
    {"icao": "DBBB", "name": "Cadjehoun Airport", "city": "Cotonou", "country": "Benin"},
    {"icao": "DBBP", "name": "Parakou Airport", "city": "Parakou", "country": "Benin"},
    # Botswana
    {"icao": "FBSK", "name": "Sir Seretse Khama International Airport", "city": "Gaborone", "country": "Botswana"},
    {"icao": "FBMN", "name": "Maun Airport", "city": "Maun", "country": "Botswana"},
    {"icao": "FBKE", "name": "Kasane Airport", "city": "Kasane", "country": "Botswana"},
    # Burkina Faso
    {"icao": "DFFD", "name": "Ouagadougou Airport", "city": "Ouagadougou", "country": "Burkina Faso"},
    # Burundi
    {"icao": "HBBA", "name": "Melchior Ndadaye International Airport", "city": "Bujumbura", "country": "Burundi"},
    # Cabo Verde
    {"icao": "GVAC", "name": "Amilcar Cabral International Airport", "city": "Sal", "country": "Cabo Verde"},
    {"icao": "GVNP", "name": "Nelson Mandela International Airport", "city": "Praia", "country": "Cabo Verde"},
    {"icao": "GVBA", "name": "Aristides Pereira International Airport", "city": "Boa Vista", "country": "Cabo Verde"},
    {"icao": "GVSV", "name": "Cesaria Evora Airport", "city": "Sao Vicente", "country": "Cabo Verde"},
    # Cameroon
    {"icao": "FKKD", "name": "Douala International Airport", "city": "Douala", "country": "Cameroon"},
    {"icao": "FKYS", "name": "Yaounde Nsimalen International Airport", "city": "Yaounde", "country": "Cameroon"},
    {"icao": "FKKR", "name": "Garoua International Airport", "city": "Garoua", "country": "Cameroon"},
    # Central African Republic
    {"icao": "FEFF", "name": "Bangui M'Poko International Airport", "city": "Bangui", "country": "Central African Republic"},
    # Chad
    {"icao": "FTTJ", "name": "N'Djamena International Airport", "city": "N'Djamena", "country": "Chad"},
    # Comoros
    {"icao": "FMCH", "name": "Prince Said Ibrahim International Airport", "city": "Moroni", "country": "Comoros"},
    {"icao": "FMCV", "name": "Ouani Airport", "city": "Anjouan", "country": "Comoros"},
    # Democratic Republic of the Congo
    {"icao": "FZAA", "name": "Kinshasa N'Djili Airport", "city": "Kinshasa", "country": "Democratic Republic of the Congo"},
    {"icao": "FZNA", "name": "Goma International Airport", "city": "Goma", "country": "Democratic Republic of the Congo"},
    {"icao": "FZQA", "name": "Lubumbashi International Airport", "city": "Lubumbashi", "country": "Democratic Republic of the Congo"},
    {"icao": "FZIC", "name": "Kisangani Bangoka Airport", "city": "Kisangani", "country": "Democratic Republic of the Congo"},
    # Djibouti
    {"icao": "HDAM", "name": "Djibouti-Ambouli International Airport", "city": "Djibouti", "country": "Djibouti"},
    # Egypt
    {"icao": "HECA", "name": "Cairo International Airport", "city": "Cairo", "country": "Egypt"},
    {"icao": "HEGN", "name": "Hurghada International Airport", "city": "Hurghada", "country": "Egypt"},
    {"icao": "HESH", "name": "Sharm El Sheikh International Airport", "city": "Sharm El-Sheikh", "country": "Egypt"},
    {"icao": "HEAX", "name": "Alexandria International Airport", "city": "Alexandria", "country": "Egypt"},
    # Equatorial Guinea
    {"icao": "FGSL", "name": "Malabo International Airport", "city": "Malabo", "country": "Equatorial Guinea"},
    {"icao": "FGBT", "name": "Bata Airport", "city": "Bata", "country": "Equatorial Guinea"},
    # Eritrea
    {"icao": "HHAS", "name": "Asmara International Airport", "city": "Asmara", "country": "Eritrea"},
    {"icao": "HHMS", "name": "Massawa International Airport", "city": "Massawa", "country": "Eritrea"},
    # Eswatini
    {"icao": "FDSK", "name": "King Mswati III International Airport", "city": "Manzini", "country": "Eswatini"},
    # Ethiopia
    {"icao": "HAAB", "name": "Addis Ababa Bole International Airport", "city": "Addis Ababa", "country": "Ethiopia"},
    {"icao": "HADR", "name": "Dire Dawa International Airport", "city": "Dire Dawa", "country": "Ethiopia"},
    {"icao": "HABD", "name": "Bahir Dar Airport", "city": "Bahir Dar", "country": "Ethiopia"},
    # Gabon
    {"icao": "FOOL", "name": "Leon M'Ba International Airport", "city": "Libreville", "country": "Gabon"},
    {"icao": "FOOG", "name": "Port-Gentil International Airport", "city": "Port-Gentil", "country": "Gabon"},
    # Gambia
    {"icao": "GBYD", "name": "Banjul International Airport", "city": "Banjul", "country": "Gambia"},
    # Ghana
    {"icao": "DGAA", "name": "Accra International Airport", "city": "Accra", "country": "Ghana"},
    {"icao": "DGSI", "name": "Kumasi Airport", "city": "Kumasi", "country": "Ghana"},
    {"icao": "DGLE", "name": "Tamale Airport", "city": "Tamale", "country": "Ghana"},
    # Guinea
    {"icao": "GUCY", "name": "Conakry International Airport", "city": "Conakry", "country": "Guinea"},
    # Guinea-Bissau
    {"icao": "GGUW", "name": "Osvaldo Vieira International Airport", "city": "Bissau", "country": "Guinea-Bissau"},
    # Ivory Coast
    {"icao": "DIAP", "name": "Felix Houphouet-Boigny International Airport", "city": "Abidjan", "country": "Ivory Coast"},
    {"icao": "DIYO", "name": "Yamoussoukro International Airport", "city": "Yamoussoukro", "country": "Ivory Coast"},
    # Kenya
    {"icao": "HKJK", "name": "Jomo Kenyatta International Airport", "city": "Nairobi", "country": "Kenya"},
    {"icao": "HKMO", "name": "Moi International Airport", "city": "Mombasa", "country": "Kenya"},
    {"icao": "HKKI", "name": "Kisumu International Airport", "city": "Kisumu", "country": "Kenya"},
    {"icao": "HKEL", "name": "Eldoret International Airport", "city": "Eldoret", "country": "Kenya"},
    # Lesotho
    {"icao": "FXMM", "name": "Moshoeshoe I International Airport", "city": "Maseru", "country": "Lesotho"},
    # Liberia
    {"icao": "GLRB", "name": "Roberts International Airport", "city": "Harbel", "country": "Liberia"},
    # Libya
    {"icao": "HLLM", "name": "Mitiga International Airport", "city": "Tripoli", "country": "Libya"},
    {"icao": "HLLB", "name": "Benina International Airport", "city": "Benghazi", "country": "Libya"},
    # Madagascar
    {"icao": "FMMI", "name": "Ivato International Airport", "city": "Antananarivo", "country": "Madagascar"},
    {"icao": "FMNN", "name": "Fascene Airport", "city": "Nosy Be", "country": "Madagascar"},
    {"icao": "FMST", "name": "Toliara Airport", "city": "Toliara", "country": "Madagascar"},
    # Malawi
    {"icao": "FWKI", "name": "Kamuzu International Airport", "city": "Lilongwe", "country": "Malawi"},
    {"icao": "FWCL", "name": "Chileka International Airport", "city": "Blantyre", "country": "Malawi"},
    # Mali
    {"icao": "GABS", "name": "Modibo Keita International Airport", "city": "Bamako", "country": "Mali"},
    {"icao": "GAGO", "name": "Gao International Airport", "city": "Gao", "country": "Mali"},
    # Mauritania
    {"icao": "GQNO", "name": "Nouakchott-Oumtounsy International Airport", "city": "Nouakchott", "country": "Mauritania"},
    # Mauritius
    {"icao": "FIMP", "name": "Sir Seewoosagur Ramgoolam International Airport", "city": "Plaisance", "country": "Mauritius"},
    # Morocco
    {"icao": "GMMN", "name": "Mohammed V International Airport", "city": "Casablanca", "country": "Morocco"},
    {"icao": "GMTT", "name": "Ibn Battouta Airport", "city": "Tangier", "country": "Morocco"},
    {"icao": "GMMX", "name": "Marrakesh Menara Airport", "city": "Marrakesh", "country": "Morocco"},
    {"icao": "GMFF", "name": "Saiss Airport", "city": "Fez", "country": "Morocco"},
    {"icao": "GMAD", "name": "Al Massira Airport", "city": "Agadir", "country": "Morocco"},
    # Mozambique
    {"icao": "FQMA", "name": "Maputo International Airport", "city": "Maputo", "country": "Mozambique"},
    {"icao": "FQBR", "name": "Beira Airport", "city": "Beira", "country": "Mozambique"},
    {"icao": "FQNP", "name": "Nampula Airport", "city": "Nampula", "country": "Mozambique"},
    {"icao": "FQPB", "name": "Pemba Airport", "city": "Pemba", "country": "Mozambique"},
    # Namibia
    {"icao": "FYWH", "name": "Windhoek Hosea Kutako International Airport", "city": "Windhoek", "country": "Namibia"},
    {"icao": "FYWB", "name": "Walvis Bay Airport", "city": "Walvis Bay", "country": "Namibia"},
    # Niger
    {"icao": "DRRN", "name": "Diori Hamani International Airport", "city": "Niamey", "country": "Niger"},
    {"icao": "DRZA", "name": "Mano Dayak International Airport", "city": "Agadez", "country": "Niger"},
    # Nigeria
    {"icao": "DNMM", "name": "Murtala Muhammed International Airport", "city": "Lagos", "country": "Nigeria"},
    {"icao": "DNAA", "name": "Nnamdi Azikiwe International Airport", "city": "Abuja", "country": "Nigeria"},
    {"icao": "DNKN", "name": "Mallam Aminu Kano International Airport", "city": "Kano", "country": "Nigeria"},
    {"icao": "DNPO", "name": "Port Harcourt International Airport", "city": "Port Harcourt", "country": "Nigeria"},
    {"icao": "DNEN", "name": "Akanu Ibiam International Airport", "city": "Enugu", "country": "Nigeria"},
    # Republic of the Congo
    {"icao": "FCBB", "name": "Maya-Maya Airport", "city": "Brazzaville", "country": "Republic of the Congo"},
    {"icao": "FCPP", "name": "Agostinho-Neto International Airport", "city": "Pointe-Noire", "country": "Republic of the Congo"},
    # Rwanda
    {"icao": "HRYR", "name": "Kigali International Airport", "city": "Kigali", "country": "Rwanda"},
    # Sao Tome and Principe
    {"icao": "FPST", "name": "Sao Tome International Airport", "city": "Sao Tome", "country": "Sao Tome and Principe"},
    # Senegal
    {"icao": "GOBD", "name": "Blaise Diagne International Airport", "city": "Dakar", "country": "Senegal"},
    {"icao": "GOOY", "name": "Leopold Sedar Senghor International Airport", "city": "Dakar", "country": "Senegal"},
    # Seychelles
    {"icao": "FSIA", "name": "Seychelles International Airport", "city": "Mahe", "country": "Seychelles"},
    # Sierra Leone
    {"icao": "GFLL", "name": "Freetown International Airport", "city": "Freetown", "country": "Sierra Leone"},
    # Somalia
    {"icao": "HCMM", "name": "Aden Adde International Airport", "city": "Mogadishu", "country": "Somalia"},
    {"icao": "HCGR", "name": "Egal International Airport", "city": "Hargeisa", "country": "Somalia"},
    # South Africa
    {"icao": "FAOR", "name": "O.R. Tambo International Airport", "city": "Johannesburg", "country": "South Africa"},
    {"icao": "FACT", "name": "Cape Town International Airport", "city": "Cape Town", "country": "South Africa"},
    {"icao": "FALE", "name": "King Shaka International Airport", "city": "Durban", "country": "South Africa"},
    {"icao": "FABL", "name": "Bram Fischer International Airport", "city": "Bloemfontein", "country": "South Africa"},
    {"icao": "FALA", "name": "Lanseria International Airport", "city": "Johannesburg", "country": "South Africa"},
    # South Sudan
    {"icao": "HJJJ", "name": "Juba International Airport", "city": "Juba", "country": "South Sudan"},
    {"icao": "HSSM", "name": "Malakal Airport", "city": "Malakal", "country": "South Sudan"},
    # Sudan
    {"icao": "HSSK", "name": "Khartoum International Airport", "city": "Khartoum", "country": "Sudan"},
    {"icao": "HSPN", "name": "Port Sudan New International Airport", "city": "Port Sudan", "country": "Sudan"},
    # Tanzania
    {"icao": "HTDA", "name": "Julius Nyerere International Airport", "city": "Dar es Salaam", "country": "Tanzania"},
    {"icao": "HTKJ", "name": "Kilimanjaro International Airport", "city": "Arusha", "country": "Tanzania"},
    {"icao": "HTZA", "name": "Abeid Amani Karume International Airport", "city": "Zanzibar", "country": "Tanzania"},
    # Togo
    {"icao": "DXXX", "name": "Lome-Tokoin International Airport", "city": "Lome", "country": "Togo"},
    # Tunisia
    {"icao": "DTTA", "name": "Tunis-Carthage International Airport", "city": "Tunis", "country": "Tunisia"},
    {"icao": "DTTJ", "name": "Djerba-Zarzis International Airport", "city": "Djerba", "country": "Tunisia"},
    {"icao": "DTMB", "name": "Monastir Habib Bourguiba International Airport", "city": "Monastir", "country": "Tunisia"},
    # Uganda
    {"icao": "HUEN", "name": "Entebbe International Airport", "city": "Entebbe", "country": "Uganda"},
    # Zambia
    {"icao": "FLKK", "name": "Kenneth Kaunda International Airport", "city": "Lusaka", "country": "Zambia"},
    {"icao": "FLSK", "name": "Simon Mwansa Kapwepwe International Airport", "city": "Ndola", "country": "Zambia"},
    {"icao": "FLHN", "name": "Harry Mwanja Nkumbula International Airport", "city": "Livingstone", "country": "Zambia"},
    # Zimbabwe
    {"icao": "FVRG", "name": "Robert Gabriel Mugabe International Airport", "city": "Harare", "country": "Zimbabwe"},
    {"icao": "FVBU", "name": "Joshua Mqabuko Nkomo International Airport", "city": "Bulawayo", "country": "Zimbabwe"},
    {"icao": "FVFA", "name": "Victoria Falls Airport", "city": "Victoria Falls", "country": "Zimbabwe"},
]

# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

# ICAO code → airport dict
AIRPORT_BY_ICAO: dict[str, dict] = {a["icao"]: a for a in AFRICAN_AIRPORTS}

# Country → list of airport dicts
AIRPORTS_BY_COUNTRY: dict[str, list[dict]] = {}
for _a in AFRICAN_AIRPORTS:
    AIRPORTS_BY_COUNTRY.setdefault(_a["country"], []).append(_a)


def get_airports_for_country(country: str) -> list[dict]:
    """Return all airports for a given country (exact ACLED name)."""
    return AIRPORTS_BY_COUNTRY.get(country, [])


def get_airport(icao: str) -> dict | None:
    """Return airport details for a given ICAO code."""
    return AIRPORT_BY_ICAO.get(icao.upper())
