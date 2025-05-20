import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import os
import json
import re
import csv
from operator import itemgetter

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

# Ścieżka do pliku JSON jako bazy danych
DB_FILE = os.path.join(os.path.dirname(__file__), "projects_db.json")

class ProjectApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Analiza Projektów")
        self.projects = {}
        self.load_projects_from_json()

        # Styl dla nowoczesnego wyglądu
        style = ttk.Style()
        style.theme_use('clam')

        # Menu główne
        self.menu = tk.Menu(root)
        root.config(menu=self.menu)
        options = [
            ("Wczytaj z XLSX", self.load_projects_from_xlsx),
            ("Wyświetl projekty", self.show_projects),
            ("Wybierz projekt", self.select_project),
            ("Dodaj projekt", self.add_project_manually),
            ("Dodaj kategorię/cechę", self.add_category_or_feature),
            ("Porównaj projekty", self.compare_projects),
            ("Sortuj wg podobieństwa", self.sort_projects_by_similarity),
            ("Filtruj projekty", self.filter_projects),
            ("Eksportuj do CSV", self.export_to_csv),
            ("Wyszukaj projekty", self.search_projects),
            ("Wyczyść wyniki", self.clear_details),
            ("Wyjdź", root.quit)
        ]
        for label, command in options:
            self.menu.add_command(label=label, command=command)

        # Ramka dla Treeview z suwakami
        self.tree_frame = ttk.Frame(root)
        self.tree_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Treeview do wyświetlania projektów
        self.tree = ttk.Treeview(self.tree_frame, columns=("Symbol", "Nazwa", "ID"), show="headings")
        for col, text in [("Symbol", "Symbol"), ("Nazwa", "Nazwa"), ("ID", "ID")]:
            self.tree.heading(col, text=text)
        self._add_scrollbars(self.tree_frame, self.tree)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Ramka dla Text z suwakiem
        self.details_frame = ttk.Frame(root)
        self.details_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Text do wyświetlania szczegółów i wyników
        self.details_text = tk.Text(self.details_frame, height=20, width=50)
        self._add_scrollbars(self.details_frame, self.details_text, horizontal=False)
        self.details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Przycisk "Wyczyść" pod polem tekstowym
        ttk.Button(self.details_frame, text="Wyczyść", command=self.clear_details).pack(side=tk.BOTTOM, pady=5)

    def _add_scrollbars(self, frame, widget, horizontal=True):
        """Dodaje suwaki do widgetu (Treeview lub Text)."""
        scroll_y = ttk.Scrollbar(frame, orient="vertical", command=widget.yview)
        widget.configure(yscrollcommand=scroll_y.set)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        if horizontal:
            scroll_x = ttk.Scrollbar(frame, orient="horizontal", command=widget.xview)
            widget.configure(xscrollcommand=scroll_x.set)
            scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

    def load_projects_from_json(self):
        """Wczytuje projekty z pliku JSON."""
        if os.path.exists(DB_FILE):
            with open(DB_FILE, "r", encoding="utf-8") as f:
                self.projects = json.load(f)
        else:
            self.projects = {}

    def save_projects_to_json(self):
        """Zapisuje projekty do pliku JSON."""
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(self.projects, f, ensure_ascii=False, indent=4)

    def load_projects_from_xlsx(self):
        """Wczytuje dane projektów z pliku XLSX."""
        file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
        if not file_path:
            return
        try:
            df = pd.read_excel(file_path)
            for _, row in df.iterrows():
                project_symbol = row["SYMBOL"]
                if project_symbol not in self.projects:
                    self.projects[project_symbol] = {
                        "Nazwa": row["NAZWA_TOWARU"],
                        "ID": row["ID_TOWARU"],
                        "Cechy": {}
                    }
                self.projects[project_symbol]["Cechy"][row["NAZWA"]] = str(row["WARTOSC"])
            self.save_projects_to_json()
            messagebox.showinfo("Sukces", "Pomyślnie wczytano dane z pliku")
            self.show_projects()
        except Exception as e:
            messagebox.showerror("Błąd", f"Wystąpił błąd: {e}")

    def show_projects(self):
        """Wyświetla listę projektów w Treeview."""
        for row in self.tree.get_children():
            self.tree.delete(row)
        if not self.projects:
            messagebox.showinfo("Informacja", "Brak wczytanych projektów!")
            return
        for symbol, details in self.projects.items():
            self.tree.insert("", "end", values=(symbol, details["Nazwa"], details["ID"]))

    def select_project(self):
        """Wyświetla szczegóły wybranego projektu oraz listę projektów posortowanych według podobieństwa."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Informacja", "Wybierz projekt z listy!")
            return
        symbol = self.tree.item(selected[0])["values"][0]
        details = self.projects[symbol]
        self.details_text.delete(1.0, tk.END)
        self.details_text.insert(tk.END, f"Projekt: {symbol} - {details['Nazwa']} (ID: {details['ID']})\n")
        for feature, value in details["Cechy"].items():
            self.details_text.insert(tk.END, f"  {feature}: {value}\n")
        if len(self.projects) < 2:
            self.details_text.insert(tk.END, "\nBrak innych projektów do porównania.\n")
            return
        similarities = []
        for proj in self.projects:
            if proj != symbol:
                cechy1, cechy2 = details["Cechy"], self.projects[proj]["Cechy"]
                all_features = set(cechy1.keys()).union(cechy2.keys())
                matches = sum(1 for f in all_features if cechy1.get(f) == cechy2.get(f))
                similarity = (matches / len(all_features)) * 100 if all_features else 0
                similarities.append((proj, similarity))
        sorted_projects = sorted(similarities, key=itemgetter(1), reverse=True)
        self.details_text.insert(tk.END, "\nProjekty posortowane wg podobieństwa:\n")
        for proj, sim in sorted_projects:
            self.details_text.insert(tk.END, f"{proj} - {self.projects[proj]['Nazwa']} (ID: {self.projects[proj]['ID']}): {sim:.2f}%\n")

    def add_project_manually(self):
        """Dodaje nowy projekt ręcznie za pomocą okna dialogowego."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Dodaj projekt")
        dialog.geometry("400x300")

        entries = {}
        for label, key in [("Symbol:", "symbol"), ("Nazwa:", "name"), ("ID (cyfry):", "id")]:
            tk.Label(dialog, text=label).pack()
            entries[key] = tk.Entry(dialog)
            entries[key].pack()

        features_frame = ttk.Frame(dialog)
        features_frame.pack(fill=tk.BOTH, expand=True)
        features = {}

        def add_feature():
            feat_dialog = tk.Toplevel(dialog)
            tk.Label(feat_dialog, text="Wybierz kategorię:").pack()
            cat_var = tk.StringVar(value=list(categories.keys())[0])
            ttk.Combobox(feat_dialog, textvariable=cat_var, values=list(categories.keys())).pack()

            tk.Label(feat_dialog, text="Wybierz cechę:").pack()
            feat_var = tk.StringVar()
            feat_combo = ttk.Combobox(feat_dialog, textvariable=feat_var)
            feat_combo.pack()

            def update_features(*args):
                feat_combo["values"] = list(categories[cat_var.get()].keys())
                feat_var.set(feat_combo["values"][0] if feat_combo["values"] else "")
            cat_var.trace("w", update_features)
            update_features()

            tk.Label(feat_dialog, text="Wartość:").pack()
            value_entry = tk.Entry(feat_dialog)
            value_entry.pack()

            def save_feature():
                feature, value = feat_var.get(), value_entry.get()
                error = self.validate_feature_value(feature, value, features)
                if error:
                    messagebox.showerror("Błąd", error)
                else:
                    features[feature] = value
                    feat_dialog.destroy()
            tk.Button(feat_dialog, text="Zapisz", command=save_feature).pack()

        tk.Button(features_frame, text="Dodaj cechę", command=add_feature).pack()

        def save_project():
            symbol = entries["symbol"].get()
            if symbol in self.projects:
                messagebox.showerror("Błąd", "Projekt o tym symbolu już istnieje!")
                return
            project_id = entries["id"].get()
            if not project_id.isdigit():
                messagebox.showerror("Błąd", "ID projektu musi być liczbą!")
                return
            self.projects[symbol] = {"Nazwa": entries["name"].get(), "ID": project_id, "Cechy": features}
            self.save_projects_to_json()
            self.show_projects()
            dialog.destroy()

        tk.Button(dialog, text="Zapisz projekt", command=save_project).pack()

    def add_category_or_feature(self):
        """Dodaje nową kategorię lub cechę."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Dodaj kategorię lub cechę")
        choice_var = tk.StringVar(value="K")
        tk.Label(dialog, text="Wybierz działanie:").pack()
        tk.Radiobutton(dialog, text="Dodaj kategorię", variable=choice_var, value="K").pack()
        tk.Radiobutton(dialog, text="Dodaj cechę", variable=choice_var, value="C").pack()

        tk.Label(dialog, text="Nazwa:").pack()
        name_entry = tk.Entry(dialog)
        name_entry.pack()

        tk.Label(dialog, text="Podpowiedź (dla cechy):").pack()
        hint_entry = tk.Entry(dialog)
        hint_entry.pack()

        tk.Label(dialog, text="Kategoria (dla cechy):").pack()
        cat_var = tk.StringVar(value=list(categories.keys())[0])
        cat_combo = ttk.Combobox(dialog, textvariable=cat_var, values=list(categories.keys()))
        cat_combo.pack()

        def save():
            name = name_entry.get()
            if choice_var.get() == "K":
                if name in categories:
                    messagebox.showerror("Błąd", "Ta kategoria już istnieje!")
                else:
                    categories[name] = {}
                    messagebox.showinfo("Sukces", f"Dodano kategorię: {name}")
                    dialog.destroy()
            else:
                category = cat_var.get()
                hint = hint_entry.get()
                if name in categories[category]:
                    messagebox.showerror("Błąd", "Ta cecha już istnieje!")
                else:
                    categories[category][name] = hint
                    messagebox.showinfo("Sukces", f"Dodano cechę '{name}' do '{category}'")
                    dialog.destroy()

        tk.Button(dialog, text="Zapisz", command=save).pack()

    def validate_feature_value(self, feature_name, value, project_cechy):
        """Sprawdza poprawność wartości cechy."""
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

    def compare_projects(self):
        """Porównuje dwa wybrane projekty i wyświetla podobieństwo."""
        if len(self.projects) < 2:
            messagebox.showerror("Błąd", "Potrzebne są co najmniej 2 projekty!")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Porównaj projekty")
        tk.Label(dialog, text="Wybierz dwa projekty:").pack()
        proj_vars = [tk.StringVar(value=key) for key in list(self.projects.keys())[:2]]
        for var in proj_vars:
            ttk.Combobox(dialog, textvariable=var, values=list(self.projects.keys())).pack()

        def compare():
            proj1, proj2 = proj_vars[0].get(), proj_vars[1].get()
            if proj1 == proj2:
                messagebox.showerror("Błąd", "Wybierz dwa różne projekty!")
                return
            cechy1, cechy2 = self.projects[proj1]["Cechy"], self.projects[proj2]["Cechy"]
            all_features = set(cechy1.keys()).union(cechy2.keys())
            matches, differences = self._compare_features(cechy1, cechy2, all_features)
            similarity = (matches / len(all_features)) * 100 if all_features else 0
            result = (
                f"Porównanie: {proj1} (ID: {self.projects[proj1]['ID']}) vs {proj2} (ID: {self.projects[proj2]['ID']})\n"
                f"Podobieństwo: {similarity:.2f}%\nRóżnice:\n" +
                ("\n".join([f"  - {diff}" for diff in differences]) if differences else "  Brak różnic!")
            )
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, result)
            dialog.destroy()

        tk.Button(dialog, text="Porównaj", command=compare).pack()

    def _compare_features(self, cechy1, cechy2, all_features):
        """Pomocnicza funkcja do porównywania cech."""
        matches = 0
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
                elif val1 == val2:
                    matches += 1
                else:
                    differences.append(f"{feature}: {val1} vs {val2}")
            else:
                differences.append(f"{feature}: {'Brak' if feature not in cechy1 else cechy1[feature]} vs {'Brak' if feature not in cechy2 else cechy2[feature]}")
        return matches, differences

    def sort_projects_by_similarity(self):
        """Sortuje projekty według podobieństwa do wybranego projektu."""
        if len(self.projects) < 2:
            messagebox.showerror("Błąd", "Potrzebne są co najmniej 2 projekty!")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Sortuj wg podobieństwa")
        tk.Label(dialog, text="Wybierz projekt odniesienia:").pack()
        ref_var = tk.StringVar(value=list(self.projects.keys())[0])
        ttk.Combobox(dialog, textvariable=ref_var, values=list(self.projects.keys())).pack()

        def sort():
            reference_proj = ref_var.get()
            similarities = []
            for proj in self.projects:
                if proj != reference_proj:
                    cechy1, cechy2 = self.projects[reference_proj]["Cechy"], self.projects[proj]["Cechy"]
                    all_features = set(cechy1.keys()).union(cechy2.keys())
                    matches, _ = self._compare_features(cechy1, cechy2, all_features)
                    similarity = (matches / len(all_features)) * 100 if all_features else 0
                    similarities.append((proj, similarity))
            sorted_projects = sorted(similarities, key=itemgetter(1), reverse=True)
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, f"Projekty posortowane wg podobieństwa do {reference_proj} (ID: {self.projects[reference_proj]['ID']}):\n")
            for proj, sim in sorted_projects:
                self.details_text.insert(tk.END, f"{proj} - {self.projects[proj]['Nazwa']} (ID: {self.projects[proj]['ID']}): {sim:.2f}%\n")
            dialog.destroy()

        tk.Button(dialog, text="Sortuj", command=sort).pack()

    def filter_projects(self):
        """Filtruje projekty według kategorii lub cechy i wartości."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Filtruj projekty")
        choice_var = tk.StringVar(value="1")
        tk.Label(dialog, text="Wybierz opcję:").pack()
        tk.Radiobutton(dialog, text="Po kategorii", variable=choice_var, value="1").pack()
        tk.Radiobutton(dialog, text="Po cesze i wartości", variable=choice_var, value="2").pack()

        tk.Label(dialog, text="Kategoria (opcja 1):").pack()
        cat_var = tk.StringVar(value=list(categories.keys())[0])
        ttk.Combobox(dialog, textvariable=cat_var, values=list(categories.keys())).pack()

        tk.Label(dialog, text="Cecha (opcja 2):").pack()
        all_features = {feat for cat in categories.values() for feat in cat}
        feat_var = tk.StringVar(value=list(all_features)[0])
        ttk.Combobox(dialog, textvariable=feat_var, values=list(all_features)).pack()

        tk.Label(dialog, text="Wartość (opcja 2):").pack()
        value_entry = tk.Entry(dialog)
        value_entry.pack()

        def filter():
            filtered = []
            if choice_var.get() == "1":
                category = cat_var.get()
                filtered = [symbol for symbol, details in self.projects.items() if any(feat in categories[category] for feat in details["Cechy"])]
            else:
                feature, value = feat_var.get(), value_entry.get()
                filtered = [symbol for symbol, details in self.projects.items() if feature in details["Cechy"] and details["Cechy"][feature] == value]
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, "Znalezione projekty:\n" if filtered else "Brak projektów spełniających kryteria!\n")
            for symbol in filtered:
                self.details_text.insert(tk.END, f"{symbol} - {self.projects[symbol]['Nazwa']} (ID: {self.projects[symbol]['ID']})\n")
            dialog.destroy()

        tk.Button(dialog, text="Filtruj", command=filter).pack()

    def export_to_csv(self):
        """Eksportuje projekty do pliku CSV."""
        if not self.projects:
            messagebox.showinfo("Informacja", "Brak projektów do eksportu!")
            return
        output_file = os.path.join(os.path.dirname(__file__), "projects_export.csv")
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Symbol", "Nazwa", "ID", "Cecha", "Wartość"])
            for symbol, details in self.projects.items():
                for feature, value in details["Cechy"].items():
                    writer.writerow([symbol, details["Nazwa"], details["ID"], feature, value])
        messagebox.showinfo("Sukces", f"Wyniki wyeksportowano do: {output_file}")

    def search_projects(self):
        """Wyszukuje projekty na podstawie frazy."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Wyszukaj projekty")
        tk.Label(dialog, text="Fraza wyszukiwania:").pack()
        search_entry = tk.Entry(dialog)
        search_entry.pack()

        def search():
            search_term = search_entry.get().lower()
            found = [
                symbol for symbol, details in self.projects.items()
                if search_term in details["Nazwa"].lower() or
                   any(search_term in str(value).lower() for value in details["Cechy"].values())
            ]
            self.details_text.delete(1.0, tk.END)
            self.details_text.insert(tk.END, "Znalezione projekty:\n" if found else "Nie znaleziono projektów!\n")
            for symbol in found:
                self.details_text.insert(tk.END, f"{symbol} - {self.projects[symbol]['Nazwa']} (ID: {self.projects[symbol]['ID']})\n")
            dialog.destroy()

        tk.Button(dialog, text="Szukaj", command=search).pack()

    def clear_details(self):
        """Czyści zawartość pola tekstowego z wynikami."""
        self.details_text.delete(1.0, tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1800x800")
    app = ProjectApp(root)
    root.mainloop()