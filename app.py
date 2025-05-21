from flask import Flask, render_template, request, redirect, url_for, make_response
import json
import os
import re
import csv
from io import StringIO
import pandas as pd
from operator import itemgetter

app = Flask(__name__)

# Hierarchiczna lista kategorii i cech z podpowiedziami
categories = {
    "Pneumatyka": {
        "Średnica Tłoka": "np. 'D 032 mm', 'D 050 mm' (format: D + liczba + mm)",
        "Skok Siłownika": "np. '0005 mm', '0020 mm' (liczba w mm)",
        "Ilość Tłoków": "np. 'Jeden', 'Dwa' (słownie)",
        "Ilość Tłoczysk": "np. 'Jedno', 'Dwa' (słownie)",
        "Gwint Przyłączy": "np. 'M5', 'G1/8' (standardowe oznaczenia gwintów)",
        "Tłok Magnetyczny": "np. 'TAK', 'NIE' (tylko TAK lub NIE)"
    },
    "Mechanika": {
        "Zabezpieczenie Przed Obrotem": "np. 'TAK', 'NIE' (tylko TAK lub NIE)",
        "Regulacja Kąta Obrotu": "np. 'TAK', 'NIE' (tylko TAK lub NIE)",
        "Kąt Obrotu": "np. '90°', '180°', 'Brak' (stopnie lub 'Brak')",
        "Amortyzacja Pneumatyczna": "np. 'TAK', 'NIE' (tylko TAK lub NIE)"
    },
    "Materiały": {
        "Materiał Tłoczyska": "np. 'Stal Węglowa Chromowana', 'Stal Nierdzewna'",
        "Materiał Tulei": "np. 'Stop Aluminium', 'Stal'"
    },
    "Dodatki": {
        "Dodatkowy Zgarniacz": "np. 'TAK', 'NIE' (tylko TAK lub NIE)"
    }
}

# Ścieżka do pliku JSON
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "data", "projects_db.json")

# Funkcja wczytująca projekty z JSON
def load_projects_from_json():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            projects = json.load(f)
            print(f"Wczytano {len(projects)} projektów z {DB_FILE}")
            return projects
    print(f"Plik {DB_FILE} nie znaleziony")
    return {}

# Funkcja zapisująca projekty do JSON
def save_projects_to_json(projects):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(projects, f, ensure_ascii=False, indent=4)

# Funkcja pobierająca wszystkie unikalne cechy i ich wartości
def get_all_features(projects):
    features = {}
    for project in projects.values():
        for feature, value in project.get("Cechy", {}).items():
            if feature not in features:
                features[feature] = set()
            features[feature].add(str(value))
    return {feature: sorted(list(values)) for feature, values in features.items()}

# Funkcja walidująca wartości cech
def validate_feature_value(feature_name, value, project_cechy):
    rules = {
        "Średnica Tłoka": (r"D \d{3} mm", "Błąd: Wartość musi być w formacie 'D XXX mm' (np. 'D 032 mm')!"),
        "Skok Siłownika": (r"\d{4} mm", "Błąd: Wartość musi być w formacie 'XXXX mm' (np. '0005 mm')!"),
        "Tłok Magnetyczny": (["TAK", "NIE"], "Błąd: Wartość musi być 'TAK' lub 'NIE'!"),
        "Zabezpieczenie Przed Obrotem": (["TAK", "NIE"], "Błąd: Wartość musi być 'TAK' lub 'NIE'!"),
        "Regulacja Kąta Obrotu": (["TAK", "NIE"], "Błąd: Wartość musi być 'TAK' lub 'NIE'!"),
        "Amortyzacja Pneumatyczna": (["TAK", "NIE"], "Błąd: Wartość musi być 'TAK' lub 'NIE'!"),
        "Dodatkowy Zgarniacz": (["TAK", "NIE"], "Błąd: Wartość musi być 'TAK' lub 'NIE'!"),
        "Kąt Obrotu": (r"\d+°|Brak", "Błąd: Wartość musi być w formacie 'X°' (np. '90°') lub 'Brak'!")
    }
    if feature_name in rules:
        pattern, error_msg = rules[feature_name]
        if isinstance(pattern, list):
            if value not in pattern:
                return error_msg
        elif not re.match(pattern, value):
            return error_msg
    if feature_name == "Regulacja Kąta Obrotu" and value == "NIE" and "Kąt Obrotu" in project_cechy and project_cechy["Kąt Obrotu"] != "Brak":
        return "Błąd: 'Regulacja Kąta Obrotu' = 'NIE' wyklucza 'Kąt Obrotu' inny niż 'Brak'!"
    if feature_name == "Kąt Obrotu" and value != "Brak" and "Regulacja Kąta Obrotu" in project_cechy and project_cechy["Regulacja Kąta Obrotu"] == "NIE":
        return "Błąd: 'Kąt Obrotu' inny niż 'Brak' wymaga 'Regulacja Kąta Obrotu' = 'TAK'!"
    return None

# Funkcja porównująca cechy dwóch projektów
def _compare_features(cechy1, cechy2, all_features):
    matches = 0
    features_comparison = {}
    differences = []
    for feature in all_features:
        if feature in cechy1 and feature in cechy2:
            val1, val2 = cechy1[feature], cechy2[feature]
            val1_str, val2_str = str(val1), str(val2)
            if feature in ["Średnica Tłoka", "Skok Siłownika"]:
                match1, match2 = re.search(r"\d+", val1_str), re.search(r"\d+", val2_str)
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

# Funkcja filtrująca projekty
def _filter_projects(projects, feature, value):
    filtered = {}
    for symbol, details in projects.items():
        if feature in details["Cechy"] and details["Cechy"][feature] == value:
            filtered[symbol] = details
    return filtered

@app.route('/')
def index():
    projects = load_projects_from_json()
    return render_template('index.html', projects=projects)

@app.route('/project/<symbol>')
def project_details(symbol):
    projects = load_projects_from_json()
    project = projects.get(symbol)
    if not project:
        return render_template('error.html', error_message="Projekt nie znaleziony"), 404
    return render_template('project_details.html', project=project)

@app.route('/compare', methods=['GET', 'POST'])
def compare_projects():
    projects = load_projects_from_json()
    if not projects or len(projects) < 2:
        return render_template('error.html', error_message="Potrzebne są co najmniej 2 projekty do porównania"), 400

    if request.method == 'POST':
        project1 = request.form.get('project1')
        project2 = request.form.get('project2')

        if not project1 or not project2:
            return render_template('compare.html', projects=projects, error="Wybierz dwa projekty"), 400
        if project1 == project2:
            return render_template('compare.html', projects=projects, error="Wybierz dwa różne projekty"), 400
        if project1 not in projects or project2 not in projects:
            return render_template('compare.html', projects=projects, error="Wybrane projekty nie istnieją"), 400

        cechy1, cechy2 = projects[project1]["Cechy"], projects[project2]["Cechy"]
        all_features = set(cechy1.keys()).union(cechy2.keys())
        matches, features_comparison, differences = _compare_features(cechy1, cechy2, all_features)
        similarity = (matches / len(all_features)) * 100 if all_features else 0

        comparison = {
            'project1_symbol': project1,
            'project2_symbol': project2,
            'features': features_comparison
        }

        return render_template('compare.html',
                               projects=projects,
                               comparison=comparison,
                               similarity=similarity,
                               differences=differences,
                               project1_name=projects[project1]["Nazwa"],
                               project2_name=projects[project2]["Nazwa"],
                               project1_id=projects[project1]["ID"],
                               project2_id=projects[project2]["ID"])

    return render_template('compare.html', projects=projects)

@app.route('/filter', methods=['GET', 'POST'])
def filter_projects():
    projects = load_projects_from_json()
    if not projects:
        return render_template('error.html', error_message="Brak projektów do filtrowania"), 400

    available_features = get_all_features(projects) or {
        "Średnica Tłoka": ["D 032 mm", "D 050 mm"],
        "Skok Siłownika": ["0005 mm", "0020 mm"],
        "Tłok Magnetyczny": ["TAK", "NIE"]
    }

    if request.method == 'POST':
        feature = request.form.get('feature')
        value = request.form.get('value')
        if not feature or not value:
            return render_template('filter.html',
                                   projects=projects,
                                   available_features=available_features,
                                   filters={'feature': feature, 'value': value},
                                   error="Wybierz cechę i wartość"), 400

        filtered_projects = _filter_projects(projects, feature, value)
        return render_template('filter.html',
                               projects=projects,
                               filtered_projects=filtered_projects,
                               available_features=available_features,
                               filters={'feature': feature, 'value': value})

    return render_template('filter.html',
                           projects=projects,
                           filtered_projects=projects,
                           available_features=available_features,
                           filters={})

@app.route('/add_project', methods=['GET', 'POST'])
def add_project():
    projects = load_projects_from_json()
    available_features = get_all_features(projects) or {
        "Średnica Tłoka": ["D 032 mm", "D 050 mm"],
        "Skok Siłownika": ["0005 mm", "0020 mm"],
        "Tłok Magnetyczny": ["TAK", "NIE"]
    }

    if request.method == 'POST':
        symbol = request.form.get('symbol')
        nazwa = request.form.get('nazwa')
        id_proj = request.form.get('id')

        if not symbol or not nazwa or not id_proj:
            return render_template('add_project.html',
                                   available_features=available_features,
                                   error="Wszystkie pola (symbol, nazwa, ID) są wymagane"), 400

        if not id_proj.isdigit():
            return render_template('add_project.html',
                                   available_features=available_features,
                                   error="ID projektu musi być liczbą"), 400

        if symbol in projects:
            return render_template('add_project.html',
                                   available_features=available_features,
                                   error="Projekt o podanym symbolu już istnieje"), 400

        cechy = {}
        for feature in available_features:
            value = request.form.get(feature)
            if value:
                error = validate_feature_value(feature, value, cechy)
                if error:
                    return render_template('add_project.html',
                                           available_features=available_features,
                                           error=error), 400
                cechy[feature] = value

        new_features = request.form.getlist('new_feature_name')
        new_values = request.form.getlist('new_feature_value')
        for name, value in zip(new_features, new_values):
            if name and value:
                error = validate_feature_value(name, value, cechy)
                if error:
                    return render_template('add_project.html',
                                           available_features=available_features,
                                           error=error), 400
                cechy[name] = value

        projects[symbol] = {
            "Nazwa": nazwa,
            "ID": id_proj,
            "Cechy": cechy
        }

        save_projects_to_json(projects)
        return redirect(url_for('index'))

    return render_template('add_project.html', available_features=available_features)

@app.route('/load_xlsx', methods=['GET', 'POST'])
def load_xlsx():
    projects = load_projects_from_json()
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename.endswith('.xlsx'):
            return render_template('load_xlsx.html', error="Wybierz plik XLSX"), 400

        try:
            df = pd.read_excel(file)
            for _, row in df.iterrows():
                project_symbol = str(row["SYMBOL"])
                if project_symbol not in projects:
                    projects[project_symbol] = {
                        "Nazwa": str(row["NAZWA_TOWARU"]),
                        "ID": str(row["ID_TOWARU"]),
                        "Cechy": {}
                    }
                projects[project_symbol]["Cechy"][str(row["NAZWA"])] = str(row["WARTOSC"])
            save_projects_to_json(projects)
            return redirect(url_for('index'))
        except Exception as e:
            return render_template('load_xlsx.html', error=f"Błąd wczytywania pliku: {e}"), 400

    return render_template('load_xlsx.html')

@app.route('/add_category_feature', methods=['GET', 'POST'])
def add_category_feature():
    if request.method == 'POST':
        choice = request.form.get('choice')
        name = request.form.get('name')
        hint = request.form.get('hint', '')
        category = request.form.get('category', '')

        if not name:
            return render_template('add_category_feature.html',
                                   categories=categories,
                                   error="Nazwa jest wymagana"), 400

        if choice == 'K':
            if name in categories:
                return render_template('add_category_feature.html',
                                       categories=categories,
                                       error="Ta kategoria już istnieje"), 400
            categories[name] = {}
        else:
            if not category or category not in categories:
                return render_template('add_category_feature.html',
                                       categories=categories,
                                       error="Wybierz istniejącą kategorię"), 400
            if name in categories[category]:
                return render_template('add_category_feature.html',
                                       categories=categories,
                                       error="Ta cecha już istnieje w tej kategorii"), 400
            categories[category][name] = hint

        return redirect(url_for('index'))

    return render_template('add_category_feature.html', categories=categories)

@app.route('/sort_similarity', methods=['GET', 'POST'])
def sort_similarity():
    projects = load_projects_from_json()
    if not projects or len(projects) < 2:
        return render_template('error.html', error_message="Potrzebne są co najmniej 2 projekty do sortowania"), 400

    if request.method == 'POST':
        reference_proj = request.form.get('reference_project')
        if not reference_proj or reference_proj not in projects:
            return render_template('sort_similarity.html',
                                   projects=projects,
                                   error="Wybierz istniejący projekt odniesienia"), 400

        similarities = []
        for proj in projects:
            if proj != reference_proj:
                cechy1, cechy2 = projects[reference_proj]["Cechy"], projects[proj]["Cechy"]
                all_features = set(cechy1.keys()).union(cechy2.keys())
                matches, _, _ = _compare_features(cechy1, cechy2, all_features)  # Poprawka: obsługa 3 wartości
                similarity = (matches / len(all_features)) * 100 if all_features else 0
                similarities.append((proj, similarity))
        sorted_projects = sorted(similarities, key=itemgetter(1), reverse=True)

        return render_template('sort_similarity.html',
                               projects=projects,
                               sorted_projects=sorted_projects,
                               reference_project=reference_proj,
                               reference_name=projects[reference_proj]["Nazwa"],
                               reference_id=projects[reference_proj]["ID"])

    return render_template('sort_similarity.html', projects=projects)

@app.route('/search', methods=['GET', 'POST'])
def search_projects():
    projects = load_projects_from_json()
    if not projects:
        return render_template('error.html', error_message="Brak projektów do wyszukiwania"), 400

    if request.method == 'POST':
        search_term = request.form.get('search_term', '').lower()
        if not search_term:
            return render_template('search.html',
                                   projects=projects,
                                   error="Wprowadź frazę wyszukiwania"), 400

        found = [
            symbol for symbol, details in projects.items()
            if search_term in details["Nazwa"].lower() or
               any(search_term in str(value).lower() for value in details["Cechy"].values())
        ]

        return render_template('search.html',
                               projects=projects,
                               found=found,
                               search_term=search_term)

    return render_template('search.html', projects=projects)

@app.route('/export_csv')
def export_csv():
    projects = load_projects_from_json()
    if not projects:
        return render_template('error.html', error_message="Brak projektów do eksportu"), 400

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Symbol", "Nazwa", "ID", "Cecha", "Wartość"])
    for symbol, details in projects.items():
        for feature, value in details["Cechy"].items():
            writer.writerow([symbol, details["Nazwa"], details["ID"], feature, value])

    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=projects.csv"
    response.headers["Content-Type"] = "text/csv"
    return response

if __name__ == '__main__':
    app.run(debug=True)