import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional, Union, Tuple, Any
import os

from notebooks.utils.scenario_data import ScenarioData


class ScenarioPlotter:
    """Klasse zum Visualisieren von Szenariodaten."""
    
    def __init__(self, style: str = "seaborn-v0_8-talk"):
        """
        Initialisiert den Plotter mit einem Plotting-Stil.
        
        Args:
            style: Matplotlib-Stil für die Plots
        """
        self.style = style
        plt.style.use(self.style)
        
    def plot_timeseries(self, 
                        scenario: ScenarioData, 
                        columns: Union[str, List[str]],
                        figsize: Tuple[int, int] = (6.4, 4),
                        title: Optional[str] = None,
                        ylabel: Optional[str] = None,
                        resample: Optional[str] = None,
                        save_path: Optional[str] = None) -> plt.Figure:
        """
        Erzeugt einen Zeitreihenplot für ausgewählte Spalten.
        
        Args:
            scenario: ScenarioData-Objekt mit Daten
            columns: Spalte(n) zum Plotten
            figsize: Abmessungen der Abbildung (Breite, Höhe)
            title: Titel des Plots
            ylabel: Beschriftung der Y-Achse
            resample: Optional Resampling-Frequenz (z.B. 'D' für täglich, 'M' für monatlich)
            save_path: Pfad zum Speichern der Abbildung
            
        Returns:
            matplotlib.figure.Figure: Die erstellte Abbildung
        """
        if scenario.processed_output is None:
            raise ValueError("Keine vorverarbeiteten Daten vorhanden. Bitte zuerst preprocess() aufrufen.")
        
        df = scenario.processed_output
        
        # Überprüfe, ob ein Datetime-Index vorhanden ist
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame hat keinen Datetime-Index. Bitte zuerst add_datetime() aufrufen.")
        
        # Resampling für größere Datensätze
        if resample:
            df = df.resample(resample).mean()
        
        # Konvertiere columns zu Liste, wenn es ein String ist
        if isinstance(columns, str):
            columns = [columns]
        
        # Prüfe, ob alle Spalten existieren
        non_existent = [col for col in columns if col not in df.columns]
        if non_existent:
            raise ValueError(f"Spalten nicht gefunden: {', '.join(non_existent)}")
        
        # Figur erstellen
        fig, ax = plt.subplots(figsize=figsize)
        
        # Alle Spalten plotten
        for column in columns:
            ax.plot(df.index, df[column], label=column)
        
        # Beschriftungen und Anpassungen
        ax.set_xlabel('Zeit')
        ax.set_ylabel(ylabel or columns[0] if len(columns) == 1 else ylabel or 'Wert')
        ax.set_title(title or f"Zeitreihe für {scenario.scenario_name}")
        
        if len(columns) > 1:
            ax.legend()
            
        ax.grid(True)
        plt.tight_layout()
        
        # Speichern, falls Pfad angegeben
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig
    
    def plot_costs(self, 
                  scenario: ScenarioData, 
                  figsize: Tuple[int, int] = (16, 9),
                  title: Optional[str] = None,
                  save_path: Optional[str] = None) -> plt.Figure:
        """
        Erzeugt ein Balkendiagramm mit Kostenkomponenten.
        
        Args:
            scenario: ScenarioData-Objekt mit Kostendaten
            figsize: Abmessungen der Abbildung (Breite, Höhe)
            title: Titel des Plots
            save_path: Pfad zum Speichern der Abbildung
            
        Returns:
            matplotlib.figure.Figure: Die erstellte Abbildung
        """
        if scenario.costs is None:
            raise ValueError("Keine Kostendaten vorhanden. Bitte zuerst load_costs() aufrufen.")
        
        # Kostenwerte filtern (nur numerische Werte behalten)
        costs_data = {k: v for k, v in scenario.costs.items() 
                     if isinstance(v, (int, float))}
        
        # Figur erstellen
        fig, ax = plt.subplots(figsize=figsize)
        
        # Balkendiagramm
        bars = ax.bar(costs_data.keys(), costs_data.values())
        
        # Werte über den Balken anzeigen
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}',
                   ha='center', va='bottom', rotation=0)
        
        # Beschriftungen und Anpassungen
        ax.set_xlabel('Kostenkomponente')
        ax.set_ylabel('Wert')
        ax.set_title(title or f"Kosten für {scenario.scenario_name}")
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        # Speichern, falls Pfad angegeben
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig
    
    def plot_daily_profile(self, 
                           scenario: ScenarioData, 
                           column: str,
                           by_month: bool = False,
                           figsize: Tuple[int, int] = (6.4, 4),
                           title: Optional[str] = None,
                           save_path: Optional[str] = None) -> plt.Figure:
        """
        Erzeugt ein Tagesprofil für eine ausgewählte Spalte.
        
        Args:
            scenario: ScenarioData-Objekt mit Daten
            column: Spalte zum Plotten
            by_month: Falls True, werden Profile nach Monaten aufgeteilt
            figsize: Abmessungen der Abbildung (Breite, Höhe)
            title: Titel des Plots
            save_path: Pfad zum Speichern der Abbildung
            
        Returns:
            matplotlib.figure.Figure: Die erstellte Abbildung
        """
        if scenario.processed_output is None:
            raise ValueError("Keine vorverarbeiteten Daten vorhanden. Bitte zuerst preprocess() aufrufen.")
        
        df = scenario.processed_output
        
        # Überprüfe, ob ein Datetime-Index vorhanden ist
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame hat keinen Datetime-Index. Bitte zuerst add_datetime() aufrufen.")
        
        # Überprüfe, ob die Spalte existiert
        if column not in df.columns:
            raise ValueError(f"Spalte '{column}' nicht gefunden.")
        
        # Figur erstellen
        fig, ax = plt.subplots(figsize=figsize)
        
        if by_month:
            # Daten nach Monaten und Stunden aggregieren
            monthly_profiles = df.groupby([df.index.month, df.index.hour])[column].mean().unstack(0)
            # Monate benennen
            month_names = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']
            monthly_profiles.columns = [month_names[m-1] for m in monthly_profiles.columns]
            
            # Plotten
            monthly_profiles.plot(ax=ax)
            ax.set_title(title or f"Monatliche Tagesprofile für {column}")
            ax.set_xlabel('Stunde des Tages')
            ax.set_ylabel(column)
            ax.set_xticks(range(0, 24, 2))
            ax.legend(title='Monat')
        else:
            # Daten nach Stunden aggregieren
            daily_profile = df.groupby(df.index.hour)[column].mean()
            
            # Plotten
            ax.plot(daily_profile.index, daily_profile.values, marker='o')
            ax.set_title(title or f"Durchschnittliches Tagesprofil für {column}")
            ax.set_xlabel('Stunde des Tages')
            ax.set_ylabel(column)
            ax.set_xticks(range(0, 24, 2))
            ax.grid(True)
        
        plt.tight_layout()
        
        # Speichern, falls Pfad angegeben
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig
    
    def plot_heatmap(self, 
                    scenario: ScenarioData, 
                    column: str,
                    figsize: Tuple[int, int] = (6.4, 4),
                    title: Optional[str] = None,
                    cmap: str = 'viridis',
                    save_path: Optional[str] = None) -> plt.Figure:
        """
        Erzeugt eine Heatmap nach Stunden und Tagen für eine ausgewählte Spalte.
        
        Args:
            scenario: ScenarioData-Objekt mit Daten
            column: Spalte zum Plotten
            figsize: Abmessungen der Abbildung (Breite, Höhe)
            title: Titel des Plots
            cmap: Farbschema für die Heatmap
            save_path: Pfad zum Speichern der Abbildung
            
        Returns:
            matplotlib.figure.Figure: Die erstellte Abbildung
        """
        if scenario.processed_output is None:
            raise ValueError("Keine vorverarbeiteten Daten vorhanden. Bitte zuerst preprocess() aufrufen.")
        
        df = scenario.processed_output
        
        # Überprüfe, ob ein Datetime-Index vorhanden ist
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame hat keinen Datetime-Index. Bitte zuerst add_datetime() aufrufen.")
        
        # Überprüfe, ob die Spalte existiert
        if column not in df.columns:
            raise ValueError(f"Spalte '{column}' nicht gefunden.")
        
        # Daten für Heatmap vorbereiten
        # Pivot-Tabelle mit Stunden als Spalten und Tagen als Zeilen
        pivot_data = df.pivot_table(
            values=column,
            index=df.index.strftime('%m-%d'),  # Tag des Jahres als Index
            columns=df.index.hour,  # Stunde als Spalte
            aggfunc='mean'
        )
        
        # Figur erstellen
        fig, ax = plt.subplots(figsize=figsize)
        
        # Heatmap zeichnen
        sns.heatmap(pivot_data, cmap=cmap, ax=ax, cbar_kws={'label': column})
        
        # Beschriftungen und Anpassungen
        ax.set_title(title or f"Heatmap für {column}")
        ax.set_xlabel('Stunde des Tages')
        ax.set_ylabel('Tag des Jahres')
        
        # X-Achse anpassen
        ax.set_xticks(range(0, 24, 2))  # Nur jede zweite Stunde anzeigen
        
        # Y-Achse anpassen (nur jeden x-ten Tag anzeigen)
        n_days = len(pivot_data)
        step = max(1, n_days // 12)  # Maximal 12 Tage anzeigen
        ax.set_yticks(range(0, n_days, step))
        
        plt.tight_layout()
        
        # Speichern, falls Pfad angegeben
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig


class ComparisonPlotter:
    """Klasse zum Vergleichen und Visualisieren mehrerer Szenarien."""
    
    def __init__(self, style: str = "seaborn-v0_8-whitegrid"):
        """
        Initialisiert den Plotter mit einem Plotting-Stil.
        
        Args:
            style: Matplotlib-Stil für die Plots
        """
        self.style = style
        plt.style.use(self.style)
    
    def compare_timeseries(self, 
                          scenarios: Dict[str, ScenarioData], 
                          column: str,
                          figsize: Tuple[int, int] = (6.4, 4),
                          title: Optional[str] = None,
                          ylabel: Optional[str] = None,
                          resample: Optional[str] = None,
                          save_path: Optional[str] = None) -> plt.Figure:
        """
        Vergleicht eine Spalte über mehrere Szenarien hinweg.
        
        Args:
            scenarios: Dictionary mit Szenarioname als Schlüssel und ScenarioData als Wert
            column: Spalte zum Vergleichen
            figsize: Abmessungen der Abbildung (Breite, Höhe)
            title: Titel des Plots
            ylabel: Beschriftung der Y-Achse
            resample: Optional Resampling-Frequenz (z.B. 'D' für täglich, 'M' für monatlich)
            save_path: Pfad zum Speichern der Abbildung
            
        Returns:
            matplotlib.figure.Figure: Die erstellte Abbildung
        """
        # Figur erstellen
        fig, ax = plt.subplots(figsize=figsize)
        
        # Für jedes Szenario plotten
        for name, scenario in scenarios.items():
            if scenario.processed_output is None:
                print(f"Warnung: Szenario {name} hat keine verarbeiteten Daten. Überspringe.")
                continue
            
            df = scenario.processed_output
            
            # Überprüfe, ob ein Datetime-Index vorhanden ist
            if not isinstance(df.index, pd.DatetimeIndex):
                print(f"Warnung: Szenario {name} hat keinen Datetime-Index. Überspringe.")
                continue
            
            # Überprüfe, ob die Spalte existiert
            if column not in df.columns:
                print(f"Warnung: Spalte '{column}' nicht in Szenario {name} gefunden. Überspringe.")
                continue
            
            # Resampling für größere Datensätze
            if resample:
                df = df.resample(resample).mean()
            
            # Plotten
            ax.plot(df.index, df[column], label=name)
        
        # Beschriftungen und Anpassungen
        ax.set_xlabel('Zeit')
        ax.set_ylabel(ylabel or column)
        ax.set_title(title or f"Vergleich von {column} zwischen Szenarien")
        ax.legend()
        ax.grid(True)
        plt.tight_layout()
        
        # Speichern, falls Pfad angegeben
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig
    
    def compare_costs(self, 
                     scenarios: Dict[str, ScenarioData], 
                     costs_to_include: Optional[List[str]] = None,
                     figsize: Tuple[int, int] = (12, 8),
                     title: Optional[str] = None,
                     as_stacked: bool = False,
                     save_path: Optional[str] = None) -> plt.Figure:
        """
        Vergleicht Kosten über mehrere Szenarien hinweg.
        
        Args:
            scenarios: Dictionary mit Szenarioname als Schlüssel und ScenarioData als Wert
            costs_to_include: Liste der zu inkludierenden Kostenkomponenten (None = alle)
            figsize: Abmessungen der Abbildung (Breite, Höhe)
            title: Titel des Plots
            as_stacked: Falls True, werden gestapelte Balken erzeugt
            save_path: Pfad zum Speichern der Abbildung
            
        Returns:
            matplotlib.figure.Figure: Die erstellte Abbildung
        """
        # Sammle Kostendaten von allen Szenarien
        all_costs = {}
        
        for name, scenario in scenarios.items():
            if scenario.costs is None:
                print(f"Warnung: Szenario {name} hat keine Kostendaten. Überspringe.")
                continue
                
            # Numerische Werte extrahieren
            costs_data = {k: v for k, v in scenario.costs.items() 
                         if isinstance(v, (int, float))}
            
            # Nur ausgewählte Kostenkomponenten behalten, falls angegeben
            if costs_to_include:
                costs_data = {k: v for k, v in costs_data.items() if k in costs_to_include}
                
            all_costs[name] = costs_data
        
        if not all_costs:
            raise ValueError("Keine gültigen Kostendaten gefunden.")
        
        # Alle eindeutigen Kostenkomponenten sammeln
        all_cost_keys = set()
        for costs in all_costs.values():
            all_cost_keys.update(costs.keys())
        
        # DataFrame für den Vergleich erstellen
        cost_df = pd.DataFrame(index=all_cost_keys, columns=all_costs.keys())
        
        for scenario_name, costs in all_costs.items():
            for cost_key, value in costs.items():
                cost_df.loc[cost_key, scenario_name] = value
        
        # NaN-Werte mit 0 füllen
        cost_df = cost_df.fillna(0)
        
        # Figur erstellen
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plotten
        if as_stacked:
            cost_df.T.plot(kind='bar', stacked=True, ax=ax)
            ax.set_xlabel('Szenario')
            ax.set_ylabel('Gesamtkosten')
        else:
            cost_df.plot(kind='bar', ax=ax)
            ax.set_xlabel('Kostenkomponente')
            ax.set_ylabel('Wert')
        
        ax.set_title(title or "Kostenvergleich zwischen Szenarien")
        plt.legend(title='Komponente' if as_stacked else 'Szenario')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        # Speichern, falls Pfad angegeben
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig
    
    def compare_daily_profiles(self, 
                              scenarios: Dict[str, ScenarioData], 
                              column: str,
                              figsize: Tuple[int, int] = (6.4, 4),
                              title: Optional[str] = None,
                              save_path: Optional[str] = None) -> plt.Figure:
        """
        Vergleicht Tagesprofile einer Spalte über mehrere Szenarien hinweg.
        
        Args:
            scenarios: Dictionary mit Szenarioname als Schlüssel und ScenarioData als Wert
            column: Spalte zum Vergleichen
            figsize: Abmessungen der Abbildung (Breite, Höhe)
            title: Titel des Plots
            save_path: Pfad zum Speichern der Abbildung
            
        Returns:
            matplotlib.figure.Figure: Die erstellte Abbildung
        """
        # Figur erstellen
        fig, ax = plt.subplots(figsize=figsize)
        
        # Für jedes Szenario plotten
        for name, scenario in scenarios.items():
            if scenario.processed_output is None:
                print(f"Warnung: Szenario {name} hat keine verarbeiteten Daten. Überspringe.")
                continue
                
            df = scenario.processed_output
            
            # Überprüfe, ob ein Datetime-Index vorhanden ist
            if not isinstance(df.index, pd.DatetimeIndex):
                print(f"Warnung: Szenario {name} hat keinen Datetime-Index. Überspringe.")
                continue
                
            # Überprüfe, ob die Spalte existiert
            if column not in df.columns:
                print(f"Warnung: Spalte '{column}' nicht in Szenario {name} gefunden. Überspringe.")
                continue
                
            # Daten nach Stunden aggregieren
            daily_profile = df.groupby(df.index.hour)[column].mean()
            
            # Plotten
            ax.plot(daily_profile.index, daily_profile.values, marker='o', label=name)
        
        # Beschriftungen und Anpassungen
        ax.set_title(title or f"Vergleich der Tagesprofile für {column}")
        ax.set_xlabel('Stunde des Tages')
        ax.set_ylabel(column)
        ax.set_xticks(range(0, 24, 2))
        ax.legend()
        ax.grid(True)
        plt.tight_layout()
        
        # Speichern, falls Pfad angegeben
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        
        return fig