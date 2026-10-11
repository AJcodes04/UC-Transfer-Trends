import re

_SUB_MAJOR_RE = re.compile(r'^(.+?)(\s*[-/(:]|\s+with\s|\s+w/)', re.IGNORECASE)
MAJOR_ALIASES = {
    'Communication': ['Communication Studies', 'Communication Arts'],
    'African American Studies': ['African-American Studies'],
    'Astrophysics' : ['Astronomy and Astrophysics'],
    'Asian Studies': [
        'Pre-Asian Studies',
    ],
    'Applied Mathematics' : [
        'Pre-Applied Mathematics',
        'Applied and Computational Mathematics',
    ],
    'Business Economics': [
        'Pre-Business Economics',
        'Business Management - Economics',
        'Management and Business Economics',
    ],
    'Biology': [
        'Biological Sciences',
    ],
    'Biochemistry' : [
        'Chemistry - Biochemistry',
        'Biochemistry- Molecular Biology'

    ],
    'Cognitive Science': ['Cognitive Sciences'],
    'Chicano Studies': [
        'Chicana & Chicano Studies',
        'Chicana/0 Studies',
        'Chicano/Latino Studies',
        'Chicanx Latinx Studies',
        'Chicana Studies',
    ],
    'Aerospace Engineering': ['Aerospace Science and Engineering'],
    'Electrical Engineering': ['Electrical Engineering - BS', 'Engineering - Electrical'],
    'Environmental Science':[
        'Environmental Studies',
    ],
    'Civil Engineering': ['Engineering - Civil'],
    'Mechanical Engineering': ['Engineering - Mechanical'],
    'Molecular & Cell Biology': [
        'Molecular, Cell, & Developmental Biology',
        'Cell, Molecular, & Developmental Biology',
        'Molecular & Cell Biology - Pl1 - 1',
        'Molecular & Cell Biology - Pl1 - 2',
        'Molecular & Cell Biology - Pl1 - 3',
        'Molecular & Cell Biology - Pl2 - 2',
        'Molecular & Cell Biology - Pl2 - 3',
    ],
    'Architecture': [
        'Architectural Studies',
    ],
    'Chemistry':[
        'Chemical Sciences',
    ],
    'Dance': [
        'Dance & Performance Studies',
    ],
    'Film': [
        'Film & Television',
        'Film and Digital Media',
        'Film and Media Studies',
        'Film Studies',
    ],
    "Global Studies" : [
        "Pre-Global Studies",
    ],
    'Human Development' : [
        'Human Developmental Sciences',
        'Pre-Human Development',
    ],
    'History' : [
        'Pre-History',
    ],
    'Art': [
        'Art - Studio',
    ],
    'Economics' : [
        'Pre-Economics',
        'Bachelor of Science in Economics'
    ],
    'Linguistics':[
        'Applied Linguistics',
        'Applied Linguistics and Multilingualism',
    ],
    'Statistics': [
        'Pre-Statistics'
    ],
    'Political Science':[
        'Pre-Political Science',
    ],
    'Materials Science & Engineering':[
        'Materials Engineering',
        'Materials Science',
    ],
    'Marine Science' : [
        'Marine and Coastal Science',
    ],
    'Mathematics' :[
        'Pre-Mathematics'
    ],
    "Psychology" : [
        "Pre-Psychology",
    ],
    "Sociology" : [
        "Pre-Sociology",
    ],
}

# MAJOR_ALIASES is keyed canonical -> aliases, which is the wrong direction for the
# per-row lookup "what is this name's canonical form?". Invert it once at import so
# that lookup is a single hash hit instead of a scan over every canonical + alias.
ALIAS_TO_CANONICAL = {
    alias: canonical
    for canonical, aliases in MAJOR_ALIASES.items()
    for alias in aliases
}

MAJOR_ABSORPTIONS = {
    'Asian American Studies': [
        'Asian American and Asian Diaspora Studies',
    ],
    'Animal Sciences':[
        'Animal Science & Management',
        'Animal Biology',
    ],
    'Anthropology': [
        'Biological Anthropology',
    ],
    'Mathematics': [
        'Pre-Mathematics - Computer Science',
        'Pre-Mathematics for Teaching',
        'Pre-Mathematics of Computation',
        'Pre-Mathematics/Applied Science',
        'Pre-Mathematics/Economics',
        'Mathematics - Applied Science',
        'Mathematics & Science Computation',
        'Mathematics for Secondary School',
        'Mathematics Theory & Computation',
        'Mathematical Analytics and Operations Research',
        'Mathematical Sciences',
        'Applied Mathematics',
        'Mathematics Education'
    ],
    'Chemistry': [
        'Chemical Biology',
        'Biochemistry',
        'Pharmaceutical Chemistry',
        'Pharmacological Chemistry',
        'Applied Chemistry',
        'Chemical Physics',
        'Molecular Synthesis',
    ],
    'Engineering': [
        'Chemical Engineering and Materials Science and Engineering',
        'Chemical Engineering and Nuclear Engineering',
        'Mechanical Engineering and Nuclear Engineering',
        'Materials Science and Engineering and Mechanical Engineering',
        'Electrical Engineering & Computer Sciences & Materials Science and Engineering',
        'Electrical Engineering and Computer Sciences and Nuclear Engineering',
        'Energy Engineering',
        'Engineering Mathematics - Mathematics Science',
    ],
    'Biology': [
        'Molecular & Cell Biology',
        'Cell Biology',
        'Microbial Biology',
        'Molecular Environmental Biology',
        'Molecular Toxicology',
        'Integrative Biology',
        'Evolution, Ecology & Biodiversity',
        'Biochemistry & Cell Biology',
        'Genetics & Plant Biology',
        'Genetics and Genomics',
        'Global Disease Biology',
        'Human Biology',
        'Microbiology',
        'Molecular & Medical Microbiology',
        'Molecular Biology',
        'Plant Biology',
        'Pre Human Biology and Society',
        'Pre-Computational & Systems Biology',
        'Pre-Microbiology - Immunology - Molecular Genetics',
        'Pre-Psychobiology',
    ],
    'Political Science': [
        'Political Economy',
        'Public Policy',
        'History of Public Policy',
        'History of Public Policy and Law',
    ],
    'Psychology': [
        'Biopsychology',
        'Psychological Science',
        'Psychological and Brain Science',
        'Psychology and Law & Society',
        'Psychology & Social Behavior',
    ],
    'Asian Studies': [
        'Asian Studies Area I',
        'Asian Studies Area II',
        'East Asian Studies',
        'East Asian Cultures',
        'East Asian Religion, Thought, and Culture',
        'Asian Humanities',
        'Asian Languages and Linguistics',
    ],
    'Chinese': [
        'Chinese Language & Literature',
        'Chinese Studies',
    ],
    'Data Science': [
        'Pre-Data Theory',
        'Pre-Statistics and Data Science'
    ],
    'Environmental Science':[
        'Environmental Science and Management',
        'Environmental Science and Policy',
        'Environmental Earth Science',
        'Environmental Studies/Economics',
    ],
    'Japanese': [
        'Japanese Language & Literature',
        'Japanese Studies',
    ],
    'Gender & Women\'s Studies': [
        'Gender Studies',
        'Gender and Sexuality Studies',
        'Gender, Sexuality, and Women\'s Studies',
        'Feminist Studies',
    ],
    'Theater': [
        'Theater and Performance Studies',
        'Theater Arts',
        'Theatre and Dance',
        'Theatre, Film and Digital Production',
    ],
    'Ecology, Behavior & Evolution': [
        'Ecology & Evolution',
        'Ecology & Evolutionary Biology',
    ],
    'Geology': [
        'Geosciences',
        'Geophysics',
        'Earth Science',
        'Engineering Geology',
    ],
    'Music': [
        'Music Composition',
        'Music History and Industry',
        'Music Industry',
        'Music Performance',
        'Musicology',
        'Ethnomusicology',
        'Music & Culture',
    ],
    'Public Health': [
        'Public Health Policy',
        'Public Health Sciences',
        'Pre-Public Health',
        'Bachelor of Science in Public Health W/ Concentration in Community Hlth Sci',
        'Bachelor of Science in Public Health W/ Concentration in Hlth Policy and Mgmt Sc',
        'Bachelor of Science in Public Health W/ Concentration in Medicine Science',
        'Bachelor of Science in Public Health W/Con in Epidemiology',
    ],
    'Robotics': [
        'Robotics Engineering BS',
    ],
    'Urban Studies': [
        'Urban Studies & Planning',
    ],
    'Computer Science': [
        'Computer Science with Business Applications',
        'Software Engineering',
        'Linguistics & Computer Science',
        'Computer Game Science',
    ],
    'Cognitive Science': [
        'Pre-Cognitive Science',
    ],
    'Economics': [
        'Environmental Economics & Policy',
        'Global Economics',
        'Managerial Economics',
        'Quantitative Economics',
        'Economics and Accounting',
    ],
    'Physics': [
        'Applied Physics',
    ],
}
