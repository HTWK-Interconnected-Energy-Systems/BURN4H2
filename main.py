"""Main script for the optimization of the energy system."""

# Import default libraries
import pandas as pd
import json
import os
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
from blocks import chp, grid, storage, res
import blocks.electrolyzer as elec
import blocks.heatpump as hp
import blocks.collector as st

# Path
PATH_IN = "data/input/"
PATH_OUT = "data/output/"
PATH_CONFIG = "data/config/"

# Config files
AVAILABLE_CONFIGS = [
    "dummy.json",
    "ue24_ST-min_NW-ref_2028.json",
    "ue24_ST-max_NW-ref_2028.json",
    "ue24_ST-min_NW-ext_2028.json",
    "ue24_ST-max_NW-ext_2028.json"
]

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
        self.data_portal.load(filename = 'data/config/global.json')
        
        # Load config
        with open(PATH_CONFIG + self.config_file, "r") as f:
            config = json.load(f)

        # Load timeseries data from config
        for param_name, param_config in config.get("timeseries", {}).items():
            self.data_portal.load(
                filename=PATH_IN + param_config["file"],
                index=param_config["index"],
                param=param_name,
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
        self.model.heat_demand = Param(self.model.t)
        self.model.local_heat_demand = Param(self.model.t)
        self.model.solar_thermal_heat_profile = Param(self.model.t)
        self.model.normalized_solar_thermal_heat_profile = Param(self.model.t)
        
        # Define non-indexed parameters
        self.model.CO2_PRICE = Param()
        self.model.HEAT_PRICE = Param()
        self.model.H2_PRICE = Param()
        self.model.INSTALLED_ST_POWER = Param()
        self.model.HYDROGEN_ADMIXTURE_CHP_1 = Param()
        self.model.HYDROGEN_ADMIXTURE_CHP_2 = Param()


        # Define block components
        chp1 = chp.Chp(
            "chp_1", 
            PATH_IN + "assets/chp.csv",
            hydrogen_admixture=self.model.HYDROGEN_ADMIXTURE_CHP_1
        )
        chp2 = chp.Chp(
            "chp_2", 
            PATH_IN + "assets/chp.csv",
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
        lh_storage = storage.LocalHeatStorage(
            "local_heat_storage", 
            PATH_IN + "assets/local_heat_storage.csv"
        )
        gh_storage = storage.GeoHeatStorage(
            "geo_heat_storage", 
            PATH_IN + "assets/geo_heat_storage.csv"
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
        lh_storage.add_to_model(self.model)
        gh_storage.add_to_model(self.model)

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
        # CHECK
        self.instance.arc01 = Arc(
            source=self.instance.chp_1.power_out,
            destination=self.instance.electrical_grid.power_in,
        )
        
        # POWER: CHP 2 -> Electrical Grid
        # CHECK
        self.instance.arc02 = Arc(
            source=self.instance.chp_2.power_out,
            destination=self.instance.electrical_grid.power_in,
        )
        
        # POWER: PV -> Electrical Grid
        # CHECK
        self.instance.arc03 = Arc(
            source=self.instance.pv.power_out,
            destination=self.instance.electrical_grid.power_in,
        )
        
        # POWER: Battery Storage -> Electrical Grid
        # CHECK
        self.instance.arc04 = Arc(
            source=self.instance.battery_storage.power_out,
            destination=self.instance.electrical_grid.power_in,
        )
        
        # POWER: Electrical Grid -> Battery Storage
        # CHECK
        self.instance.arc05 = Arc(
            source=self.instance.electrical_grid.power_out,
            destination=self.instance.battery_storage.power_in,
        )
        
        # NGAS: NGAS Grid -> CHP 1
        # CHECK
        self.instance.arc06 = Arc(
            source=self.instance.ngas_grid.ngas_out,
            destination=self.instance.chp_1.natural_gas_in,
        )
        
        # NGAS: NGAS Grid -> CHP 2
        # CHECK
        self.instance.arc07 = Arc(
            source=self.instance.ngas_grid.ngas_out,
            destination=self.instance.chp_2.natural_gas_in,
        )
        
        # HYDROGEN: Hydrogen Grid -> CHP 1
        # CHECK
        self.instance.arc08 = Arc(
            source=self.instance.hydrogen_grid.hydrogen_out,
            destination=self.instance.chp_1.hydrogen_in,
        )
        
        # HYDROGEN: Hydrogen Grid -> CHP 2
        # CHECK
        self.instance.arc09 = Arc(
            source=self.instance.hydrogen_grid.hydrogen_out,
            destination=self.instance.chp_2.hydrogen_in,
        )
        
        # HEAT: CHP 1 -> Heat Grid
        # CHECK
        self.instance.arc10 = Arc(
            source=self.instance.chp_1.heat_out,
            destination=self.instance.heat_grid.heat_in,
        )
        
        # HEAT: CHP 2 -> Heat Grid
        # CHECK
        self.instance.arc11 = Arc(
            source=self.instance.chp_2.heat_out,
            destination=self.instance.heat_grid.heat_in,
        )
        
        # HEAT: Heat Storage -> Heat Grid
        # CHECK
        self.instance.arc12 = Arc(
            source=self.instance.heat_storage.heat_out,
            destination=self.instance.heat_grid.heat_in,
        )
        
        # HEAT: Heat Grid -> Heat Storage
        # CHECK
        self.instance.arc13 = Arc(
            source=self.instance.heat_grid.heat_out,
            destination=self.instance.heat_storage.heat_in,
        )
        
        # WASTE: CHP 1 -> Waste Grid
        # CHECK
        self.instance.arc14 = Arc(
            source=self.instance.chp_1.waste_heat_out,
            destination=self.instance.waste_heat_grid.waste_heat_in,
        )
        
        # WASTE: CHP 2 -> Waste Grid
        # CHECK
        self.instance.arc15 = Arc(
            source=self.instance.chp_2.waste_heat_out,
            destination=self.instance.waste_heat_grid.waste_heat_in,
        )

        # WASTE: Waste Grid -> Geo Storage
        # CHECK
        self.instance.arc16 = Arc(
            source=self.instance.waste_heat_grid.waste_heat_out,
            destination=self.instance.geo_heat_storage.heat_in
        )
        
        # GEO: Geo Storage -> 1. Stage Heat Pump
        # CHECK
        self.instance.arc17 = Arc(
            source=self.instance.geo_heat_storage.heat_out,
            destination=self.instance.heatpump_s1.heat_in
        )

        # GEO: 1. Stage Heat Pump -> Waste Heat Grid
        # CHECK 
        self.instance.arc18 = Arc(
            source=self.instance.heatpump_s1.heat_out,
            destination=self.instance.waste_heat_grid.waste_heat_in
        )

        # WASTE: Waste Grid -> 2. Stage Heat Pump
        # CHECK 
        self.instance.arc19 = Arc(
            source=self.instance.waste_heat_grid.waste_heat_out,
            destination=self.instance.heatpump_s2.waste_heat_in,
        )

        # POWER: Electrical Grid -> 1.Stage Heat Pump
        # CHECK
        self.instance.arc20 = Arc(
                source=self.instance.electrical_grid.power_out,
                destination=self.instance.heatpump_s1.power_in,
        )
        
        # POWER: Electrical Grid -> 2. Stage Heat Pump 
        # CHECK
        self.instance.arc21 = Arc(
            source=self.instance.electrical_grid.power_out,
            destination=self.instance.heatpump_s2.power_in,
        )
        
        # LOCAL HEAT: Solar Thermal -> LOCAL HEAT STORAGE
        # CHECK
        self.instance.arc22 = Arc(
            source = self.instance.solar_thermal.heat_out,
            destination = self.instance.local_heat_storage.heat_in,
        )
        
        # LOCAL HEAT: 2. Stage Heat Pump  -> Local HEAT STORAGE
        # CHECK
        self.instance.arc23 = Arc(
            source=self.instance.heatpump_s2.heat_out,
            destination=self.instance.local_heat_storage.heat_in,
        )

        # LOCAL HEAT: Local HEAT STORAGE -> Local Heat Grid
        # CHECK
        self.instance.arc24 = Arc(
            source=self.instance.local_heat_storage.heat_out,
            destination=self.instance.local_heat_grid.heat_in,
        )

        # EXCESS LOCAL HEAT: Local Heat Storage -> Heat Grid
        # CHECK
        self.instance.arc25 = Arc(
            source=self.instance.local_heat_storage.excess_heat_out,
            destination=self.instance.heat_grid.excess_heat_in 
        )

        # HEAT: Heat Grid -> Local Heat Grid
        # CHECK
        self.instance.arc26 = Arc(
            source=self.instance.heat_grid.heat_grid_to_local_out,
            destination=self.instance.local_heat_grid.district_heat_in,
        )


    def solve(self, output_dir):
        """Solves the optimization problem."""
        
        # Generate timestamp once
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        config_name = os.path.basename(self.config_file).replace('.json','')
        log_filename = f"{config_name}_{self.timestamp}_solver.log"

        # Create subdirectory
        run_dir = os.path.join(output_dir, config_name)
        os.makedirs(run_dir, exist_ok=True)


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
            if name == "CO2_PRICE":
                print(f"CO2_PRICE: {value(parameter)}")

            # Write only indexed parameters
            try:
                if hasattr(parameter, 'index_set') and parameter.index_set() is not None:
                    # Vergleiche die String-Repräsentation der Sets
                    if str(parameter.index_set()) == str(self.instance.t):
                        df_parameters[name] = [value(parameter[t]) for t in self.instance.t]
            
            # Skip scalar Parameters
            except:
                continue

        for variable in self.instance.component_objects(Var, active=True):
            name = variable.name
            if "aux" in name:  # Filters auxiliary variables from the output data
                continue
            if "splitfrac" in name:
                continue
            # Skip arc variables if not included
            if not include_arcs and "arc" in name.lower():
                continue
            
            # Füge nur berechnete Variablen hinzu
            values = []
            for t in self.instance.t:
                v = value(variable[t], exception=False)  # Gibt None zurück, wenn nicht initialisiert
                if v is not None:  # Nur initialisierte Variablen hinzufügen
                    values.append(v)
                else:
                    values.append(None)  # Optional: None hinzufügen, um Lücken zu markieren
            if any(v is not None for v in values):  # Nur hinzufügen, wenn mindestens ein Wert gesetzt ist
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
        
        # Create subdirectory for runs
        run_dir = os.path.join(output_dir, config_name)
        os.makedirs(run_dir, exist_ok=True)
        
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

            # Add more relevant metadata e.g, Geothermal unit
        }

        with open(os.path.join(run_dir, f"{config_name}_{self.timestamp}_metadata.json"), 'w') as f:
            json.dump(metadata, f, indent=4)


    # Zielfunktion
    # + quicksum(m.hydrogen_grid.hydrogen_balance[t] * H2_PRICE for t in m.t) # neu
    def obj_expression(self, m):
        """Rule for the model objective."""
        return (
            quicksum(m.ngas_grid.ngas_supply[t] * m.gas_price[t] for t in m.t)
            + quicksum(m.chp_1.co2[t] * m.CO2_PRICE for t in m.t)
            + quicksum(m.chp_2.co2[t] * m.CO2_PRICE for t in m.t)
            + quicksum(m.electrical_grid.power_balance[t] * m.power_price[t] for t in m.t)
            + quicksum(m.hydrogen_grid.hydrogen_supply[t] * m.H2_PRICE for t in m.t)
            - quicksum(m.heat_grid.heat_feedin[t] * m.HEAT_PRICE for t in m.t)
        )


if __name__ == "__main__":
    # Parse arguments
    parser = argparse.ArgumentParser(description='Run energy system optimization')
    parser.add_argument(
        '--config',
        choices=AVAILABLE_CONFIGS,
        default="dummy.json",
        help='Configuration file to use')
    args = parser.parse_args()

    print(f"Running scenario: {args.config}")

    # Create model instance
    lp = Model(config_file=args.config)

    print("SETTING SOLVER OPTIONS")
    lp.set_solver(
        solver_name="gurobi",
        TimeLimit=5000,  # solver will stop after x seconds
        MIPGap=0.08, # solver will stop if gap <= x %
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

    lp.write_results()
    lp.save_result_data(output_dir=PATH_OUT)
