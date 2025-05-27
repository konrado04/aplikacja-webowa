from flask import Flask, render_template, request, redirect, url_for, make_response, flash, jsonify
import json
import os
import re
import csv
from io import StringIO
import pandas as pd
from operator import itemgetter
from collections import Counter
import logging
from datetime import datetime
import chardet

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Ustawienie kodowania UTF-8
app.config['JSON_AS_ASCII'] = False
app.config['DEFAULT_CHARSET'] = ['utf-8']

# Konfiguracja logowania
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Ścieżka do pliku JSON
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "data", "projects_db.json")

# Hierarchiczna lista kategorii i cech
categories = {
    "Pneumatyka": {
        "Średnica Tłoka": {
            "hint": "Format: 'D XXX mm [E]', 'D XXX mm [H]' lub 'D XXX mm [J]' (np. 'D 032 mm [E]')",
            "pattern": r"^D \d{3} mm \[[EHJ]\]$"
        },
        "Skok Siłownika": {
            "hint": "Format: 'XXXX mm' (np. '0020 mm', 4 cyfry)",
            "pattern": r"^\d{4} mm$"
        },
        "Ilość Tłoków": {
            "hint": "Wybierz: 'Jeden' lub 'Dwa'",
            "allowed_values": ["Jeden", "Dwa"]
        },
        "Ilość Tłoczysk": {
            "hint": "Wybierz: 'Jedno' lub 'Dwa (Dwustronne Tłoczysko)'",
            "allowed_values": ["Jedno", "Dwa (Dwustronne Tłoczysko)"]
        },
        "Gwint Przyłączy": {
            "hint": "Wybierz: 'M5', 'G1/8', 'G3/8'",
            "allowed_values": ["M5", "G1/8", "G3/8"]
        },
        "Tłok Magnetyczny": {
            "hint": "Wybierz: 'TAK' lub 'NIE'",
            "allowed_values": ["TAK", "NIE"]
        },
        "Ilość Przyłączy": {
            "hint": "Wybierz: 'Jeden' lub 'Dwa'",
            "allowed_values": ["Jeden", "Dwa"]
        },
        "Średnica Tłoczyska": {
            "hint": "Format: 'XX mm' (np. '12 mm')",
            "pattern": r"^\d{1,2} mm$"
        }
    },
    "Mechanika": {
        "Zabezpieczenie Przed Obrotem": {
            "hint": "Wybierz: 'TAK' lub 'NIE'",
            "allowed_values": ["TAK", "NIE"]
        },
        "Regulacja Kąta Obrotu": {
            "hint": "Wybierz: 'TAK' lub 'NIE'",
            "allowed_values": ["TAK", "NIE"]
        },
        "Kąt Obrotu": {
            "hint": "Format: 'XX°' (np. '90°') lub 'Brak'",
            "pattern": r"^\d+°|Brak$"
        },
        "Amortyzacja Pneumatyczna": {
            "hint": "Wybierz: 'Z Amortyzacją Pneumatyczną' lub 'Bez Amortyzacji Pneumatycznej'",
            "allowed_values": ["Z Amortyzacją Pneumatyczną", "Bez Amortyzacji Pneumatycznej"]
        },
        "Gwint Tłoczyska": {
            "hint": "Wybierz: 'M10', 'M6', 'M16x1,5', 'M20x1,5'",
            "allowed_values": ["M10", "M6", "M16x1,5", "M20x1,5"]
        },
        "Rodzaj Gwintu Tłoczyska": {
            "hint": "Wybierz: 'Zewnętrzny' lub 'Wewnętrzny'",
            "allowed_values": ["Zewnętrzny", "Wewnętrzny"]
        }
    },
    "Materiały": {
        "Materiał Tłoczyska": {
            "hint": "Wybierz: 'Stal Węglowa Chromowana' lub 'Stal Kwasoodporna'",
            "allowed_values": ["Stal Węglowa Chromowana", "Stal Kwasoodporna"]
        },
        "Materiał Tulei": {
            "hint": "Wybierz: 'Stop Aluminium' lub 'Stal Kwasoodporna'",
            "allowed_values": ["Stop Aluminium", "Stal Kwasoodporna"]
        },
        "Materiał Pokryw": {
            "hint": "Wybierz: 'Stop Aluminium' lub 'Stal Kwasoodporna'",
            "allowed_values": ["Stop Aluminium", "Stal Kwasoodporna"]
        },
        "Materiał Uszczelnień": {
            "hint": "Wybierz: 'PU (Poliuretan)' lub 'VITON'",
            "allowed_values": ["PU (Poliuretan)", "VITON"]
        },
        "Rodzaj Tulei": {
            "hint": "Wybierz: 'Tuleja Okrągła', 'Tuleja Profilowa z Kanałkiem Trapezowym' lub 'Tuleja Kształtowa'",
            "allowed_values": ["Tuleja Okrągła", "Tuleja Profilowa z Kanałkiem Trapezowym", "Tuleja Kształtowa"]
        }
    },
    "Dodatki": {
        "Dodatkowy Zgarniacz": {
            "hint": "Wybierz: 'TAK' lub 'NIE'",
            "allowed_values": ["TAK", "NIE"]
        },
        "Zamontowany Osprzęt": {
            "hint": "Wybierz: 'Brak'",
            "allowed_values": ["Brak"]
        },
        "Wykonanie Specjalne": {
            "hint": "Wybierz: 'TAK' lub 'NIE'",
            "allowed_values": ["TAK", "NIE"]
        },
        "ATEX": {
            "hint": "Wybierz: 'TAK' lub 'NIE'",
            "allowed_values": ["TAK", "NIE"]
        }
    },
    "Inne": {
        "Seria": {
            "hint": "Wybierz: 'SCN', 'SDK', 'SSI', 'STK'",
            "allowed_values": ["SCN", "SDK", "SSI", "STK"]
        },
        "Funkcja": {
            "hint": "Wybierz: 'Dwustronnego Działania'",
            "allowed_values": ["Dwustronnego Działania"]
        }
    }
}

def normalize_form_data(form_data):
    """Normalizuje dane z formularza."""
    normalization_rules = {
        'Dodatkowy Zgarniacz': {'nie': 'NIE', 'tak': 'TAK', 'no': 'NIE', 'yes': 'TAK'},
        'Regulacja Kąta Obrotu': {'nie': 'NIE', 'tak': 'TAK', 'no': 'NIE', 'yes': 'TAK'},
        'Ilość Tłoków': {'jeden': 'Jeden', 'dwa': 'Dwa'},
        'Ilość Tłoczysk': {'jedno': 'Jedno', 'dwa': 'Dwa (Dwustronne Tłoczysko)'},
        'Zabezpieczenie Przed Obrotem': {'nie': 'NIE', 'tak': 'TAK', 'no': 'NIE', 'yes': 'TAK'},
        'Kąt Obrotu': {'brak': 'Brak'},
        'Materiał Tłoczyska': {'stal węglowa chromowana': 'Stal Węglowa Chromowana', 'stal kwasoodporna': 'Stal Kwasoodporna'},
        'Materiał Tulei': {'stop aluminium': 'Stop Aluminium', 'stal kwasoodporna': 'Stal Kwasoodporna'},
        'Materiał Pokryw': {'stop aluminium': 'Stop Aluminium', 'stal kwasoodporna': 'Stal Kwasoodporna'},
        'Amortyzacja Pneumatyczna': {'tak': 'Z Amortyzacją Pneumatyczną', 'nie': 'Bez Amortyzacji Pneumatycznej'},
        'Wykonanie Specjalne': {'nie': 'NIE', 'tak': 'TAK', 'no': 'NIE', 'yes': 'TAK'},
        'ATEX': {'nie': 'NIE', 'tak': 'TAK', 'no': 'NIE', 'yes': 'TAK'},
        'Seria': {'scn': 'SCN', 'sdk': 'SDK', 'ssi': 'SSI', 'stk': 'STK'},
        'Zamontowany Osprzęt': {'brak': 'Brak'},
        'Gwint Przyłączy': {'g1/8': 'G1/8', 'g3/8': 'G3/8', 'm5': 'M5'},
        'Ilość Przyłączy': {'dwa': 'Dwa', 'jeden': 'Jeden'},
        'Gwint Tłoczyska': {'m10': 'M10', 'm6': 'M6', 'm16x1,5': 'M16x1,5', 'm20x1,5': 'M20x1,5'},
        'Rodzaj Gwintu Tłoczyska': {
            'zewnętrzny': 'Zewnętrzny',
            'wewnętrzny': 'Wewnętrzny',
            'external': 'Zewnętrzny',
            'internal': 'Wewnętrzny'
        },
        'Rodzaj Tulei': {
            'tuleja okrągła': 'Tuleja Okrągła',
            'tuleja profilowa z kanałkiem trapezowym': 'Tuleja Profilowa z Kanałkiem Trapezowym',
            'tuleja kształtowa': 'Tuleja Kształtowa'
        },
        'Tłok Magnetyczny': {'nie': 'NIE', 'tak': 'TAK', 'no': 'NIE', 'yes': 'TAK'},
        'Materiał Uszczelnień': {'pu': 'PU (Poliuretan)', 'viton': 'VITON'},
        'Funkcja': {'dwustronnego działania': 'Dwustronnego Działania'}
    }

    normalized_data = {}
    for key, value in form_data.items():
        key = key.strip()
        value = value.strip() if isinstance(value, str) else value
        if not value:
            continue

        logger.debug(f"Normalizowanie: {key} = {value}")

        if key == 'Średnica Tłoka':
            value = re.sub(r'\s+', ' ', value)
            if not re.search(r'\[[EHJ]\]', value):
                value = value.replace('mm', 'mm [E]')
        elif key == 'Skok Siłownika':
            try:
                num = int(re.search(r'\d+', value).group())
                value = f"{num:04d} mm"
            except (AttributeError, ValueError):
                pass
        elif key == 'Średnica Tłoczyska':
            value = re.sub(r'\s*mm\s*', ' mm', value.strip())
            try:
                num = int(re.search(r'\d+', value).group())
                value = f"{num} mm"
            except (AttributeError, ValueError):
                pass
        elif key in normalization_rules:
            value_lower = value.lower()
            if value_lower in normalization_rules[key]:
                value = normalization_rules[key][value_lower]

        normalized_data[key] = value
        logger.debug(f"Znormalizowano: {key} -> {value}")

    return normalized_data

def load_projects_from_json():
    """Wczytuje dane z pliku JSON."""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                projects = json.load(f)
                logger.info(f"Wczytano {len(projects)} projektów z {DB_FILE}")
                return projects
        except json.JSONDecodeError as e:
            logger.error(f"Błąd dekodowania JSON: {e}")
            return {}
    logger.warning(f"Plik {DB_FILE} nie istnieje, zwracam pustą bazę")
    return {}

def save_projects_to_json(projects):
    """Zapisuje projekty do pliku JSON."""
    try:
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(projects, f, ensure_ascii=False, indent=4)
        logger.info(f"Zapisano {len(projects)} projektów do {DB_FILE}")
    except Exception as e:
        logger.error(f"Błąd zapisu do {DB_FILE}: {e}")

def get_feature_suggestions(projects):
    """Generuje sugestie wartości dla cech."""
    feature_values = {}
    feature_counts = {}
    for project in projects.values():
        for feature, value in project.get("Cechy", {}).items():
            if feature not in feature_values:
                feature_values[feature] = set()
                feature_counts[feature] = Counter()
            feature_values[feature].add(str(value))
            feature_counts[feature][str(value)] += 1

    suggestions = {}
    for feature in feature_values:
        most_common = feature_counts[feature].most_common(1)
        suggestions[feature] = most_common[0][0] if most_common else sorted(feature_values[feature])[0]
    logger.debug(f"Sugestie cech: {suggestions}")
    return suggestions, {k: sorted(v, key=str.lower) for k, v in feature_values.items()}

def validate_feature_value(feature_name, value, project_cechy, allow_new=False):
    """Waliduje wartość cechy."""
    logger.debug(f"Walidacja cechy: {feature_name} = {value}, allow_new={allow_new}")
    for category, features in categories.items():
        if feature_name in features:
            rules = features[feature_name]
            if "pattern" in rules:
                if not re.match(rules["pattern"], value):
                    logger.error(f"Nieprawidłowy format dla {feature_name}: {value}")
                    return f"Błąd w polu '{feature_name}': Oczekiwano formatu: {rules['hint']}"
                if allow_new and "allowed_values" not in rules:
                    rules["allowed_values"] = []
                if allow_new and value not in rules.get("allowed_values", []):
                    rules["allowed_values"].append(value)
                    logger.info(f"Dodano nową wartość dla {feature_name}: {value}")
            elif "allowed_values" in rules:
                if value not in rules["allowed_values"]:
                    if allow_new:
                        rules["allowed_values"].append(value)
                        logger.info(f"Dodano nową wartość dla {feature_name}: {value}")
                    else:
                        logger.error(f"Niedozwolona wartość dla {feature_name}: {value}")
                        return f"Błąd w polu '{feature_name}': Dozwolone wartości to: {', '.join(rules['allowed_values'])}"
            break
    else:
        if not re.match(r'^[\w\s\-+()°/.,]+$', value):
            logger.error(f"Nieprawidłowy format nowej wartości: {value}")
            return f"Błąd w polu '{feature_name}': Wartość może zawierać litery, cyfry, spacje, myślniki, plusy, nawiasy, stopnie, ukośniki, kropki i przecinki"

    if feature_name == "Regulacja Kąta Obrotu" and value == "NIE" and "Kąt Obrotu" in project_cechy and project_cechy["Kąt Obrotu"] != "Brak":
        logger.error("Niezgodność: Regulacja Kąta Obrotu = NIE, ale Kąt Obrotu != Brak")
        return "Błąd: 'Regulacja Kąta Obrotu' = 'NIE' wymaga 'Kąt Obrotu' = 'Brak'"
    if feature_name == "Kąt Obrotu" and value != "Brak" and "Regulacja Kąta Obrotu" in project_cechy and project_cechy["Regulacja Kąta Obrotu"] == "NIE":
        logger.error("Niezgodność: Kąt Obrotu != Brak, ale Regulacja Kąta Obrotu = NIE")
        return "Błąd: 'Kąt Obrotu' inny niż 'Brak' wymaga 'Regulacja Kąta Obrotu' = 'TAK'"

    logger.debug(f"Walidacja zakończona sukcesem dla {feature_name}")
    return None

def _compare_features(cechy1, cechy2, all_features):
    """Porównuje cechy dwóch projektów."""
    matches = 0
    features_comparison = {}
    differences = []
    for feature in all_features:
        if feature in cechy1 and feature in cechy2:
            val1, val2 = cechy1[feature], cechy2[feature]
            val1_str, val2_str = str(val1), str(val2)
            if feature in ["Średnica Tłoka", "Skok Siłownika", "Średnica Tłoczyska"]:
                match1 = re.search(r'\d+', val1_str)
                match2 = re.search(r'\d+', val2_str)
                if match1 and match2 and float(match1.group()) == float(match2.group()):
                    matches += 1
                else:
                    differences.append(f"{feature}: {val1} vs {val2}")
                    features_comparison[feature] = {'project1': val1, 'project2': val2}
            elif val1 == val2:
                matches += 1
                features_comparison[feature] = {'project1': val1, 'project2': val2}
            else:
                differences.append(f"{feature}: {val1} vs {val2}")
                features_comparison[feature] = {'project1': val1, 'project2': val2}
        else:
            differences.append(f"{feature}: {'Brak' if feature not in cechy1 else cechy1[feature]} vs {'Brak' if feature not in cechy2 else cechy2[feature]}")
            features_comparison[feature] = {
                'project1': cechy1.get(feature, 'Brak'),
                'project2': cechy2.get(feature, 'Brak')
            }
    return matches, features_comparison, differences

def _filter_projects(projects, feature, value):
    """Filtruje projekty według cechy i wartości."""
    filtered = {}
    logger.debug(f"Filtruję projekty dla cechy: {feature}, wartość: {value}")
    for symbol, details in projects.items():
        project_value = details["Cechy"].get(feature)
        if project_value and str(project_value).lower() == str(value).lower():
            filtered[symbol] = details
            logger.debug(f"Znaleziono projekt {symbol} z {feature}={project_value}")
    logger.info(f"Znaleziono {len(filtered)} projektów dla filtru {feature}={value}")
    return filtered

def detect_delimiter(file_content):
    """Wykrywa separator CSV."""
    sample = file_content.decode('utf-8', errors='ignore')[:1024]
    sniffer = csv.Sniffer()
    common_delimiters = [',', ';', '\t', '|']
    try:
        dialect = sniffer.sniff(sample, delimiters=common_delimiters)
        logger.debug(f"Wykryto separator CSV: '{dialect.delimiter}'")
        return dialect.delimiter
    except csv.Error:
        logger.warning("Nie udało się wykryć separatora, domyślnie ','")
        return ','

@app.route('/')
def index():
    projects = load_projects_from_json()
    available_features = set()
    for project in projects.values():
        available_features.update(project.get('Cechy', {}).keys())
    available_features = sorted(available_features)
    sorted_projects = sorted(
        projects.items(),
        key=lambda x: x[1].get('created_at', '1970-01-01T00:00:00'),
        reverse=True
    )
    logger.debug(f"Przekazano {len(sorted_projects)} projektów do index.html")
    return render_template('index.html', projects=dict(sorted_projects), available_features=available_features)

@app.route('/project/<symbol>')
def project_details(symbol):
    projects = load_projects_from_json()
    project = projects.get(symbol)
    if not project:
        logger.error(f"Projekt {symbol} nie znaleziony")
        flash(f"Projekt {symbol} nie znaleziony.", 'error')
        return redirect(url_for('index'))
    return render_template('project_details.html', symbol=symbol, project=project)

@app.route('/compare', methods=['GET', 'POST'])
def compare_projects():
    projects = load_projects_from_json()
    if not projects or len(projects) < 2:
        logger.error("Za mało projektów do porównania")
        flash("Potrzebne są co najmniej 2 projekty do porównania.", 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        project1 = request.form.get('project1')
        project2 = request.form.get('project2')

        if not project1 or not project2:
            logger.error("Nie wybrano dwóch projektów")
            flash("Wybierz dwa projekty.", 'error')
            return render_template('compare.html', projects=projects)
        if project1 == project2:
            logger.error("Wybrano ten sam projekt")
            flash("Wybierz dwa różne projekty.", 'error')
            return render_template('compare.html', projects=projects)
        if project1 not in projects or project2 not in projects:
            logger.error(f"Projekty {project1} lub {project2} nie istnieją")
            flash("Wybrane projekty nie istnieją.", 'error')
            return render_template('compare.html', projects=projects)

        cechy1, cechy2 = projects[project1]["Cechy"], projects[project2]["Cechy"]
        all_features = sorted(set(cechy1.keys()).union(cechy2.keys()))
        matches, features_comparison, differences = _compare_features(cechy1, cechy2, all_features)
        similarity = (matches / len(all_features)) * 100 if all_features else 0

        comparison = {
            'project1_symbol': project1,
            'project2_symbol': project2,
            'features': features_comparison
        }

        return render_template(
            'compare.html',
            projects=projects,
            comparison=comparison,
            similarity=similarity,
            differences=differences,
            project1_name=projects[project1]["Nazwa"],
            project2_name=projects[project2]["Nazwa"],
            project1_id=projects[project1]["ID"],
            project2_id=projects[project2]["ID"]
        )

    return render_template('compare.html', projects=projects)

@app.route('/filter', methods=['GET', 'POST'])
def filter_projects():
    projects = load_projects_from_json()
    if not projects:
        logger.error("Brak projektów do filtrowania")
        flash("Brak projektów do filtrowania.", 'error')
        return render_template('filter.html', projects={}, available_features={})

    suggestions, available_features = get_feature_suggestions(projects)
    logger.debug(f"Dostępne cechy: {list(available_features.keys())}")

    if request.method == 'POST':
        feature = request.form.get('feature')
        value = request.form.get('value')
        logger.debug(f"Otrzymano filtr: cecha={feature}, wartość={value}")

        if not feature or not value:
            logger.error("Nie wybrano cechy lub wartości")
            flash("Wybierz cechę i wartość.", 'error')
            return render_template('filter.html', projects=projects, available_features=available_features, filters={'feature': '', 'value': ''})

        normalized_value = normalize_form_data({feature: value}).get(feature, value)
        filtered_projects = _filter_projects(projects, feature, normalized_value)

        if not filtered_projects:
            logger.warning(f"Brak projektów dla filtru: {feature}={normalized_value}")
            flash(f"Brak projektów dla cechy '{feature}' o wartości '{value}'", 'error')

        return render_template(
            'filter.html',
            projects=filtered_projects,
            available_features=available_features,
            filters={'feature': feature, 'value': value},
            suggestions=suggestions
        )

    return render_template(
        'filter.html',
        projects=projects,
        available_features=available_features,
        filters={'feature': '', 'value': ''},
        suggestions=suggestions
    )

@app.route('/add_project', methods=['GET', 'POST'])
def add_project():
    projects = load_projects_from_json()
    suggestions, available_features = get_feature_suggestions(projects)

    if request.method == 'POST':
        normalized_data = normalize_form_data(request.form.to_dict())
        logger.debug(f"Normalized form data: {normalized_data}")
        symbol = normalized_data.get('symbol')
        project_name = normalized_data.get('nazwa')
        id_project = normalized_data.get('id')

        # Walidacja pól symbol, nazwa, ID
        if not symbol or not project_name or not id_project:
            logger.error("Brakujące wymagane pola")
            flash("Wszystkie pola są wymagane.", 'error')
            return render_template('add_project.html', categories=categories, suggestions=suggestions, available_features=available_features)

        if not id_project.isdigit():
            logger.error("ID projektu nie jest liczbą")
            flash("ID projektu musi być liczbą.", 'error')
            return render_template('add_project.html', categories=categories, suggestions=suggestions, available_features=available_features)

        if symbol in projects:
            logger.error(f"Projekt {symbol} już istnieje")
            flash("Projekt o podanym symbolu już istnieje.", 'error')
            return render_template('add_project.html', categories=categories, suggestions=suggestions, available_features=available_features)

        cechy = {}
        new_value_flags = request.form.getlist('new_value_flag')
        logger.debug(f"New value flags: {new_value_flags}")

        # Przetwarzanie istniejących cech z kategorii
        for category_name, features in categories.items():
            for feature in features:
                value = normalized_data.get(feature)
                new_value = normalized_data.get(f"new_value_{feature}")
                is_new_value = f"{feature}:new" in new_value_flags
                logger.debug(f"Przetwarzanie cechy: {feature}, wartość: {value}, nowa wartość: {new_value}, is_new: {is_new_value}")

                if is_new_value and new_value:
                    error = validate_feature_value(feature, new_value, cechy, allow_new=True)
                    if error:
                        logger.error(f"Błąd walidacji: {error}")
                        flash(error, 'error')
                        return render_template('add_project.html', categories=categories, suggestions=suggestions, available_features=available_features)
                    cechy[feature] = new_value
                elif value:
                    error = validate_feature_value(feature, value, cechy, allow_new=False)
                    if error:
                        logger.error(f"Błąd walidacji: {error}")
                        flash(error, 'error')
                        return render_template('add_project.html', categories=categories, suggestions=suggestions, available_features=available_features)
                    cechy[feature] = value

        # Przetwarzanie nowych, niestandardowych cech
        new_feature_names = request.form.getlist('new_feature_name')
        new_feature_values = request.form.getlist('new_feature_value')
        logger.debug(f"Nowe cechy: names={new_feature_names}, values={new_feature_values}")
        for feature_name, value in zip(new_feature_names, new_feature_values):
            feature_name = feature_name.strip().title()
            value = value.strip()
            if not feature_name or not value:
                continue
            if not re.match(r'^[\w\s\-+()°/\.,]+$', feature_name):
                logger.error(f"Nieprawidłowa nazwa cechy: {feature_name}")
                flash(
                    "Nazwa cechy może zawierać tylko litery, cyfry, spacje, myślniki, plusy, nawiasy, stopnie, ukośniki, kropki i przecinki.",
                    'error')
                return render_template('add_project.html', categories=categories, suggestions=suggestions, available_features=available_features)
            normalized_value = normalize_form_data({feature_name: value}).get(feature_name, value)
            error = validate_feature_value(feature_name, normalized_value, cechy, allow_new=True)
            if error:
                logger.error(f"Błąd walidacji nowej cechy: {error}")
                flash(error, 'error')
                return render_template('add_project.html', categories=categories, suggestions=suggestions, available_features=available_features)
            cechy[feature_name] = normalized_value
            if feature_name not in categories.get("Inne", {}):
                categories.setdefault("Inne", {})[feature_name] = {
                    "hint": "Wprowadź wartość tekstową",
                    "allowed_values": [normalized_value]
                }
            elif normalized_value not in categories["Inne"][feature_name].get("allowed_values", []):
                categories["Inne"][feature_name]["allowed_values"].append(normalized_value)

        # Zapis projektu
        logger.debug(f"Zapisane cechy: {cechy}")
        projects[symbol] = {
            "Nazwa": project_name,
            "ID": id_project,
            "Cechy": cechy,
            "created_at": datetime.utcnow().isoformat()
        }
        save_projects_to_json(projects)
        logger.info(f"Dodano projekt: {symbol}")
        flash(f"Projekt {symbol} dodany pomyślnie.", 'success')
        return redirect(url_for('index'))

    # GET
    return render_template('add_project.html', categories=categories, suggestions=suggestions, available_features=available_features)

@app.route('/load_csv', methods=['GET', 'POST'])
def load_csv():
    projects = load_projects_from_json()
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename.endswith('.csv'):
            logger.error("Nie wybrano pliku CSV")
            flash("Wybierz plik CSV.", 'error')
            return render_template('load_csv.html')

        try:
            file.seek(0)
            raw_data = file.read(1024)
            result = chardet.detect(raw_data)
            encoding = result['encoding'] or 'utf-8'
            logger.debug(f"Wykryto kodowanie pliku: {encoding}")

            file.seek(0)
            delimiter = detect_delimiter(raw_data)

            file.seek(0)
            df = pd.read_csv(file, encoding=encoding, delimiter=delimiter, dtype=str)

            required_columns = ["SYMBOL", "NAZWA_TOWARU", "ID_TOWARU", "NAZWA", "WARTOSC"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.error(f"Brak wymaganych kolumn: {', '.join(missing_columns)}")
                flash(f"Brak wymaganych kolumn: {', '.join(missing_columns)}.", 'error')
                return render_template('load_csv.html')

            for _, row in df.iterrows():
                project_symbol = str(row["SYMBOL"]).strip()
                project_name = str(row["NAZWA_TOWARU"]).strip()
                id_towaru = str(row["ID_TOWARU"]).strip()
                feature_name = str(row["NAZWA"]).strip()
                feature_value = str(row["WARTOSC"]).strip()

                if not project_symbol or not project_name or not id_towaru or not feature_name or not feature_value:
                    logger.warning(f"Pomijanie wiersza: brak danych - {project_symbol}, {project_name}, {id_towaru}, {feature_name}, {feature_value}")
                    continue

                if not id_towaru.isdigit():
                    logger.warning(f"Pomijanie wiersza: ID_TOWARU nie jest liczbą - {id_towaru}")
                    continue

                if project_symbol not in projects:
                    projects[project_symbol] = {
                        "Nazwa": project_name,
                        "ID": id_towaru,
                        "Cechy": {},
                        'created_at': datetime.utcnow().isoformat()
                    }

                normalized_value = normalize_form_data({feature_name: feature_value}).get(feature_name, feature_value)
                error = validate_feature_value(feature_name, normalized_value, projects[project_symbol]["Cechy"], allow_new=True)
                if error:
                    logger.warning(f"Pomijanie cechy: błąd walidacji - {error}")
                    continue

                projects[project_symbol]["Cechy"][feature_name] = normalized_value
                if feature_name not in categories.get("Inne", {}):
                    categories.setdefault("Inne", {})[feature_name] = {
                        "hint": "Wprowadź wartość tekstową",
                        "allowed_values": [normalized_value]
                    }
                elif normalized_value not in categories["Inne"][feature_name].get("allowed_values", []):
                    categories["Inne"][feature_name]["allowed_values"].append(normalized_value)

            save_projects_to_json(projects)
            logger.info(f"Zaimportowano {len(df)} wierszy z CSV")
            flash("Dane z CSV zaimportowane pomyślnie.", 'success')
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Błąd wczytywania CSV: {e}")
            flash(f"Błąd wczytywania pliku: {e}.", 'error')
            return render_template('load_csv.html')

    return render_template('load_csv.html')

@app.route('/add_category_feature', methods=['GET', 'POST'])
def add_category_feature():
    projects = load_projects_from_json()
    form_data = {
        'choice': 'K',
        'name': '',
        'hint': '',
        'category': ''
    }
    edit_mode = False

    if request.method == 'POST':
        action = request.form.get('action', 'add')

        if action == 'edit_category':
            category_name = request.form.get('category_name')
            if category_name in categories:
                form_data = {
                    'choice': 'K',
                    'name': category_name,
                    'hint': '',
                    'category': ''
                }
                edit_mode = True
                logger.info(f"Rozpoczęto edycję kategorii: {category_name}")
            else:
                flash("Kategoria nie istnieje.", 'error')
                logger.error(f"Próba edycji nieistniejącej kategorii: {category_name}")

        elif action == 'edit_feature':
            category_name = request.form.get('category_name')
            feature_name = request.form.get('feature_name')
            if category_name in categories and feature_name in categories[category_name]:
                form_data = {
                    'choice': 'C',
                    'name': feature_name,
                    'hint': categories[category_name][feature_name].get('hint', ''),
                    'category': category_name
                }
                edit_mode = True
                logger.info(f"Rozpoczęto edycję cechy: {feature_name} w kategorii {category_name}")
            else:
                flash("Cecha lub kategoria nie istnieje.", 'error')
                logger.error(f"Próba edycji nieistniejącej cechy: {feature_name} w {category_name}")

        elif action == 'delete_category':
            category_name = request.form.get('category_name')
            if category_name in categories:
                if categories[category_name]:
                    flash("Nie można usunąć kategorii z przypisanymi cechami.", 'error')
                    logger.error(f"Próba usunięcia kategorii {category_name} z cechami")
                else:
                    del categories[category_name]
                    # Update projects to remove category references if necessary
                    for project in projects.values():
                        cechy = project.get("Cechy", {})
                        for feature in list(cechy.keys()):
                            if any(feature in cat for cat in categories.values() if cat != categories.get(category_name)):
                                continue
                            if feature not in categories.get("Inne", {}):
                                del cechy[feature]
                    save_projects_to_json(projects)
                    flash(f"Kategoria {category_name} została usunięta.", 'success')
                    logger.info(f"Usunięto kategorię: {category_name}")
            else:
                flash("Kategoria nie istnieje.", 'error')
                logger.error(f"Próba usunięcia nieistniejącej kategorii: {category_name}")

        elif action == 'delete_feature':
            category_name = request.form.get('category_name')
            feature_name = request.form.get('feature_name')
            if category_name in categories and feature_name in categories[category_name]:
                del categories[category_name][feature_name]
                # Update projects to remove feature
                for project in projects.values():
                    if feature_name in project.get("Cechy", {}):
                        del project["Cechy"][feature_name]
                save_projects_to_json(projects)
                flash(f"Cecha {feature_name} została usunięta.", 'success')
                logger.info(f"Usunięto cechę: {feature_name} z kategorii {category_name}")
            else:
                flash("Cecha lub kategoria nie istnieje.", 'error')
                logger.error(f"Próba usunięcia nieistniejącej cechy: {feature_name} w {category_name}")

        elif action in ['add', 'edit']:
            choice = request.form.get('choice')
            name = request.form.get('name').strip().title()
            hint = request.form.get('hint', '').strip()
            category = request.form.get('category', '').strip()

            if not name:
                flash("Nazwa wymagana.", 'error')
                form_data.update(choice=choice, name=name, hint=hint, category=category)
                logger.error("Brak nazwy dla nowej kategorii/cechy")
                return render_template('add_category_feature.html', categories=categories, form_data=form_data, edit_mode=edit_mode)

            if not re.match(r'^[\w\s\-+()°/.,]+$', name):
                flash("Nazwa może zawierać tylko litery, cyfry, spacje, myślniki, plusy, nawiasy, stopnie, ukośniki, kropki i przecinki.", 'error')
                form_data.update(choice=choice, name=name, hint=hint, category=category)
                logger.error(f"Nieprawidłowa nazwa: {name}")
                return render_template('add_category_feature.html', categories=categories, form_data=form_data, edit_mode=edit_mode)

            if action == 'edit':
                original_name = request.form.get('original_name')
                original_category = request.form.get('original_category', '')

            if choice == 'K':
                if action == 'add' and name in categories:
                    flash("Ta kategoria już istnieje.", 'error')
                    form_data.update(choice=choice, name=name, hint=hint, category=category)
                    logger.error(f"Kategoria {name} już istnieje")
                    return render_template('add_category_feature.html', categories=categories, form_data=form_data, edit_mode=edit_mode)
                elif action == 'edit' and original_name != name and name in categories:
                    flash("Kategoria o tej nazwie już istnieje.", 'error')
                    form_data.update(choice=choice, name=name, hint=hint, category=category)
                    logger.error(f"Kategoria {name} już istnieje podczas edycji")
                    return render_template('add_category_feature.html', categories=categories, form_data=form_data, edit_mode=edit_mode)
                if action == 'edit':
                    if original_name in categories:
                        categories[name] = categories.pop(original_name)
                        # Update projects if category name changed
                        for project in projects.values():
                            cechy = project.get("Cechy", {})
                            for feature in list(cechy.keys()):
                                if feature in categories[name]:
                                    continue
                                if feature not in categories.get("Inne", {}):
                                    del cechy[feature]
                        save_projects_to_json(projects)
                        flash(f"Kategoria {original_name} zmieniona na {name}.", 'success')
                        logger.info(f"Zmieniono nazwę kategorii z {original_name} na {name}")
                    else:
                        flash("Kategoria nie istnieje.", 'error')
                        logger.error(f"Próba edycji nieistniejącej kategorii: {original_name}")
                        return render_template('add_category_feature.html', categories=categories, form_data=form_data, edit_mode=edit_mode)
                else:
                    categories[name] = {}
                    flash(f"Dodano kategorię: {name}.", 'success')
                    logger.info(f"Dodano kategorię: {name}")

            else:  # choice == 'C'
                if not category or category not in categories:
                    flash("Wybierz istnieją kategorię.", 'error')
                    form_data.update(choice=choice, name=name, hint=hint, category=category)
                    logger.error("Nie wybrano istniejącej kategorii")
                    return render_template('add_category_feature.html', categories=categories, form_data=form_data, edit_mode=edit_mode)
                if action == 'add' and name in categories[category]:
                    flash("Ta cecha już istnieje w tej kategorii.", 'error')
                    form_data.update(choice=choice, name=name, hint=hint, category=category)
                    logger.error(f"Cecha {name} już istnieje w kategorii {category}")
                    return render_template('add_category_feature.html', categories=categories, form_data=form_data, edit_mode=edit_mode)
                elif action == 'edit' and (original_category != category or original_name != name) and name in categories[category]:
                    flash("Cecha o tej nazwie już istnieje w tej kategorii.", 'error')
                    form_data.update(choice=choice, name=name, hint=hint, category=category)
                    logger.error(f"Cecha {name} już istnieje w kategorii {category} podczas edycji")
                    return render_template('add_category_feature.html', categories=categories, form_data=form_data, edit_mode=edit_mode)
                if action == 'edit':
                    if original_category in categories and original_name in categories[original_category]:
                        if original_category != category:
                            # Move feature to new category
                            feature_data = categories[original_category].pop(original_name)
                            feature_data['hint'] = hint or "Wprowadź wartość"
                            categories[category][name] = feature_data
                        else:
                            # Update feature in same category
                            categories[category][name] = categories[category].pop(original_name)
                            categories[category][name]['hint'] = hint or "Wprowadź wartość"
                        # Update projects to reflect feature name change
                        for project in projects.values():
                            cechy = project.get("Cechy", {})
                            if original_name in cechy:
                                cechy[name] = cechy.pop(original_name)
                        save_projects_to_json(projects)
                        flash(f"Cecha {original_name} zmieniona na {name} w kategorii {category}.", 'success')
                        logger.info(f"Zmieniono cechę z {original_name} na {name} w kategorii {category}")
                    else:
                        flash("Cecha lub kategoria nie istnieje.", 'error')
                        logger.error(f"Próba edycji nieistniejącej cechy: {original_name} w {original_category}")
                        return render_template('add_category_feature.html', categories=categories, form_data=form_data, edit_mode=edit_mode)
                else:
                    categories[category][name] = {"hint": hint or "Wprowadź wartość", "allowed_values": []}
                    flash(f"Dodano cechę: {name} do kategorii {category}.")
                    logger.info(f"Dodano cechę {name} do kategorii {category}")

            return redirect(url_for('add_category_feature'))

    return render_template('add_category_feature.html', categories=categories, form_data=form_data, edit_mode=edit_mode)

@app.route('/sort_similarity', methods=['GET', 'POST'])
def sort_similarity():
    projects = load_projects_from_json()
    logger.debug(f"Loaded {len(projects)} projects")
    if not projects or len(projects) < 2:
        logger.error("Za mało projektów do sortowania")
        flash("Potrzebne są co najmniej 2 projekty do sortowania.", 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        reference_project = request.form.get('reference_project')
        logger.debug(f"Received reference_project: {reference_project}")
        if not reference_project or reference_project not in projects:
            logger.error(f"Projekt odniesienia {reference_project} nie istnieje")
            flash("Wybierz istniejący projekt odniesienia.", 'error')
            return render_template('sort_similarity.html', projects=projects)

        similarities = []
        for proj in projects:
            if proj != reference_project:
                cechy1, cechy2 = projects[reference_project]["Cechy"], projects[proj]["Cechy"]
                all_features = sorted(set(cechy1.keys()).union(cechy2.keys()))
                matches, _, _ = _compare_features(cechy1, cechy2, all_features)
                similarity = (matches / len(all_features)) * 100 if all_features else 0
                similarities.append((proj, similarity))
                logger.debug(f"Similarity for {proj}: {similarity}%")
        sorted_similarities = sorted(similarities, key=lambda x: x[1], reverse=True)
        logger.debug(f"Sorted similarities: {sorted_similarities}")

        return render_template(
            'sort_similarity.html',
            projects=projects,
            sorted_similarities=sorted_similarities,
            reference_project=reference_project,
            reference_name=projects[reference_project]["Nazwa"],
            reference_id=projects[reference_project]["ID"]
        )

    return render_template('sort_similarity.html', projects=projects)
@app.route('/search', methods=['GET', 'POST'])
def search_projects():
    projects = load_projects_from_json()
    if not projects:
        logger.error("Brak projektów do wyszukiwania")
        flash("Brak projektów do wyszukiwania.", 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        search_term = request.form.get('search_term', '').lower()
        if not search_term:
            logger.error("Brak frazy wyszukiwania")
            flash("Wprowadź frazę wyszukiwania.", 'error')
            return render_template('search.html', projects=projects)

        found = [
            {'symbol': symbol, 'details': details}
            for symbol, details in projects.items()
            if search_term in details["Nazwa"].lower() or any(search_term in str(value).lower() for value in details["Cechy"].values())
        ]

        return render_template('search.html', projects=projects, found=found, search_term=search_term)

    return render_template('search.html', projects=projects)

@app.route('/export_csv')
def export_csv():
    projects = load_projects_from_json()
    if not projects:
        logger.error("Brak projektów do eksportu")
        flash("Brak projektów do eksportu.", 'error')
        return redirect(url_for('index'))

    output = StringIO()
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(["SYMBOL", "NAZWA_TOWARU", "ID_TOWARU", "NAZWA", "WARTOSC"])
    for symbol, details in projects.items():
        for feature, value in details["Cechy"].items():
            writer.writerow([symbol, details["Nazwa"], details["ID"], feature, value])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=projects.csv"
    response.headers["Content-Type"] = "text/csv; charset=UTF-8"
    logger.info("Wygenerowano plik CSV do eksportu")
    return response

@app.route('/delete_project/<symbol>', methods=['POST'])
def delete_project(symbol):
    projects = load_projects_from_json()
    if symbol not in projects:
        logger.error(f"Projekt {symbol} nie istnieje")
        flash(f"Projekt {symbol} nie istnieje.", 'error')
        return redirect(url_for('index'))

    del projects[symbol]
    save_projects_to_json(projects)
    logger.info(f"Usunięto projekt: {symbol}")
    flash(f"Projekt {symbol} został usunięty.", 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)