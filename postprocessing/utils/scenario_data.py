'''
Helper script for postprocessing energy system simulation results.
Contains the Scenario class to access and load data for specific scenarios.
'''
import os
import json
import pandas as pd
import re
import datetime as dt

class Scenario:
    """
    Manages access to data for a specific simulation scenario.
    """
    def __init__(self, base_data_path, use_case, year, h2_pct, co2_multiplier):
        """
        Initializes a Scenario object.

        Args:
            base_data_path (str): The base path to the data output directory.
            use_case (str): The use case identifier ("uc1" or "uc2").
            year (int): The simulation year (e.g., 2030).
            h2_pct (int): The hydrogen percentage (e.g., 0, 30, 50, 100).
            co2_multiplier (bool): False for standard CO2 price (uc1), True for doubled (uc2).
        """
        self.base_data_path = base_data_path
        self.use_case = use_case
        self.year = year # This is the primary year for the scenario
        self.h2_pct = h2_pct
        self.co2_multiplier = co2_multiplier

        if self.use_case == "uc1" and self.co2_multiplier:
            raise ValueError("For use_case 'uc1', co2_multiplier must be False.")
        if self.use_case == "uc2" and not self.co2_multiplier:
            raise ValueError("For use_case 'uc2', co2_multiplier must be True.")

        if self.use_case == "uc1":
            self.scenario_name_identifier = f"uc1_{self.year}_{self.h2_pct}h2"
        elif self.use_case == "uc2":
            self.scenario_name_identifier = f"uc2_{self.year}_{self.h2_pct}h2_2xco2"
        else:
            raise ValueError(f"Unknown use_case: {self.use_case}. Must be 'uc1' or 'uc2'.")

        self.scenario_dir = os.path.join(self.base_data_path, self.use_case, self.scenario_name_identifier)

        self.data_output = None
        self.data_costs = None
        self.data_metadata = None
        self.data_chp_asset = None

    def _find_file(self, suffix_pattern):
        if not os.path.exists(self.scenario_dir):
            abs_path_scenario_dir = os.path.abspath(self.scenario_dir)
            raise FileNotFoundError(
                f"Scenario directory not found: '{self.scenario_dir}' (resolved to '{abs_path_scenario_dir}'). "
                f"Ensure 'base_data_path' ('{self.base_data_path}') is correct and the directory exists."
            )
        if not os.path.isdir(self.scenario_dir):
            abs_path_scenario_dir = os.path.abspath(self.scenario_dir)
            raise NotADirectoryError(
                f"The path '{self.scenario_dir}' (resolved to '{abs_path_scenario_dir}') is not a directory."
            )
        expected_prefix = self.scenario_name_identifier
        found_files = [os.path.join(self.scenario_dir, fname) for fname in os.listdir(self.scenario_dir)
                       if fname.startswith(expected_prefix) and fname.endswith(suffix_pattern)]
        if not found_files:
            raise FileNotFoundError(
                f"No file starting with '{expected_prefix}' and ending with '{suffix_pattern}' "
                f"found in directory '{self.scenario_dir}'. Check filenames and timestamps."
            )
        return found_files[0]

    def load_output_data(self, set_datetime_index=True):
        """
        Loads the time series output CSV file, adds a datetime index, and stores it.
        The year for the datetime index is determined from metadata if available,
        otherwise from the scenario's year attribute.
        
        Args:
            set_datetime_index (bool): If True, sets the datetime column as index.
                                       If False, adds 'datetime' as a column.
                                       (This argument is for potential future flexibility,
                                        current primary use case sets it as index).
        Returns:
            pd.DataFrame: The output data with a datetime index or column.
        """
        if self.data_output is not None:
            # Check if datetime processing was already done according to set_datetime_index
            if set_datetime_index and isinstance(self.data_output.index, pd.DatetimeIndex):
                return self.data_output
            if not set_datetime_index and 'datetime' in self.data_output.columns:
                 return self.data_output
            # If not, it means data was cached but not processed as requested, so re-process
            # This case is less likely if load_output_data is the only entry point for self.data_output modification

        csv_file_path = self._find_file("_output.csv")
        loaded_df = pd.read_csv(csv_file_path)

        # --- Start of integrated datetime logic ---
        # Ensure metadata is loaded for year extraction
        if self.data_metadata is None:
            try:
                self.load_metadata()
            except FileNotFoundError:
                print("Metadata file not found for year extraction. Will use scenario year.")
            except Exception as e:
                print(f"Error loading metadata for year extraction: {e}. Will use scenario year.")


        year_to_use = self.year # Default to scenario's year
        extracted_year_from_meta = None

        if self.data_metadata and 'config' in self.data_metadata:
            config_name = self.data_metadata['config']
            year_match = re.search(r'(\d{4})', config_name)
            if year_match:
                extracted_year_from_meta = int(year_match.group(1))
                print(f"Jahr {extracted_year_from_meta} aus Metadaten ('config': '{config_name}') für Datetime-Index extrahiert.")
                if extracted_year_from_meta != self.year:
                    print(f"WARNUNG: Jahr aus Metadaten ({extracted_year_from_meta}) weicht vom Szenario-Jahr ({self.year}) ab. Verwende Jahr aus Metadaten für Zeitstempel.")
                year_to_use = extracted_year_from_meta
            else:
                print(f"Kein Jahr in Metadaten-Konfiguration '{config_name}' gefunden. Verwende Szenario-Jahr {self.year} für Zeitstempel.")
        else:
            print(f"Keine Metadaten für Jahr-Extraktion verfügbar oder 'config'-Schlüssel fehlt. Verwende Szenario-Jahr {self.year} für Zeitstempel.")

        num_points = len(loaded_df)
        is_leap_year = (year_to_use % 4 == 0 and year_to_use % 100 != 0) or (year_to_use % 400 == 0)
        expected_hours = 8784 if is_leap_year else 8760

        if num_points != expected_hours:
            print(f"WARNUNG: Anzahl Datenpunkte ({num_points}) für {self.scenario_name_identifier} stimmt nicht mit erwarteten Stunden für {year_to_use} ({expected_hours}) überein.")
        print(f"Erstelle Zeitstempel für {self.scenario_name_identifier}, Jahr {year_to_use} ({'Schaltjahr' if is_leap_year else 'Normales Jahr'}).")

        
        start_datetime = dt.datetime(year_to_use, 1, 1, 0, 0) # Start at 00:00
        
        # Create datetime series
        # If num_points is 8761 (e.g. from oemof results ending at hour 1 of next year for a full year)
        # and expected_hours is 8760, we might want to trim the last point or adjust periods.   
        # For now, using num_points directly.
        hours_index = pd.date_range(start=start_datetime, periods=num_points, freq='h')

        if len(hours_index) > len(loaded_df): # e.g. if num_points was 8761 and freq='h' created 8761 periods
            hours_index = hours_index[:-1] # common fix for oemof results that include hour 0 of next year
            print(f"Angepasste Länge des DatetimeIndex von {len(hours_index)+1} auf {len(hours_index)} um mit Datenlänge {len(loaded_df)} übereinzustimmen.")


        if set_datetime_index:
            if len(hours_index) == len(loaded_df):
                loaded_df = loaded_df.set_index(hours_index)
                loaded_df.index.name = 'datetime'
                print(f"Datetime-Index für {self.scenario_name_identifier} gesetzt.")
            else:
                print(f"FEHLER: Länge des generierten DatetimeIndex ({len(hours_index)}) stimmt nicht mit Datenlänge ({len(loaded_df)}) überein. Index nicht gesetzt.")
        else:
            if len(hours_index) == len(loaded_df):
                loaded_df = loaded_df.assign(datetime=hours_index)
                print(f"Datetime-Spalte für {self.scenario_name_identifier} hinzugefügt.")
            else:
                print(f"FEHLER: Länge der generierten Datetime-Spalte ({len(hours_index)}) stimmt nicht mit Datenlänge ({len(loaded_df)}) überein. Spalte nicht hinzugefügt.")
        # --- End of integrated datetime logic ---

        self.data_output = loaded_df # Cache the processed DataFrame
        return self.data_output

    def load_costs_data(self):
        if self.data_costs is None:
            json_costs_path = self._find_file("_costs.json")
            with open(json_costs_path, 'r', encoding='utf-8') as f:
                self.data_costs = json.load(f)
        return self.data_costs

    def load_metadata(self):
        if self.data_metadata is None:
            json_metadata_path = self._find_file("_metadata.json")
            with open(json_metadata_path, 'r', encoding='utf-8') as f:
                self.data_metadata = json.load(f)
        return self.data_metadata

    def load_chp_asset_data(self):
        if self.data_chp_asset is None:
            chp_asset_filename = f"chp_h2_{self.h2_pct}.csv" if self.h2_pct > 0 else "chp.csv"
            # Construct path relative to this script file or a known base for input data
            # Assuming 'data/input/assets' is two levels up from 'postprocessing/utils' and then down
            script_dir = os.path.dirname(os.path.abspath(__file__)) # postprocessing/utils
            input_assets_dir = os.path.abspath(os.path.join(script_dir, "..", "..", "data", "input", "assets"))
            chp_asset_filepath = os.path.join(input_assets_dir, chp_asset_filename)

            if not os.path.exists(chp_asset_filepath):
                # Fallback for old naming or if base_data_path was meant to be more general
                assets_dir_fallback = os.path.abspath(os.path.join(self.base_data_path, "..", "..", "data", "input", "assets"))
                chp_asset_filepath_fallback = os.path.join(assets_dir_fallback, chp_asset_filename)
                if os.path.exists(chp_asset_filepath_fallback):
                    chp_asset_filepath = chp_asset_filepath_fallback
                else:
                    raise FileNotFoundError(
                        f"CHP asset data file not found at '{chp_asset_filepath}' or '{chp_asset_filepath_fallback}'. "
                        f"Ensure the file exists for H2 percentage {self.h2_pct}."
                    )
            try:
                self.data_chp_asset = pd.read_csv(chp_asset_filepath, index_col='index')
            except Exception as e:
                raise Exception(f"Error loading CHP asset data from '{chp_asset_filepath}': {e}")
        return self.data_chp_asset

    def load_all_data(self):
        return {
            "output": self.load_output_data(),
            "costs": self.load_costs_data(),
            "metadata": self.load_metadata(),
            "chp_asset": self.load_chp_asset_data()
        }

    def __repr__(self):
        return (f"<Scenario: {self.scenario_name_identifier} ( "
                f"use_case='{self.use_case}', year={self.year}, "
                f"h2_pct={self.h2_pct}, co2_multiplier={self.co2_multiplier})>")