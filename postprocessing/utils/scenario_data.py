import pandas as pd
import json
import os
import glob
import datetime as dt
import re
from typing import Dict, Any, List, Optional, Union

class ScenarioData:
    """Klasse zur Verwaltung von Szenariodaten aus verschiedenen Dateien."""
    
    def __init__(self, scenario_name: str, base_path: str):
        """
        Initialisiert ein Szenariodatenobjekt.
        
        Args:
            scenario_name: Name des Szenarios
            base_path: Basispfad zum Szenarioverzeichnis
        """
        self.scenario_name = scenario_name
        self.base_path = base_path
        self.scenario_path = os.path.join(base_path, scenario_name)
        
        # Datenspeicher
        self.costs: Optional[Dict[str, Any]] = None
        self.metadata: Optional[Dict[str, Any]] = None
        self.output: Optional[pd.DataFrame] = None
        self.processed_output: Optional[pd.DataFrame] = None
        
        # Dateipfade
        self._find_files()
    
    def _find_files(self) -> None:
        """Identifiziert alle relevanten Dateien im Szenariopfad."""
        if not os.path.exists(self.scenario_path):
            raise FileNotFoundError(f"Szenariopfad {self.scenario_path} existiert nicht.")
        
        self.output_files = glob.glob(os.path.join(self.scenario_path, '*_output.csv'))
        self.costs_files = glob.glob(os.path.join(self.scenario_path, '*_costs.json'))
        self.metadata_files = glob.glob(os.path.join(self.scenario_path, '*_metadata.json'))
    
    def load_all_data(self) -> 'ScenarioData':
        """Lädt alle verfügbaren Daten für das Szenario."""
        self.load_costs()
        self.load_metadata()
        self.load_output()
        return self
    
    def load_costs(self) -> 'ScenarioData':
        """Lädt die Kostendaten aus der JSON-Datei."""
        if self.costs_files:
            # Nehme die neueste Datei
            latest_file = max(self.costs_files, key=os.path.getmtime)
            with open(latest_file, 'r') as f:
                self.costs = json.load(f)
            print(f"Kostendaten aus {os.path.basename(latest_file)} geladen.")
        else:
            print(f"Keine Kostendateien für {self.scenario_name} gefunden.")
        return self
    
    def load_metadata(self) -> 'ScenarioData':
        """Lädt die Metadaten aus der JSON-Datei."""
        if self.metadata_files:
            # Nehme die neueste Datei
            latest_file = max(self.metadata_files, key=os.path.getmtime)
            with open(latest_file, 'r') as f:
                self.metadata = json.load(f)
            print(f"Metadaten aus {os.path.basename(latest_file)} geladen.")
        else:
            print(f"Keine Metadatendateien für {self.scenario_name} gefunden.")
        return self
    
    def load_output(self) -> 'ScenarioData':
        """Lädt die Ausgabedaten aus der CSV-Datei."""
        if self.output_files:
            # Nehme die neueste Datei
            latest_file = max(self.output_files, key=os.path.getmtime)
            self.output = pd.read_csv(latest_file)
            print(f"Ausgabedaten aus {os.path.basename(latest_file)} geladen.")
        else:
            print(f"Keine Ausgabedateien für {self.scenario_name} gefunden.")
        return self
    
    def preprocess(self) -> 'ScenarioData':
        """Verarbeitet die geladenen Daten vor."""
        if self.output is not None:
            # Kopie erstellen, um das Original nicht zu verändern
            df = self.output.copy()
            
            # Fehlende Werte behandeln
            df = df.fillna(0)
            
            # Zeit-Spalten in Datetime konvertieren
            time_columns = [col for col in df.columns if 'time' in col.lower() or 'date' in col.lower()]
            for col in time_columns:
                if df[col].dtype == 'object':
                    df[col] = pd.to_datetime(df[col], errors='ignore')
            
            # Numerische Spalten identifizieren
            numeric_cols = df.select_dtypes(include=['number']).columns
            
            # Optional: Ausreißer behandeln in numerischen Spalten
            for col in numeric_cols:
                # 3 Standardabweichungen als Grenze für Ausreißer
                mean, std = df[col].mean(), df[col].std()
                if std > 0:  # Vermeide Division durch Null
                    df[col] = df[col].clip(lower=mean-3*std, upper=mean+3*std)
            
            # Optional: Zeitreihenindexierung, wenn Zeitstempel vorhanden
            if time_columns and not df[time_columns[0]].isna().any():
                df.set_index(time_columns[0], inplace=True)
            
            self.processed_output = df
            print(f"Daten für {self.scenario_name} vorverarbeitet.")
        else:
            print("Keine Ausgabedaten zum Vorverarbeiten vorhanden. Bitte zuerst load_output() aufrufen.")
        return self
    
    def add_datetime(self, default_year=None, set_as_index=True) -> 'ScenarioData':
        """
        Fügt eine datetime-Spalte basierend auf dem stündlichen Index hinzu.
        Das Jahr wird automatisch aus den Metadaten extrahiert, wenn möglich.
        
        Args:
            default_year (int, optional): Fallback-Jahr, falls Metadaten nicht verfügbar sind
            set_as_index (bool): Wenn True, wird die neue datetime-Spalte als Index gesetzt
            
        Returns:
            ScenarioData: Das aktuelle ScenarioData-Objekt für Method Chaining
        """
     
        
        # Daten vorbereiten, falls nötig
        if self.processed_output is None:
            if self.output is not None:
                self.preprocess()
            else:
                print("Keine Ausgabedaten vorhanden. Bitte zuerst load_output() aufrufen.")
                return self
        
        # Jahr aus Metadaten extrahieren
        year = default_year or 2023  # Fallback-Jahr
        
        if self.metadata and 'config' in self.metadata:
            config_name = self.metadata['config']
            # Regex, um das Jahr zu extrahieren (vier aufeinanderfolgende Ziffern)
            year_match = re.search(r'(\d{4})', config_name)
            if year_match:
                year = int(year_match.group(1))
                print(f"Jahr {year} aus Metadaten extrahiert.")
            else:
                print(f"Kein Jahr in der Konfiguration {config_name} gefunden, verwende {year}.")
        else:
            if default_year:
                print(f"Keine Metadaten verfügbar. Verwende angegebenes Jahr: {default_year}.")
            else:
                print(f"Keine Metadaten verfügbar. Verwende Standardjahr: {year}.")
        
        # Anzahl der Datenpunkte
        num_points = len(self.processed_output)
        
        # Bestimmen, ob es ein Schaltjahr ist
        is_leap_year = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
        expected_hours = 8784 if is_leap_year else 8760
        
        # Warnung, wenn die Datenpunkte nicht mit dem erwarteten Jahr übereinstimmen
        if num_points not in [expected_hours, expected_hours-1, expected_hours+1]:
            print(f"Warnung: Die Anzahl der Datenpunkte ({num_points}) stimmt nicht mit der erwarteten Anzahl für das Jahr {year} ({expected_hours}) überein.")
        
        print(f"Erstelle Zeitstempel für das Jahr {year} ({'Schaltjahr' if is_leap_year else 'Normales Jahr'}).")
        
        # Startdatum: 1. Januar des angegebenen Jahres um 01:00 Uhr
        start_date = dt.datetime(year, 1, 1, 1, 0)
        
        # Erzeuge Zeitstempel für jede Stunde des Jahres (mit 'h' statt 'H')
        hours = pd.date_range(start=start_date, periods=num_points, freq='h')
        
        # Effizienter: Assign verwenden statt direkter Zuweisung
        if set_as_index:
            # Effizienter: Direkt Index setzen
            self.processed_output = self.processed_output.set_index(hours)
            self.processed_output.index.name = 'datetime'
        else:
            # Effizienter: assign verwenden statt direkter Zuweisung
            self.processed_output = self.processed_output.assign(datetime=hours)
        
        print(f"Datetime-Spalte für {self.scenario_name} hinzugefügt.")
        
        return self
    
    
    def summary(self) -> Dict[str, Any]:
        """Erstellt eine Zusammenfassung der Szenariodaten."""
        summary = {
            "scenario_name": self.scenario_name,
            "data_available": {
                "costs": self.costs is not None,
                "metadata": self.metadata is not None,
                "output": self.output is not None,
                "processed": self.processed_output is not None,
            }
        }
        
        if self.metadata:
            summary["scenario_info"] = {
                "hydrogen_admixture_chp1": self.metadata.get("hydrogen_admixture", {}).get("chp_1"),
                "hydrogen_admixture_chp2": self.metadata.get("hydrogen_admixture", {}).get("chp_2"),
            }
            
   
            
        if self.output is not None:
            summary["data_shape"] = {
                "rows": self.output.shape[0],
                "columns": self.output.shape[1]
            }
            
        return summary

class ScenarioCollection:
    """Sammlung mehrerer Szenarien für den Vergleich."""
    
    def __init__(self, base_path: str):
        """
        Initialisiert eine Sammlung von Szenarien.
        
        Args:
            base_path: Basispfad zum Verzeichnis mit den Szenarioverzeichnissen
        """
        self.base_path = base_path
        self.scenarios: Dict[str, ScenarioData] = {}
        
    def discover_scenarios(self) -> 'ScenarioCollection':
        """Findet alle verfügbaren Szenarien im Basispfad."""
        import os
        
        if not os.path.exists(self.base_path):
            raise FileNotFoundError(f"Der Basispfad {self.base_path} existiert nicht.")
        
        # Alle Verzeichnisse im Basispfad als Szenarien betrachten
        scenario_dirs = [d for d in os.listdir(self.base_path) 
                        if os.path.isdir(os.path.join(self.base_path, d))]
        
        print(f"{len(scenario_dirs)} Szenarien gefunden: {scenario_dirs}")
        return self
    
    def load_scenario(self, scenario_name: str) -> 'ScenarioCollection':
        """Lädt ein einzelnes Szenario in die Sammlung."""
        scenario = ScenarioData(scenario_name, self.base_path)
        scenario.load_all_data()
        self.scenarios[scenario_name] = scenario
        return self
    
    def load_scenarios(self, scenario_names: List[str]) -> 'ScenarioCollection':
        """Lädt mehrere Szenarien in die Sammlung."""
        for name in scenario_names:
            self.load_scenario(name)
        return self
    
    def preprocess_all(self) -> 'ScenarioCollection':
        """Verarbeitet alle geladenen Szenarien vor."""
        for scenario in self.scenarios.values():
            scenario.preprocess()
        return self
    
    def add_datetime_all(self, default_year=None, set_as_index=True) -> 'ScenarioCollection':
        """Fügt Datetime-Spalten für alle geladenen Szenarien hinzu."""
        for scenario in self.scenarios.values():
            scenario.add_datetime(default_year=default_year, set_as_index=set_as_index)
        return self
