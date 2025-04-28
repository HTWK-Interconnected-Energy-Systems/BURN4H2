"""Main script for the optimization of the energy system."""

# Import default libraries
import pandas as pd
import json
import os
import glob
import sys
import argparse
from datetime import datetime

# Import external libraries
from pyomo.opt import SolverFactory
from pyomo.environ import (
    AbstractModel,
    DataPortal,
    Set,
    Param,
    Objective,
    Var,
    Expression,
    quicksum,
    value,
    minimize,
    TransformationFactory,
)
from pyomo.network import Arc

# import internal modules 
from burn4h2.blocks import chp, grid, storage, res
import burn4h2.blocks.heatpump as hp
import burn4h2.blocks.collector as st

# Path
PATH_IN = "data/input/"
PATH_OUT = "data/output/"
PATH_CONFIG = "config/"

# Config files
AVAILABLE_CONFIGS = [os.path.basename(f) for f in glob.glob(os.path.join(PATH_CONFIG + 'templates/', "*.json"))]
# print(f"Available config files: {AVAILABLE_CONFIGS}")

class Model:
    """Main class for the creation of the optimization model."""

    def __init__(self, config_file: str) -> None:
        self.model = AbstractModel()
        self.instance = None
        self.solver = None
        self.timeseries_data = None
        self.results = None
        self.result_data = None
        self.config_file = config_file
        self.timestamp = None 

    def set_solver(self, solver_name, **kwargs):
        """Declare solver and solver options."""
        self.solver = SolverFactory(solver_name)

        for key in kwargs:
            self.solver.options[key] = kwargs[key]

    def load_timeseries_data(self):
        """Declare timeseries data for the optimization model."""
        self.data_portal = DataPortal()

        # Load global data
        self.data_portal.load(filename = PATH_CONFIG + 'global.json')
        
        # Load config
        with open(PATH_CONFIG + 'templates/' + self.config_file, "r") as f:
            config = json.load(f)

        # Load timeseries data from config
        for param_name, param_config in config.get("timeseries", {}).items():
            self.data_portal.load(
                filename=PATH_IN + param_config["file"],
                index=param_config["index"],
                param=param_config["param"]
        )
            
         # Load scalar parameters
        for param_name, param_value in config.get("parameters", {}).items():
            # For scalar parameters, use a dictionary with None as key
            self.data_portal.data()[param_name] = {None: param_value}
        

    def add_components(self):
        """Adds pyomo component to the model."""
        # Define sets
        self.model.t = Set(ordered=True)
        
        # Define indexed parameters
        self.model.gas_price = Param(self.model.t)
        self.model.power_price = Param(self.model.t)
        self.model.hydrogen_price = Param(self.model.t)
        self.model.heat_demand = Param(self.model.t)
        self.model.local_heat_demand = Param(self.model.t)
        self.model.supply_temperature = Param(self.model.t)
        self.model.return_temperature = Param(self.model.t)
        self.model.solar_thermal_heat_profile = Param(self.model.t)
        self.model.normalized_solar_thermal_heat_profile = Param(self.model.t)
        self.model.normalized_pv_profile = Param(self.model.t)


        # Define non-indexed parameters
        self.model.CO2_PRICE = Param()
        self.model.HEAT_PRICE = Param()
        self.model.H2_PRICE = Param()
        self.model.USE_CONST_H2_PRICE = Param()
        self.model.INSTALLED_ST_POWER = Param()
        self.model.HYDROGEN_ADMIXTURE_CHP_1 = Param()
        self.model.HYDROGEN_ADMIXTURE_CHP_2 = Param()

        # Erlaubte hydrogen_admixture Werte
        ALLOWED_ADMIXTURE_VALUES = [0, 0.3, 0.5, 1.0]
        
        # Konvertiere Pyomo-Parameter in konkrete Werte
        # Verwende die Werte aus der Konfiguration, da die Pyomo-Parameter noch nicht instanziiert sind
        with open(PATH_CONFIG + 'templates/' + self.config_file, "r") as f:
            config = json.load(f)
        
        h2_admixture_chp_1 = config.get("parameters", {}).get("HYDROGEN_ADMIXTURE_CHP_1", 0)
        h2_admixture_chp_2 = config.get("parameters", {}).get("HYDROGEN_ADMIXTURE_CHP_2", 0)
        
        # Validiere die Werte
        if h2_admixture_chp_1 not in ALLOWED_ADMIXTURE_VALUES:
            raise ValueError(f"Invalid hydrogen_admixture value for CHP_1: {h2_admixture_chp_1}. "
                            f"Allowed values are: {ALLOWED_ADMIXTURE_VALUES}")
        if h2_admixture_chp_2 not in ALLOWED_ADMIXTURE_VALUES:
            raise ValueError(f"Invalid hydrogen_admixture value for CHP_2: {h2_admixture_chp_2}. "
                            f"Allowed values are: {ALLOWED_ADMIXTURE_VALUES}")
        
        # Bestimme die entsprechenden CSV-Dateien
        def get_chp_csv_path(h2_value):
            """Bestimmt den Pfad zur CHP-CSV-Datei basierend auf dem hydrogen_admixture_factor."""
            if h2_value == 0:
                return PATH_IN + "assets/chp.csv"  # Standarddatei für 0% H2
            else:
                # Prozentsatz für Dateinamen (30, 50, 100)
                h2_percent = int(h2_value * 100)
                specific_file = PATH_IN + f"assets/chp_h2_{h2_percent}.csv"
                
                # Prüfe, ob die spezifische Datei existiert
                if os.path.exists(specific_file):
                    return specific_file
                else:
                    print(f"Warning: Specific data file for {h2_percent}% hydrogen not found. Using default.")
                    return PATH_IN + "assets/chp.csv"
        
        # Hole die Dateipfade für die jeweiligen H2-Beimischungen
        chp1_filepath = get_chp_csv_path(h2_admixture_chp_1)
        chp2_filepath = get_chp_csv_path(h2_admixture_chp_2)
        
        print(f"Using CHP 1 data file: {chp1_filepath} with {h2_admixture_chp_1*100}% hydrogen admixture")
        print(f"Using CHP 2 data file: {chp2_filepath} with {h2_admixture_chp_2*100}% hydrogen admixture")


        # Define block components
        chp1 = chp.Chp(
            "chp_1", 
            chp1_filepath,
            hydrogen_admixture=self.model.HYDROGEN_ADMIXTURE_CHP_1
        )
        chp2 = chp.Chp(
            "chp_2", 
            chp2_filepath,
            hydrogen_admixture=self.model.HYDROGEN_ADMIXTURE_CHP_2
        )
        h2_grid = grid.HydrogenGrid(
            "hydrogen_grid"
        )
        n_grid = grid.NGasGrid(
            "ngas_grid"
        )
        wh_grid = grid.WasteHeatGrid(
            "waste_heat_grid", 
            PATH_IN + "assets/waste_heat_grid.csv"
        )
        lh_grid = grid.LocalHeatGrid(
            "local_heat_grid", 
            PATH_IN + "assets/local_heat_grid.csv"
        )
        e_grid = grid.ElectricalGrid(
            "electrical_grid", 
            PATH_IN + "assets/electrical_grid.csv"
        )
        h_grid = grid.HeatGrid(
            "heat_grid",
            PATH_IN + "assets/heat_grid.csv"
        )
        b_storage = storage.BatteryStorage(
            "battery_storage",
            PATH_IN + "assets/battery_storage.csv"
        )
        h_storage = storage.HeatStorage(
            "heat_storage",
            PATH_IN + "assets/heat_storage.csv"
        )
        pv = res.Photovoltaics(
            "pv",
            PATH_IN + "assets/pv.csv",
            PATH_IN + "pv_capacity_factors/leipzig_t45_a180.csv",
        )
        solar_thermal = st.Collector(
            "solar_thermal",
            # PATH_IN + 'profiles/ST Süd_max/max_solarthermal_profil_2028.csv' # Not necessary anymore
            PATH_IN + 'profiles/dummy/dummy_solarthermal_profil.csv' # Not necessary anymore
        )
        hp_s1 = hp.HeatpumpStageOne(
            "heatpump_s1", 
            PATH_IN + "assets/heatpump.csv"
        )
        hp_s2 = hp.HeatpumpStageTwo(
            "heatpump_s2", 
            PATH_IN + "assets/heatpump.csv"
        )
        gh_storage = storage.GeoHeatStorage(
            "geo_heat_storage", 
            PATH_IN + "assets/geo_heat_storage.csv"
        )
        sh_storage = storage.StratifiedHeatStorage(
            "stratified_storage",
            PATH_IN + "assets/stratified_storage.csv",
            seasonal_discharge_restriction=True,
        )


        chp1.add_to_model(self.model)
        chp2.add_to_model(self.model)
        e_grid.add_to_model(self.model)
        h2_grid.add_to_model(self.model)
        wh_grid.add_to_model(self.model)
        lh_grid.add_to_model(self.model)
        n_grid.add_to_model(self.model)
        h_grid.add_to_model(self.model)
        b_storage.add_to_model(self.model)
        h_storage.add_to_model(self.model)
        pv.add_to_model(self.model)
        solar_thermal.add_to_model(self.model)
        hp_s1.add_to_model(self.model)
        hp_s2.add_to_model(self.model)
        gh_storage.add_to_model(self.model)
        sh_storage.add_to_model(self.model)


    def add_objective(self):
        """Adds the objective to the abstract model."""
        self.model.objective = Objective(rule=self.obj_expression, sense=minimize)

    def instantiate(self):
        """Creates a concrete model from the abstract model."""
        self.instance = self.model.create_instance(self.data_portal)

    def expand_arcs(self):
        """Expands arcs and generate connection constraints."""
        TransformationFactory("network.expand_arcs").apply_to(self.instance)

    def add_instance_component(self, component_name, component):
        """Adds a pyomo component to the model instance."""
        self.instance.add_component(component_name, component)

    def add_arcs(self):
        """Adds arcs to the model instance."""
        
        # POWER: CHP 1 -> Electrical Grid
        self.instance.arc01 = Arc(
            source=self.instance.chp_1.power_out,
            destination=self.instance.electrical_grid.power_in,
        )
        
        # POWER: CHP 2 -> Electrical Grid
        self.instance.arc02 = Arc(
            source=self.instance.chp_2.power_out,
            destination=self.instance.electrical_grid.power_in,
        )
        
        # POWER: PV -> Electrical Grid
        self.instance.arc03 = Arc(
            source=self.instance.pv.power_out,
            destination=self.instance.electrical_grid.power_in,
        )
        
        # POWER: Battery Storage -> Electrical Grid
        self.instance.arc04 = Arc(
            source=self.instance.battery_storage.power_out,
            destination=self.instance.electrical_grid.power_in,
        )
        
        # POWER: Electrical Grid -> Battery Storage
        self.instance.arc05 = Arc(
            source=self.instance.electrical_grid.power_out,
            destination=self.instance.battery_storage.power_in,
        )
        
        # NGAS: NGAS Grid -> CHP 1
        self.instance.arc06 = Arc(
            source=self.instance.ngas_grid.ngas_out,
            destination=self.instance.chp_1.natural_gas_in,
        )
        
        # NGAS: NGAS Grid -> CHP 2
        self.instance.arc07 = Arc(
            source=self.instance.ngas_grid.ngas_out,
            destination=self.instance.chp_2.natural_gas_in,
        )
        
        # HYDROGEN: Hydrogen Grid -> CHP 1
        self.instance.arc08 = Arc(
            source=self.instance.hydrogen_grid.hydrogen_out,
            destination=self.instance.chp_1.hydrogen_in,
        )
        
        # HYDROGEN: Hydrogen Grid -> CHP 2
        self.instance.arc09 = Arc(
            source=self.instance.hydrogen_grid.hydrogen_out,
            destination=self.instance.chp_2.hydrogen_in,
        )
        
        # DISTRICT HEAT: CHP 1 -> District Heat Grid
        self.instance.arc10 = Arc(
            source=self.instance.chp_1.heat_out,
            destination=self.instance.heat_grid.heat_in,
        )
        
        # DISTRICT HEAT: CHP 2 -> District Heat Grid
        self.instance.arc11 = Arc(
            source=self.instance.chp_2.heat_out,
            destination=self.instance.heat_grid.heat_in,
        )
        
        # DISTRICT HEAT: District Heat Storage -> District Heat Grid
        self.instance.arc12 = Arc(
            source=self.instance.heat_storage.heat_out,
            destination=self.instance.heat_grid.heat_in,
        )
        
        # DISTRICT HEAT: District Heat Grid -> District Heat Storage
        self.instance.arc13 = Arc(
            source=self.instance.heat_grid.heat_out,
            destination=self.instance.heat_storage.heat_in,
        )
        
        # WASTE: CHP 1 -> Waste Heat Grid
        self.instance.arc14 = Arc(
            source=self.instance.chp_1.waste_heat_out,
            destination=self.instance.waste_heat_grid.waste_heat_in,
        )
        
        # WASTE: CHP 2 -> Waste Heat Grid
        self.instance.arc15 = Arc(
            source=self.instance.chp_2.waste_heat_out,
            destination=self.instance.waste_heat_grid.waste_heat_in,
        )

        # WASTE: Waste Heat Grid -> Geo Storage
        self.instance.arc16 = Arc(
            source=self.instance.waste_heat_grid.waste_heat_out,
            destination=self.instance.geo_heat_storage.heat_in
        )
        
        # GEO: Geo Storage -> 1. Stage Heat Pump
        self.instance.arc17 = Arc(
            source=self.instance.geo_heat_storage.heat_out,
            destination=self.instance.heatpump_s1.heat_in
        )

        # GEO: 1. Stage Heat Pump -> 2. Stage Heat Pump
        self.instance.arc18 = Arc(
            source=self.instance.heatpump_s1.heat_out,
            destination=self.instance.heatpump_s2.waste_heat_in,
        )

        # WASTE: Waste Heat Grid -> 2. Stage Heat Pump
        self.instance.arc19 = Arc(
            source=self.instance.waste_heat_grid.waste_heat_out,
            destination=self.instance.heatpump_s2.waste_heat_in,
        )

        # POWER: Electrical Grid -> 1.Stage Heat Pump
        self.instance.arc20 = Arc(
                source=self.instance.electrical_grid.power_out,
                destination=self.instance.heatpump_s1.power_in,
        )
        
        # POWER: Electrical Grid -> 2. Stage Heat Pump 
        self.instance.arc21 = Arc(
            source=self.instance.electrical_grid.power_out,
            destination=self.instance.heatpump_s2.power_in,
        )
        
        # LOCAL HEAT: Solar Thermal -> Stratified Storage
        self.instance.arc22 = Arc(
            source=self.instance.solar_thermal.heat_out,
            destination=self.instance.stratified_storage.st_heat_in,
        )
        # LOCAL HEAT: 2.Stage Heat Pump -> Stratified Storage
        self.instance.arc23 = Arc(
            source=self.instance.heatpump_s2.heat_out,
            destination=self.instance.stratified_storage.wp_heat_in,
        )

        # LOCAL HEAT: Stratified Storage Z1 -> District Heat Grid 
        self.instance.arc24 = Arc(
            source=self.instance.stratified_storage.Z1_FW_heat_out,
            destination=self.instance.heat_grid.excess_heat_in,
        )
        # LOCAL HEAT: Stratified Storage Z1 -> Local Heat Grid
        self.instance.arc25 = Arc(
            source=self.instance.stratified_storage.Z1_NW_heat_out,
            destination=self.instance.local_heat_grid.Z1_NW_heat_in,
        )
        
        # LOCAL HEAT: Stratified Storage Z2 -> Local Heat Grid
        self.instance.arc26 = Arc(
            source=self.instance.stratified_storage.Z2_NW_heat_out,
            destination=self.instance.local_heat_grid.Z2_NW_heat_in,
        )

        # DISTRICT HEAT: District Heat Grid -> Local Heat Grid
        self.instance.arc27 = Arc(
            source=self.instance.heat_grid.heat_grid_to_local_out, 
            destination=self.instance.local_heat_grid.district_heat_in,
        )




    def solve(self, output_dir):
        """Solves the optimization problem."""
        
        # Generate timestamp once
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config_name = os.path.basename(self.config_file).replace('.json','')
        log_filename = f"{config_name}_{self.timestamp}_solver.log"

        # Get directory structure
        _, run_dir = self.get_directory_structure(output_dir)


        self.results = self.solver.solve(
            self.instance,
            symbolic_solver_labels=True,
            tee=True,
            logfile= os.path.join(run_dir, log_filename),
            load_solutions=True,
            report_timing=True,
        )

    def write_results(self, include_arcs=False):
        """Writes the resulting time series to a dataframe."""
        self.results.write()

        df_variables = pd.DataFrame()
        df_parameters = pd.DataFrame()
        df_expressions = pd.DataFrame()
        df_output = pd.DataFrame()

        for parameter in self.instance.component_objects(Param, active=True):
            name = parameter.name
            # Write only indexed parameters
            try:
                if hasattr(parameter, 'index_set') and parameter.index_set() is not None:
                    # Vergleiche die String-Repräsentation der Sets
                    if str(parameter.index_set()) == str(self.instance.t):
                        df_parameters[name] = [value(parameter[t]) for t in self.instance.t]
            
            # Skip scalar Parameters
            except:
                continue

        #########

        # for variable in self.instance.component_objects(Var, active=True):
        #     name = variable.name
        #     if "aux" in name:  # Filters auxiliary variables from the output data
        #         continue
        #     if "splitfrac" in name:
        #         continue
        #     # Skip arc variables if not included
        #     if not include_arcs and "arc" in name.lower():
        #         continue
            
        #     # Füge nur berechnete Variablen hinzu
        #     values = []
        #     for t in self.instance.t:
        #         v = value(variable[t], exception=False)  # Gibt None zurück, wenn nicht initialisiert
        #         if v is not None:  # Nur initialisierte Variablen hinzufügen
        #             values.append(v)
        #         else:
        #             values.append(None)  # Optional: None hinzufügen, um Lücken zu markieren
        #     if any(v is not None for v in values):  # Nur hinzufügen, wenn mindestens ein Wert gesetzt ist
        #         df_variables[name] = values
        
        ######

        # Verbesserte Variable-Verarbeitung für mehrfach indizierte Variablen
        for variable in self.instance.component_objects(Var, active=True):
            name = variable.name
            if "aux" in name or "splitfrac" in name or (not include_arcs and "arc" in name.lower()):
                continue
            
            # Prüfen, ob die Variable mehrfach indiziert ist
            try:
                next(variable.iteritems())
                index_dims = sum(1 for _ in next(variable.iteritems())[0]) if variable else 0
            except (StopIteration, TypeError):
                index_dims = 0
            
            if index_dims > 1:
                # Mehrfach indizierte Variable (z.B. T_sto[t, layer])
                # Erstelle für jede zweite Dimension einen eigenen Eintrag
                second_indices = set(idx[1] for idx in variable.keys())
                for second_idx in second_indices:
                    values = []
                    for t in self.instance.t:
                        try:
                            v = value(variable[t, second_idx], exception=False)
                            values.append(v)
                        except (KeyError, IndexError):
                            values.append(None)
                            
                    if any(v is not None for v in values):
                        col_name = f"{name}_{second_idx}"
                        df_variables[col_name] = values
            else:
                # Einfach indizierte Variable (nur nach Zeit)
                values = []
                for t in self.instance.t:
                    try:
                        v = value(variable[t], exception=False)
                        values.append(v)
                    except (KeyError, IndexError):
                        values.append(None)
                        
                if any(v is not None for v in values):
                    df_variables[name] = values

        # Get expressions
        for expr in self.instance.component_objects(Expression, active=True):
            name = expr.name
            values = []
            for t in self.instance.t:
                try:
                    v = value(expr[t])
                    values.append(v)
                except:
                    values.append(None)
            df_expressions[name] = values


        df_output = pd.concat([df_parameters, df_variables, df_expressions], axis=1)
        df_output.index = self.instance.t
        df_output.index.name = "t"

        self.result_data = df_output

    def save_result_data(self, output_dir):
        """Saves the result data as csv with timestamp."""
    
        
        # Create filename with config and timestamp
        config_name = os.path.basename(self.config_file).replace('.json','')
        output_filename = f"{config_name}_{self.timestamp}_output.csv"
        
        # Get directory structure
        _, run_dir = self.get_directory_structure(output_dir)
        
        # Save file
        output_filepath = os.path.join(run_dir, output_filename)
        self.result_data.to_csv(output_filepath)
        
        # Optional: Save run metadata
        metadata = {
            "timestamp": self.timestamp,
            "config": self.config_file,
            "solver_options": self.solver.options,
            "hydrogen_admixture": {
                "chp_1": self.instance.chp_1.hydrogen_admixture_factor.value,
                "chp_2": self.instance.chp_2.hydrogen_admixture_factor.value,
            },
            "H2_PRICE": self.instance.H2_PRICE.value,
            "CO2_PRICE": self.instance.CO2_PRICE.value,
            "HEAT_PRICE": self.instance.HEAT_PRICE.value,
            "USE_CONST_H2_PRICE": self.instance.USE_CONST_H2_PRICE.value,

            # Add more relevant metadata e.g, Geothermal unit
        }

        with open(os.path.join(run_dir, f"{config_name}_{self.timestamp}_metadata.json"), 'w') as f:
            json.dump(metadata, f, indent=4)

    def get_directory_structure(self, output_dir):
        """
        Creates a directory structure based on use case and config.
        Handles single-word config names specially to avoid redundant nesting.
        
        Returns:
        -------
        tuple
            (use_case_dir, run_dir) - Paths to the use case directory and specific run directory
        """
        # Extract base config name without .json extension
        config_name = os.path.basename(self.config_file).replace('.json', '')
        
        # Extract use case (part before first underscore)
        if '_' in config_name:
            # Regular case: "uc1_2028_0h2" -> use_case="uc1", full path="output/uc1/uc1_2028_0h2/"
            use_case = config_name.split('_')[0]
            use_case_dir = os.path.join(output_dir, use_case)
            run_dir = os.path.join(use_case_dir, config_name)
        else:
            # Special case for configs without underscore (like "dummy")
            # Just create a single directory: "output/dummy/"
            use_case = config_name
            use_case_dir = output_dir
            run_dir = os.path.join(output_dir, config_name)
        
        # Create directories
        os.makedirs(run_dir, exist_ok=True)
    
        return use_case_dir, run_dir
    
    
    def calculate_costs(self, component_param, price_param):
        """
        Calculate costs for a component using its values and a price parameter.
        
        Parameters:
        ----------
        component_values : Pyomo component or expression
            The component whose cost should be calculated (e.g., CO2 emissions, gas consumption)
        price_param : Pyomo parameter
            The price parameter, which can be constant or time-dependent
            
        Returns:
        -------
        float
            Total costs, rounded to 2 decimal places
        """
        if hasattr(price_param, 'index_set') and price_param.index_set() is self.instance.t:
            is_price_indexed = True
        else:
            is_price_indexed = False
        
        # is_price_indexed = hasattr(price_param, 'index_set') 
        # print(price_param.index_set())
        # print(f"Price indexed: {is_price_indexed}")
        total_costs = 0
        
        try:
            for i in self.instance.t:

                # Get appropriate price (time dependent or constant)
                if is_price_indexed:
                    price = value(price_param[i])
                else:
                    price = value(price_param)

                component = value(component_param[i])
                
                total_costs += component * price

            return round(total_costs, 2)
        except Exception as e:
            print(f"Error calculating costs: {e}")
            return 0.0



    def save_costs(self, output_dir):
        """
        Calculate, display, and save the cost breakdown of the optimization.
        
        This function:
        1. Calculates all cost components based on model results
        2. Compares calculated costs with solver objective
        3. Displays a formatted cost summary
        4. Saves the cost data to a JSON file
        
        Parameters:
        ----------
        output_dir : str
            Directory path where cost results will be saved
            
        Returns:
        -------
        dict
            Dictionary containing all cost components
        """
        # 1. Calculate costs using appropriate hydrogen price setting
        if value(self.instance.USE_CONST_H2_PRICE):
            h2_price_param = self.instance.H2_PRICE
            h2_price_type = "constant"
        else:
            h2_price_param = self.instance.hydrogen_price
            h2_price_type = "time-varying"
        
        # Get solver objective value for comparison
        solver_objective = value(self.instance.objective)
        
        # 2. Calculate all cost components
        costs = {
            "costs": {
                "CO2_costs_chp_1": self.calculate_costs(
                    self.instance.chp_1.co2, self.instance.CO2_PRICE
                ),
                "CO2_costs_chp_2": self.calculate_costs(
                    self.instance.chp_2.co2, self.instance.CO2_PRICE
                ),
                "gas_costs": self.calculate_costs(
                    self.instance.ngas_grid.ngas_supply, self.instance.gas_price
                ),
                "power_costs": self.calculate_costs(
                    self.instance.electrical_grid.power_balance, self.instance.power_price
                ),
                "hydrogen_costs": self.calculate_costs(
                    self.instance.hydrogen_grid.hydrogen_supply, h2_price_param
                )
            },
            "revenue": {
                "heat_revenue": self.calculate_costs(
                    self.instance.heat_grid.heat_feedin, self.instance.HEAT_PRICE
                )
            },
            "solver_objective": round(solver_objective, 2)
        }
        
        # 3. Compute summary values
        total_costs = sum(cost for cost in costs["costs"].values())
        costs["costs"]["total"] = total_costs
        
        total_revenue = sum(rev for rev in costs["revenue"].values())
        costs["revenue"]["total"] = total_revenue
        
        net_total = total_costs - total_revenue
        costs["net_total"] = net_total
        
        # 4. Calculate discrepancy between calculated costs and solver objective
        discrepancy = abs(net_total - solver_objective)
        discrepancy_percent = (discrepancy / solver_objective * 100) if solver_objective != 0 else 0
        costs["validation"] = {
            "discrepancy": round(discrepancy, 2),
            "discrepancy_percent": round(discrepancy_percent, 4),
        }
        
        # 5. Display formatted cost summary
        print("\nCost Summary:")
        print("=============")
        for name, cost in costs["costs"].items():
            print(f"{name.replace('_', ' ').title()}: {cost:,.2f} €")
        
        print("\nRevenue Summary:")
        print("===============")
        for name, rev in costs["revenue"].items():
            print(f"{name.replace('_', ' ').title()}: {rev:,.2f} €")
        
        print("===============")
        print(f"Info: Using {h2_price_type} hydrogen price")
        print(f"Net Total (Costs - Revenue): {net_total:,.2f} €")
        print(f"Solver Objective Value: {solver_objective:,.2f} €")
        print(f"Discrepancy: {discrepancy:,.2f} € ({discrepancy_percent:.4f}%)")
        print("===============")

        # 6. Save cost data to file
        config_name = os.path.basename(self.config_file).replace('.json', '')
        
        # Get directory structure
        _, run_dir = self.get_directory_structure(output_dir)
        
        cost_filename = f"{config_name}_{self.timestamp}_costs.json"
        try:
            with open(os.path.join(run_dir, cost_filename), 'w') as f:
                json.dump(costs, f, indent=4)
        except IOError as e:
            print(f"Warning: Could not save cost file: {e}")
                
        return costs

    # Zielfunktion
    # def obj_expression(self, m):
    #     """Rule for the model objective."""
    #     return (
    #         quicksum(m.ngas_grid.ngas_supply[t] * m.gas_price[t] for t in m.t)
    #         + quicksum(m.chp_1.co2[t] * m.CO2_PRICE for t in m.t)
    #         + quicksum(m.chp_2.co2[t] * m.CO2_PRICE for t in m.t)
    #         + quicksum(m.electrical_grid.power_balance[t] * m.power_price[t] for t in m.t)
    #         #+ quicksum(m.hydrogen_grid.hydrogen_supply[t] * m.H2_PRICE for t in m.t)
    #         + quicksum(m.hydrogen_grid.hydrogen_supply[t] * m.hydrogen_price[t] for t in m.t)
    #         - quicksum(m.heat_grid.heat_feedin[t] * m.HEAT_PRICE for t in m.t)
    #     )
    
    def obj_expression(self, m):
        """Rule for the model objective."""
        # Determine which hydrogen price to use based on configuration
        if value(m.USE_CONST_H2_PRICE):
            # Verwende konstanten Preis
            hydrogen_cost = quicksum(m.hydrogen_grid.hydrogen_supply[t] * m.H2_PRICE for t in m.t)
        else:
            # Verwende zeitvariablen Preis
            hydrogen_cost = quicksum(m.hydrogen_grid.hydrogen_supply[t] * m.hydrogen_price[t] for t in m.t)
        
        return (
            quicksum(m.ngas_grid.ngas_supply[t] * m.gas_price[t] for t in m.t)
            + quicksum(m.chp_1.co2[t] * m.CO2_PRICE for t in m.t)
            + quicksum(m.chp_2.co2[t] * m.CO2_PRICE for t in m.t)
            + quicksum(m.electrical_grid.power_balance[t] * m.power_price[t] for t in m.t)
            + hydrogen_cost
            - quicksum(m.heat_grid.heat_feedin[t] * m.HEAT_PRICE for t in m.t)
        )


if __name__ == "__main__":
    # Parse arguments
    parser = argparse.ArgumentParser(description='Run energy system optimization')
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--config',
        choices=AVAILABLE_CONFIGS,
        default="dummy.json",
        help='Configuration file to use')
    group.add_argument(
        '--use-case',
        help='Run all configuration files for a specific use case (e.g., "uc1")')
    args = parser.parse_args()

    # Function to run a single simulation
    def run_simulation(config_file):
        print(f"\n{'='*80}")
        print(f"Running scenario: {config_file}")
        print(f"{'='*80}\n")
        
        try:
            # Create model instance
            lp = Model(config_file=config_file)

            print("SETTING SOLVER OPTIONS")
            lp.set_solver(
                solver_name="gurobi",
                #TimeLimit=5000,  # solver will stop after x seconds
                MIPGap=0.02, # solver will stop if gap <= x %
            )

            print("LOADING TIMESERIES DATA")
            lp.load_timeseries_data()

            print("DECLARING MODEL")
            lp.add_components()

            # Declare Objective
            print("DECLARING OBJECTIVE...")
            lp.add_objective()

            # Create model instance
            print("CREATING INSTANCE...")
            lp.instantiate()

            # Define arcs
            print("DECLARING ARCS...")
            lp.add_arcs()
            lp.expand_arcs()

            # Solve the optimization problem
            print("START SOLVING...")
            lp.solve(output_dir=PATH_OUT)

            # Write results
            print("WRITING RESULTS...")
            lp.write_results()
            
            # Save results
            print("SAVING RESULTS...")
            lp.save_result_data(output_dir=PATH_OUT)

            # Calculate costs
            print("CALCULATING COSTS...")
            lp.save_costs(output_dir=PATH_OUT)
            
            print(f"\nFinished scenario: {config_file}\n")
            return True
        except Exception as e:
            print(f"ERROR in scenario {config_file}: {str(e)}")
            return False

    # Run simulations
    if args.use_case:
        # Filter configurations for the specified use case
        use_case_configs = [cfg for cfg in AVAILABLE_CONFIGS if cfg.startswith(f"{args.use_case}_")]
        
        if not use_case_configs:
            print(f"No configuration files found for use case: {args.use_case}")
            sys.exit(1)
        
        print(f"Found {len(use_case_configs)} configuration files for use case {args.use_case}:")
        for cfg in use_case_configs:
            print(f"  - {cfg}")
        
        # Run sequentially with error handling
        successful = 0
        failed = 0
        for config_file in use_case_configs:
            if run_simulation(config_file):
                successful += 1
            else:
                failed += 1
                
        print(f"All simulations for use case {args.use_case} completed.")
        print(f"Results: {successful} successful, {failed} failed")
    else:
        # Run a single configuration
        run_simulation(args.config)