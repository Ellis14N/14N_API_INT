# African airport reference data.
# ICAO codes mapped to country (using exact ACLED names), city, and airport name.
# Restricted to international and major airports only.
# Used for OpenSky API queries scoped to Africa.

AFRICAN_AIRPORTS: list[dict] = [
    # Algeria
    {"icao": "DAAG", "name": "Houari Boumediene Airport", "city": "Algiers", "country": "Algeria"},
    {"icao": "DAOO", "name": "Ahmed Ben Bella Airport", "city": "Oran", "country": "Algeria"},
    {"icao": "DABC", "name": "Mohamed Boudiaf Airport", "city": "Constantine", "country": "Algeria"},
    {"icao": "DABB", "name": "Rabah Bitat Airport", "city": "Annaba", "country": "Algeria"},
    # Angola
    {"icao": "FNLU", "name": "Quatro de Fevereiro Airport", "city": "Luanda", "country": "Angola"},
    {"icao": "FNCT", "name": "Catumbela Airport", "city": "Catumbela", "country": "Angola"},
    {"icao": "FNUB", "name": "Lubango Airport", "city": "Lubango", "country": "Angola"},
    {"icao": "FNCA", "name": "Cabinda Airport", "city": "Cabinda", "country": "Angola"},
    # Benin
    {"icao": "DBBB", "name": "Cadjehoun Airport", "city": "Cotonou", "country": "Benin"},
    {"icao": "DBBP", "name": "Parakou Airport", "city": "Parakou", "country": "Benin"},
    {"icao": "DBBN", "name": "Boundetingou Airport", "city": "Natitingou", "country": "Benin"},
    {"icao": "DBBK", "name": "Kandi Airport", "city": "Kandi", "country": "Benin"},
    # Botswana
    {"icao": "FBSK", "name": "Sir Seretse Khama International Airport", "city": "Gaborone", "country": "Botswana"},
    {"icao": "FBMN", "name": "Maun Airport", "city": "Maun", "country": "Botswana"},
    {"icao": "FBKE", "name": "Kasane Airport", "city": "Kasane", "country": "Botswana"},
    {"icao": "FBPM", "name": "P.G. Matante International Airport", "city": "Francistown", "country": "Botswana"},
    # Burkina Faso
    {"icao": "DFFD", "name": "Thomas Sankara International Airport", "city": "Ouagadougou", "country": "Burkina Faso"},
    {"icao": "DFOO", "name": "Bobo-Dioulasso Airport", "city": "Bobo-Dioulasso", "country": "Burkina Faso"},
    {"icao": "DFOD", "name": "Dedougou Airport", "city": "Dedougou", "country": "Burkina Faso"},
    {"icao": "DFCC", "name": "Ouahigouya Airport", "city": "Ouahigouya", "country": "Burkina Faso"},
    # Burundi (small country — only 3 operational airports with ICAO codes)
    {"icao": "HBBA", "name": "Melchior Ndadaye International Airport", "city": "Bujumbura", "country": "Burundi"},
    {"icao": "HBBE", "name": "Gitega Airport", "city": "Gitega", "country": "Burundi"},
    {"icao": "HBBO", "name": "Kirundo Airport", "city": "Kirundo", "country": "Burundi"},
    # Cabo Verde
    {"icao": "GVAC", "name": "Amilcar Cabral International Airport", "city": "Espargos", "country": "Cabo Verde"},
    {"icao": "GVNP", "name": "Nelson Mandela International Airport", "city": "Praia", "country": "Cabo Verde"},
    {"icao": "GVSV", "name": "Cesaria Evora Airport", "city": "Sao Vicente", "country": "Cabo Verde"},
    {"icao": "GVBA", "name": "Aristides Pereira International Airport", "city": "Boa Vista", "country": "Cabo Verde"},
    # Cameroon
    {"icao": "FKKD", "name": "Douala International Airport", "city": "Douala", "country": "Cameroon"},
    {"icao": "FKYS", "name": "Yaounde Nsimalen International Airport", "city": "Yaounde", "country": "Cameroon"},
    {"icao": "FKKR", "name": "Garoua International Airport", "city": "Garoua", "country": "Cameroon"},
    {"icao": "FKKL", "name": "Maroua Salak Airport", "city": "Maroua", "country": "Cameroon"},
    # Central African Republic
    {"icao": "FEFF", "name": "Bangui M'Poko International Airport", "city": "Bangui", "country": "Central African Republic"},
    {"icao": "FEFT", "name": "Berberati Airport", "city": "Berberati", "country": "Central African Republic"},
    {"icao": "FEFM", "name": "Bambari Airport", "city": "Bambari", "country": "Central African Republic"},
    {"icao": "FEFO", "name": "Bouar Airport", "city": "Bouar", "country": "Central African Republic"},
    # Chad
    {"icao": "FTTJ", "name": "N'Djamena International Airport", "city": "N'Djamena", "country": "Chad"},
    {"icao": "FTTC", "name": "Abeche Airport", "city": "Abeche", "country": "Chad"},
    {"icao": "FTTD", "name": "Moundou Airport", "city": "Moundou", "country": "Chad"},
    {"icao": "FTTA", "name": "Sarh Airport", "city": "Sarh", "country": "Chad"},
    # Comoros (small country — only 3 operational airports)
    {"icao": "FMCH", "name": "Prince Said Ibrahim International Airport", "city": "Moroni", "country": "Comoros"},
    {"icao": "FMCV", "name": "Ouani Airport", "city": "Anjouan", "country": "Comoros"},
    {"icao": "FMCI", "name": "Bandar Es Eslam Airport", "city": "Moheli", "country": "Comoros"},
    # Democratic Republic of the Congo
    {"icao": "FZAA", "name": "N'Djili International Airport", "city": "Kinshasa", "country": "Democratic Republic of the Congo"},
    {"icao": "FZNA", "name": "Goma International Airport", "city": "Goma", "country": "Democratic Republic of the Congo"},
    {"icao": "FZQA", "name": "Lubumbashi International Airport", "city": "Lubumbashi", "country": "Democratic Republic of the Congo"},
    {"icao": "FZIC", "name": "Bangoka International Airport", "city": "Kisangani", "country": "Democratic Republic of the Congo"},
    # Djibouti
    {"icao": "HDAM", "name": "Djibouti-Ambouli International Airport", "city": "Djibouti", "country": "Djibouti"},
    {"icao": "HDAS", "name": "Ali-Sabieh Airport", "city": "Ali Sabieh", "country": "Djibouti"},
    {"icao": "HDOB", "name": "Obock Airport", "city": "Obock", "country": "Djibouti"},
    {"icao": "HDTJ", "name": "Tadjoura Airport", "city": "Tadjoura", "country": "Djibouti"},
    # Egypt
    {"icao": "HECA", "name": "Cairo International Airport", "city": "Cairo", "country": "Egypt"},
    {"icao": "HEGN", "name": "Hurghada International Airport", "city": "Hurghada", "country": "Egypt"},
    {"icao": "HESH", "name": "Sharm El Sheikh International Airport", "city": "Sharm El-Sheikh", "country": "Egypt"},
    {"icao": "HEAX", "name": "Alexandria International Airport", "city": "Alexandria", "country": "Egypt"},
    # Equatorial Guinea
    {"icao": "FGSL", "name": "Malabo International Airport", "city": "Malabo", "country": "Equatorial Guinea"},
    {"icao": "FGBT", "name": "Bata Airport", "city": "Bata", "country": "Equatorial Guinea"},
    {"icao": "FGAN", "name": "Annobon Airport", "city": "San Antonio de Pale", "country": "Equatorial Guinea"},
    {"icao": "FGCO", "name": "Corisco International Airport", "city": "Corisco Island", "country": "Equatorial Guinea"},
    # Eritrea
    {"icao": "HHAS", "name": "Asmara International Airport", "city": "Asmara", "country": "Eritrea"},
    {"icao": "HHSB", "name": "Assab International Airport", "city": "Assab", "country": "Eritrea"},
    {"icao": "HHMS", "name": "Massawa International Airport", "city": "Massawa", "country": "Eritrea"},
    {"icao": "HHTS", "name": "Teseney Airport", "city": "Teseney", "country": "Eritrea"},
    # Eswatini (small country — only 2 paved airports)
    {"icao": "FDSK", "name": "King Mswati III International Airport", "city": "Manzini", "country": "Eswatini"},
    {"icao": "FDMS", "name": "Matsapha Airport", "city": "Matsapha", "country": "Eswatini"},
    # Ethiopia
    {"icao": "HAAB", "name": "Addis Ababa Bole International Airport", "city": "Addis Ababa", "country": "Ethiopia"},
    {"icao": "HADR", "name": "Dire Dawa International Airport", "city": "Dire Dawa", "country": "Ethiopia"},
    {"icao": "HABD", "name": "Bahir Dar Airport", "city": "Bahir Dar", "country": "Ethiopia"},
    {"icao": "HAMK", "name": "Alula Aba Nega Airport", "city": "Mekelle", "country": "Ethiopia"},
    # Gabon
    {"icao": "FOOL", "name": "Leon M'Ba International Airport", "city": "Libreville", "country": "Gabon"},
    {"icao": "FOOG", "name": "Port-Gentil International Airport", "city": "Port-Gentil", "country": "Gabon"},
    {"icao": "FOON", "name": "M'Vengue El Hadj Omar Bongo Ondimba Airport", "city": "Franceville", "country": "Gabon"},
    {"icao": "FOGR", "name": "Lambarene Airport", "city": "Lambarene", "country": "Gabon"},
    # Gambia (small country — only 1 commercial airport)
    {"icao": "GBYD", "name": "Banjul International Airport", "city": "Banjul", "country": "Gambia"},
    # Ghana
    {"icao": "DGAA", "name": "Kotoka International Airport", "city": "Accra", "country": "Ghana"},
    {"icao": "DGSI", "name": "Kumasi Airport", "city": "Kumasi", "country": "Ghana"},
    {"icao": "DGLE", "name": "Tamale Airport", "city": "Tamale", "country": "Ghana"},
    {"icao": "DGTK", "name": "Takoradi Airport", "city": "Sekondi-Takoradi", "country": "Ghana"},
    # Guinea
    {"icao": "GUCY", "name": "Conakry International Airport", "city": "Conakry", "country": "Guinea"},
    {"icao": "GULB", "name": "Tata Airport", "city": "Labe", "country": "Guinea"},
    {"icao": "GUXD", "name": "Kankan Airport", "city": "Kankan", "country": "Guinea"},
    {"icao": "GUNZ", "name": "Nzerekore Airport", "city": "Nzerekore", "country": "Guinea"},
    # Guinea-Bissau
    {"icao": "GGOV", "name": "Osvaldo Vieira International Airport", "city": "Bissau", "country": "Guinea-Bissau"},
    {"icao": "GGBU", "name": "Bubaque Airport", "city": "Bubaque", "country": "Guinea-Bissau"},
    {"icao": "GGBF", "name": "Bafata Airport", "city": "Bafata", "country": "Guinea-Bissau"},
    {"icao": "GGGB", "name": "Gabu Airport", "city": "Gabu", "country": "Guinea-Bissau"},
    # Ivory Coast
    {"icao": "DIAP", "name": "Felix Houphouet-Boigny International Airport", "city": "Abidjan", "country": "Ivory Coast"},
    {"icao": "DIBK", "name": "Bouake Airport", "city": "Bouake", "country": "Ivory Coast"},
    {"icao": "DIYO", "name": "Yamoussoukro International Airport", "city": "Yamoussoukro", "country": "Ivory Coast"},
    {"icao": "DISP", "name": "San Pedro Airport", "city": "San Pedro", "country": "Ivory Coast"},
    # Kenya
    {"icao": "HKJK", "name": "Jomo Kenyatta International Airport", "city": "Nairobi", "country": "Kenya"},
    {"icao": "HKMO", "name": "Moi International Airport", "city": "Mombasa", "country": "Kenya"},
    {"icao": "HKKI", "name": "Kisumu International Airport", "city": "Kisumu", "country": "Kenya"},
    {"icao": "HKEL", "name": "Eldoret International Airport", "city": "Eldoret", "country": "Kenya"},
    # Lesotho
    {"icao": "FXMM", "name": "Moshoeshoe I International Airport", "city": "Maseru", "country": "Lesotho"},
    {"icao": "FXMK", "name": "Mokhotlong Airport", "city": "Mokhotlong", "country": "Lesotho"},
    {"icao": "FXLR", "name": "Leribe Airport", "city": "Leribe", "country": "Lesotho"},
    {"icao": "FXMF", "name": "Mafeteng Airport", "city": "Mafeteng", "country": "Lesotho"},
    # Liberia
    {"icao": "GLRB", "name": "Roberts International Airport", "city": "Harbel", "country": "Liberia"},
    {"icao": "GLMR", "name": "Spriggs Payne Airport", "city": "Monrovia", "country": "Liberia"},
    {"icao": "GLGE", "name": "Greenville/Sinoe Airport", "city": "Greenville", "country": "Liberia"},
    {"icao": "GLNA", "name": "Nimba Airport", "city": "Nimba", "country": "Liberia"},
    # Libya
    {"icao": "HLLM", "name": "Mitiga International Airport", "city": "Tripoli", "country": "Libya"},
    {"icao": "HLLB", "name": "Benina International Airport", "city": "Benghazi", "country": "Libya"},
    {"icao": "HLLS", "name": "Sabha Airport", "city": "Sabha", "country": "Libya"},
    {"icao": "HLMS", "name": "Misrata International Airport", "city": "Misrata", "country": "Libya"},
    # Madagascar
    {"icao": "FMMI", "name": "Ivato International Airport", "city": "Antananarivo", "country": "Madagascar"},
    {"icao": "FMNN", "name": "Fascene Airport", "city": "Nosy Be", "country": "Madagascar"},
    {"icao": "FMNM", "name": "Amborovy Airport", "city": "Mahajanga", "country": "Madagascar"},
    {"icao": "FMMT", "name": "Toamasina Airport", "city": "Toamasina", "country": "Madagascar"},
    # Malawi
    {"icao": "FWKI", "name": "Kamuzu International Airport", "city": "Lilongwe", "country": "Malawi"},
    {"icao": "FWCL", "name": "Chileka International Airport", "city": "Blantyre", "country": "Malawi"},
    {"icao": "FWMZ", "name": "Mzuzu Airport", "city": "Mzuzu", "country": "Malawi"},
    {"icao": "FWKA", "name": "Karonga Airport", "city": "Karonga", "country": "Malawi"},
    # Mali
    {"icao": "GABS", "name": "Modibo Keita International Airport", "city": "Bamako", "country": "Mali"},
    {"icao": "GATB", "name": "Timbuktu Airport", "city": "Timbuktu", "country": "Mali"},
    {"icao": "GAMO", "name": "Ambodedjo Airport", "city": "Mopti", "country": "Mali"},
    {"icao": "GAGO", "name": "Gao Airport", "city": "Gao", "country": "Mali"},
    # Mauritania
    {"icao": "GQNO", "name": "Nouakchott-Oumtounsy International Airport", "city": "Nouakchott", "country": "Mauritania"},
    {"icao": "GQNN", "name": "Nouadhibou International Airport", "city": "Nouadhibou", "country": "Mauritania"},
    {"icao": "GQPA", "name": "Atar International Airport", "city": "Atar", "country": "Mauritania"},
    {"icao": "GQNI", "name": "Nema Airport", "city": "Nema", "country": "Mauritania"},
    # Mauritius
    {"icao": "FIMP", "name": "Sir Seewoosagur Ramgoolam International Airport", "city": "Plaisance", "country": "Mauritius"},
    {"icao": "FIMR", "name": "Sir Gaetan Duval Airport", "city": "Rodrigues", "country": "Mauritius"},
    # Morocco
    {"icao": "GMMN", "name": "Mohammed V International Airport", "city": "Casablanca", "country": "Morocco"},
    {"icao": "GMMX", "name": "Marrakesh Menara Airport", "city": "Marrakesh", "country": "Morocco"},
    {"icao": "GMAD", "name": "Al Massira Airport", "city": "Agadir", "country": "Morocco"},
    {"icao": "GMTT", "name": "Ibn Battouta Airport", "city": "Tangier", "country": "Morocco"},
    # Mozambique
    {"icao": "FQMA", "name": "Maputo International Airport", "city": "Maputo", "country": "Mozambique"},
    {"icao": "FQBR", "name": "Beira Airport", "city": "Beira", "country": "Mozambique"},
    {"icao": "FQNP", "name": "Nampula Airport", "city": "Nampula", "country": "Mozambique"},
    {"icao": "FQTT", "name": "Chingozi Airport", "city": "Tete", "country": "Mozambique"},
    # Namibia
    {"icao": "FYWH", "name": "Hosea Kutako International Airport", "city": "Windhoek", "country": "Namibia"},
    {"icao": "FYWB", "name": "Walvis Bay Airport", "city": "Walvis Bay", "country": "Namibia"},
    {"icao": "FYOA", "name": "Andimba Toivo ya Toivo Airport", "city": "Ondangwa", "country": "Namibia"},
    {"icao": "FYRU", "name": "Rundu Airport", "city": "Rundu", "country": "Namibia"},
    # Niger
    {"icao": "DRRN", "name": "Diori Hamani International Airport", "city": "Niamey", "country": "Niger"},
    {"icao": "DRZA", "name": "Mano Dayak Airport", "city": "Agadez", "country": "Niger"},
    {"icao": "DRZR", "name": "Zinder Airport", "city": "Zinder", "country": "Niger"},
    {"icao": "DRRM", "name": "Maradi Airport", "city": "Maradi", "country": "Niger"},
    # Nigeria
    {"icao": "DNMM", "name": "Murtala Muhammed International Airport", "city": "Lagos", "country": "Nigeria"},
    {"icao": "DNAA", "name": "Nnamdi Azikiwe International Airport", "city": "Abuja", "country": "Nigeria"},
    {"icao": "DNKN", "name": "Mallam Aminu Kano International Airport", "city": "Kano", "country": "Nigeria"},
    {"icao": "DNPO", "name": "Port Harcourt International Airport", "city": "Port Harcourt", "country": "Nigeria"},
    # Republic of the Congo
    {"icao": "FCBB", "name": "Maya-Maya Airport", "city": "Brazzaville", "country": "Republic of the Congo"},
    {"icao": "FCPP", "name": "Agostinho-Neto International Airport", "city": "Pointe-Noire", "country": "Republic of the Congo"},
    {"icao": "FCOD", "name": "Dolisie Airport", "city": "Dolisie", "country": "Republic of the Congo"},
    {"icao": "FCOU", "name": "Ouesso Airport", "city": "Ouesso", "country": "Republic of the Congo"},
    # Rwanda
    {"icao": "HRYR", "name": "Kigali International Airport", "city": "Kigali", "country": "Rwanda"},
    {"icao": "HRYI", "name": "Kamembe Airport", "city": "Kamembe", "country": "Rwanda"},
    {"icao": "HRYG", "name": "Gisenyi Airport", "city": "Gisenyi", "country": "Rwanda"},
    # Sao Tome and Principe (small country — only 2 operational airports)
    {"icao": "FPST", "name": "Sao Tome International Airport", "city": "Sao Tome", "country": "Sao Tome and Principe"},
    {"icao": "FPPR", "name": "Principe Airport", "city": "Santo Antonio", "country": "Sao Tome and Principe"},
    # Senegal
    {"icao": "GOBD", "name": "Blaise Diagne International Airport", "city": "Dakar", "country": "Senegal"},
    {"icao": "GOSS", "name": "Ziguinchor Airport", "city": "Ziguinchor", "country": "Senegal"},
    {"icao": "GOSP", "name": "Saint-Louis Airport", "city": "Saint-Louis", "country": "Senegal"},
    {"icao": "GOTK", "name": "Tambacounda Airport", "city": "Tambacounda", "country": "Senegal"},
    # Seychelles
    {"icao": "FSIA", "name": "Seychelles International Airport", "city": "Mahe", "country": "Seychelles"},
    {"icao": "FSPP", "name": "Praslin Island Airport", "city": "Praslin", "country": "Seychelles"},
    {"icao": "FSDR", "name": "Desroches Airport", "city": "Desroches", "country": "Seychelles"},
    {"icao": "FSSB", "name": "Bird Island Airport", "city": "Bird Island", "country": "Seychelles"},
    # Sierra Leone
    {"icao": "GFLL", "name": "Freetown International Airport", "city": "Freetown", "country": "Sierra Leone"},
    {"icao": "GFHA", "name": "Hastings Airport", "city": "Hastings", "country": "Sierra Leone"},
    {"icao": "GFBO", "name": "Sherbro International Airport", "city": "Bonthe", "country": "Sierra Leone"},
    {"icao": "GFKN", "name": "Kenema Airport", "city": "Kenema", "country": "Sierra Leone"},
    # Somalia
    {"icao": "HCMM", "name": "Aden Adde International Airport", "city": "Mogadishu", "country": "Somalia"},
    {"icao": "HCMH", "name": "Egal International Airport", "city": "Hargeisa", "country": "Somalia"},
    {"icao": "HCMF", "name": "Bosaso Airport", "city": "Bosaso", "country": "Somalia"},
    {"icao": "HCMK", "name": "Kismayo Airport", "city": "Kismayo", "country": "Somalia"},
    # South Africa
    {"icao": "FAOR", "name": "O.R. Tambo International Airport", "city": "Johannesburg", "country": "South Africa"},
    {"icao": "FACT", "name": "Cape Town International Airport", "city": "Cape Town", "country": "South Africa"},
    {"icao": "FALE", "name": "King Shaka International Airport", "city": "Durban", "country": "South Africa"},
    {"icao": "FALA", "name": "Lanseria International Airport", "city": "Johannesburg", "country": "South Africa"},
    # South Sudan
    {"icao": "HJJJ", "name": "Juba International Airport", "city": "Juba", "country": "South Sudan"},
    {"icao": "HSSM", "name": "Malakal Airport", "city": "Malakal", "country": "South Sudan"},
    {"icao": "HSWW", "name": "Wau Airport", "city": "Wau", "country": "South Sudan"},
    {"icao": "HSMK", "name": "Rumbek Airport", "city": "Rumbek", "country": "South Sudan"},
    # Sudan
    {"icao": "HSSK", "name": "Khartoum International Airport", "city": "Khartoum", "country": "Sudan"},
    {"icao": "HSPN", "name": "Port Sudan New International Airport", "city": "Port Sudan", "country": "Sudan"},
    {"icao": "HSEL", "name": "El Fashir Airport", "city": "El Fashir", "country": "Sudan"},
    {"icao": "HSOB", "name": "El Obeid Airport", "city": "El Obeid", "country": "Sudan"},
    # Tanzania
    {"icao": "HTDA", "name": "Julius Nyerere International Airport", "city": "Dar es Salaam", "country": "Tanzania"},
    {"icao": "HTKJ", "name": "Kilimanjaro International Airport", "city": "Arusha", "country": "Tanzania"},
    {"icao": "HTZA", "name": "Abeid Amani Karume International Airport", "city": "Zanzibar", "country": "Tanzania"},
    {"icao": "HTMW", "name": "Mwanza Airport", "city": "Mwanza", "country": "Tanzania"},
    # Togo
    {"icao": "DXXX", "name": "Gnassingbe Eyadema International Airport", "city": "Lome", "country": "Togo"},
    {"icao": "DXNG", "name": "Niamtougou Airport", "city": "Niamtougou", "country": "Togo"},
    # Tunisia
    {"icao": "DTTA", "name": "Tunis-Carthage International Airport", "city": "Tunis", "country": "Tunisia"},
    {"icao": "DTTJ", "name": "Djerba-Zarzis International Airport", "city": "Djerba", "country": "Tunisia"},
    {"icao": "DTMB", "name": "Habib Bourguiba International Airport", "city": "Monastir", "country": "Tunisia"},
    {"icao": "DTTX", "name": "Enfidha-Hammamet International Airport", "city": "Enfidha", "country": "Tunisia"},
    # Uganda
    {"icao": "HUEN", "name": "Entebbe International Airport", "city": "Entebbe", "country": "Uganda"},
    {"icao": "HUGU", "name": "Gulu Airport", "city": "Gulu", "country": "Uganda"},
    {"icao": "HUSO", "name": "Soroti Airport", "city": "Soroti", "country": "Uganda"},
    {"icao": "HUKB", "name": "Kasese Airport", "city": "Kasese", "country": "Uganda"},
    # Zambia
    {"icao": "FLKK", "name": "Kenneth Kaunda International Airport", "city": "Lusaka", "country": "Zambia"},
    {"icao": "FLHN", "name": "Harry Mwanja Nkumbula International Airport", "city": "Livingstone", "country": "Zambia"},
    {"icao": "FLND", "name": "Simon Mwansa Kapwepwe International Airport", "city": "Ndola", "country": "Zambia"},
    {"icao": "FLMF", "name": "Mfuwe Airport", "city": "Mfuwe", "country": "Zambia"},
    # Zimbabwe
    {"icao": "FVRG", "name": "Robert Gabriel Mugabe International Airport", "city": "Harare", "country": "Zimbabwe"},
    {"icao": "FVBU", "name": "Joshua Mqabuko Nkomo International Airport", "city": "Bulawayo", "country": "Zimbabwe"},
    {"icao": "FVFA", "name": "Victoria Falls Airport", "city": "Victoria Falls", "country": "Zimbabwe"},
    {"icao": "FVKB", "name": "Kariba Airport", "city": "Kariba", "country": "Zimbabwe"},
]

# ---------------------------------------------------------------------------
# Major African airports by passenger traffic (top ~30)
MAJOR_AFRICAN_AIRPORTS: list[dict] = [
    {"icao": "FAOR", "name": "O.R. Tambo International Airport", "city": "Johannesburg", "country": "South Africa"},
    {"icao": "HECA", "name": "Cairo International Airport", "city": "Cairo", "country": "Egypt"},
    {"icao": "DNMM", "name": "Murtala Muhammed International Airport", "city": "Lagos", "country": "Nigeria"},
    {"icao": "HKJK", "name": "Jomo Kenyatta International Airport", "city": "Nairobi", "country": "Kenya"},
    {"icao": "HAAB", "name": "Addis Ababa Bole International Airport", "city": "Addis Ababa", "country": "Ethiopia"},
    {"icao": "FACT", "name": "Cape Town International Airport", "city": "Cape Town", "country": "South Africa"},
    {"icao": "GMMN", "name": "Mohammed V International Airport", "city": "Casablanca", "country": "Morocco"},
    {"icao": "DAAG", "name": "Houari Boumediene Airport", "city": "Algiers", "country": "Algeria"},
    {"icao": "DTTA", "name": "Tunis Carthage International Airport", "city": "Tunis", "country": "Tunisia"},
    {"icao": "FALE", "name": "King Shaka International Airport", "city": "Durban", "country": "South Africa"},
    {"icao": "DGAA", "name": "Kotoka International Airport", "city": "Accra", "country": "Ghana"},
    {"icao": "GOOY", "name": "Leopold Sedar Senghor International Airport", "city": "Dakar", "country": "Senegal"},
    {"icao": "FNLU", "name": "Quatro de Fevereiro Airport", "city": "Luanda", "country": "Angola"},
    {"icao": "HSSS", "name": "Khartoum International Airport", "city": "Khartoum", "country": "Sudan"},
    {"icao": "HTDA", "name": "Julius Nyerere International Airport", "city": "Dar es Salaam", "country": "Tanzania"},
    {"icao": "HUEN", "name": "Entebbe International Airport", "city": "Entebbe", "country": "Uganda"},
    {"icao": "FKKD", "name": "Douala International Airport", "city": "Douala", "country": "Cameroon"},
    {"icao": "DIAP", "name": "Felix Houphouet Boigny International Airport", "city": "Abidjan", "country": "Ivory Coast"},
    {"icao": "FQMA", "name": "Maputo International Airport", "city": "Maputo", "country": "Mozambique"},
    {"icao": "FVHA", "name": "Robert Gabriel Mugabe International Airport", "city": "Harare", "country": "Zimbabwe"},
    {"icao": "FZAA", "name": "N'Djili Airport", "city": "Kinshasa", "country": "Democratic Republic of the Congo"},
    {"icao": "FOOL", "name": "Léon-Mba International Airport", "city": "Libreville", "country": "Gabon"},
    {"icao": "DNPO", "name": "Port Harcourt International Airport", "city": "Port Harcourt", "country": "Nigeria"},
    {"icao": "GABS", "name": "Modibo Keita International Airport", "city": "Bamako", "country": "Mali"},
    {"icao": "DFFD", "name": "Thomas Sankara International Airport", "city": "Ouagadougou", "country": "Burkina Faso"},
    {"icao": "GUCY", "name": "Conakry International Airport", "city": "Conakry", "country": "Guinea"},
    {"icao": "GLRB", "name": "Roberts International Airport", "city": "Monrovia", "country": "Liberia"},
    {"icao": "GFLL", "name": "Lungi International Airport", "city": "Freetown", "country": "Sierra Leone"},
    {"icao": "HDAM", "name": "Djibouti-Ambouli International Airport", "city": "Djibouti", "country": "Djibouti"},
    {"icao": "FMMI", "name": "Ivato International Airport", "city": "Antananarivo", "country": "Madagascar"},
]

AIRPORT_BY_ICAO: dict[str, dict] = {a["icao"]: a for a in AFRICAN_AIRPORTS}


def get_airport(icao: str) -> dict | None:
    return AIRPORT_BY_ICAO.get(icao.upper())
