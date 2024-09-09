"""Main script for the optimization of the energy system."""

import pandas as pd

from pyomo.opt import SolverFactory
from pyomo.environ import (
    AbstractModel,
    DataPortal,
    Set,
    Param,
    Objective,
    Var,
    quicksum,
    value,
    minimize,
    TransformationFactory,
)
from pyomo.network import Arc

from blocks import chp, grid, storage, res
import blocks.electrolyzer as elec
import blocks.heatpump as hp


# Path
PATH_IN = "data/input/"
PATH_OUT = "data/output/"


# Declare constant prices
CO2_PRICE = 95.98  # price in €/t
HEAT_PRICE = 0  # price in €/MWh
H2_PRICE = 81.01  # price in €/MWh


class Model:
    """Main class for the creation of the optimization model."""

    def __init__(self) -> None:
        self.model = AbstractModel()
        self.instance = None
        self.solver = None
        self.timeseries_data = None
        self.results = None
        self.result_data = None

    def set_solver(self, solver_name, **kwargs):
        """Declare solver and solver options."""
        self.solver = SolverFactory(solver_name)

        for key in kwargs:
            self.solver.options[key] = kwargs[key]

    def load_timeseries_data(self):
        """Declare timeseries data for the optimization model."""
        self.timeseries_data = DataPortal()

        self.timeseries_data.load(
            # filename=PATH_IN + 'prices/dummy/gas_price.csv',
            filename=PATH_IN + "prices/gee23/gas_price_2024.csv",
            index="t",
            param="gas_price",
        )
        self.timeseries_data.load(
            # filename=PATH_IN + 'prices/dummy/power_price.csv',
            filename=PATH_IN + "prices/gee23/power_price_2024.csv",
            index="t",
            param="power_price",
        )
        self.timeseries_data.load(
            # filename=PATH_IN + PATH_IN + 'demands/heat_short.csv',
            filename=PATH_IN + "demands/heat.csv",
            index="t",
            param="heat_demand",
        )

    def add_components(self):
        """Adds pyomo component to the model."""

        # Define sets
        self.model.t = Set(ordered=True)

        # Define parameters
        self.model.gas_price = Param(self.model.t)
        self.model.power_price = Param(self.model.t)
        self.model.heat_demand = Param(self.model.t)

        # Define block components
        chp1 = chp.Chp("chp_1", PATH_IN + "assets/chp.csv", hydrogen_admixture=1)
        chp2 = chp.Chp("chp_2", PATH_IN + "assets/chp.csv", hydrogen_admixture=1)
        electrolyzer1 = elec.Electrolyzer(
            "electrolyzer_1", PATH_IN + "assets/electrolyzer.csv"
        )
        electrolyzer2 = elec.Electrolyzer(
            "electrolyzer_2", PATH_IN + "assets/electrolyzer.csv"
        )
        electrolyzer3 = elec.Electrolyzer(
            "electrolyzer_3", PATH_IN + "assets/electrolyzer.csv"
        )
        electrolyzer4 = elec.Electrolyzer(
            "electrolyzer_4", PATH_IN + "assets/electrolyzer.csv"
        )
        electrolyzer5 = elec.Electrolyzer(
            "electrolyzer_5", PATH_IN + "assets/electrolyzer.csv"
        )
        electrolyzer6 = elec.Electrolyzer(
            "electrolyzer_6", PATH_IN + "assets/electrolyzer.csv"
        )
        h2_grid = grid.HydrogenGrid(
            "hydrogen_grid", PATH_IN + "assets/hydrogen_grid.csv"
        )
        n_grid = grid.NGasGrid("ngas_grid")
        e_grid = grid.ElectricalGrid(
            "electrical_grid", PATH_IN + "assets/electrical_grid.csv"
        )
        h_grid = grid.HeatGrid("heat_grid", PATH_IN + "assets/heat_grid.csv")
        b_storage = storage.BatteryStorage(
            "battery_storage", PATH_IN + "assets/battery_storage.csv"
        )
        h_storage = storage.HeatStorage(
            "heat_storage", PATH_IN + "assets/heat_storage.csv"
        )
        heatpump = hp.Heatpump("heatpump", PATH_IN + "assets/heatpump.csv")
        pv = res.Photovoltaics(
            "pv",
            PATH_IN + "assets/pv.csv",
            PATH_IN + "pv_capacity_factors/leipzig_t45_a180.csv",
        )

        chp1.add_to_model(self.model)
        chp2.add_to_model(self.model)
        electrolyzer1.add_to_model(self.model)
        electrolyzer2.add_to_model(self.model)
        electrolyzer3.add_to_model(self.model)
        electrolyzer4.add_to_model(self.model)
        electrolyzer5.add_to_model(self.model)
        electrolyzer6.add_to_model(self.model)
        e_grid.add_to_model(self.model)
        h2_grid.add_to_model(self.model)
        n_grid.add_to_model(self.model)
        h_grid.add_to_model(self.model)
        b_storage.add_to_model(self.model)
        h_storage.add_to_model(self.model)
        heatpump.add_to_model(self.model)
        pv.add_to_model(self.model)

    def add_objective(self):
        """Adds the objective to the abstract model."""
        self.model.objective = Objective(rule=self.obj_expression, sense=minimize)

    def instantiate(self):
        """Creates a concrete model from the abstract model."""
        self.instance = self.model.create_instance(self.timeseries_data)

    def expand_arcs(self):
        """Expands arcs and generate connection constraints."""
        TransformationFactory("network.expand_arcs").apply_to(self.instance)

    def add_instance_component(self, component_name, component):
        """Adds a pyomo component to the model instance."""
        self.instance.add_component(component_name, component)

    def add_arcs(self):
        """Adds arcs to the model instance."""

        self.instance.arc01 = Arc(
            source=self.instance.chp_1.power_out,
            destination=self.instance.electrical_grid.power_in,
        )
        self.instance.arc02 = Arc(
            source=self.instance.chp_2.power_out,
            destination=self.instance.electrical_grid.power_in,
        )
        self.instance.arc03 = Arc(
            source=self.instance.pv.power_out,
            destination=self.instance.electrical_grid.power_in,
        )
        self.instance.arc04 = Arc(
            source=self.instance.battery_storage.power_out,
            destination=self.instance.electrical_grid.power_in,
        )
        self.instance.arc05 = Arc(
            source=self.instance.electrical_grid.power_out,
            destination=self.instance.battery_storage.power_in,
        )
        self.instance.arc06 = Arc(
            source=self.instance.electrical_grid.power_out,
            destination=self.instance.electrolyzer_1.power_in,
        )
        self.instance.arc07 = Arc(
            source=self.instance.electrical_grid.power_out,
            destination=self.instance.electrolyzer_2.power_in,
        )
        self.instance.arc08 = Arc(
            source=self.instance.electrical_grid.power_out,
            destination=self.instance.electrolyzer_3.power_in,
        )
        self.instance.arc09 = Arc(
            source=self.instance.electrical_grid.power_out,
            destination=self.instance.electrolyzer_4.power_in,
        )
        self.instance.arc10 = Arc(
            source=self.instance.electrical_grid.power_out,
            destination=self.instance.electrolyzer_5.power_in,
        )
        self.instance.arc11 = Arc(
            source=self.instance.electrical_grid.power_out,
            destination=self.instance.electrolyzer_6.power_in,
        )
        self.instance.arc12 = Arc(
            source=self.instance.electrolyzer_1.hydrogen_out,
            destination=self.instance.hydrogen_grid.hydrogen_in,
        )
        self.instance.arc13 = Arc(
            source=self.instance.electrolyzer_2.hydrogen_out,
            destination=self.instance.hydrogen_grid.hydrogen_in,
        )
        self.instance.arc14 = Arc(
            source=self.instance.electrolyzer_3.hydrogen_out,
            destination=self.instance.hydrogen_grid.hydrogen_in,
        )
        self.instance.arc15 = Arc(
            source=self.instance.electrolyzer_4.hydrogen_out,
            destination=self.instance.hydrogen_grid.hydrogen_in,
        )
        self.instance.arc16 = Arc(
            source=self.instance.electrolyzer_5.hydrogen_out,
            destination=self.instance.hydrogen_grid.hydrogen_in,
        )
        self.instance.arc17 = Arc(
            source=self.instance.electrolyzer_6.hydrogen_out,
            destination=self.instance.hydrogen_grid.hydrogen_in,
        )
        self.instance.arc18 = Arc(
            source=self.instance.chp_1.natural_gas_in,
            destination=self.instance.ngas_grid.ngas_out,
        )
        self.instance.arc19 = Arc(
            source=self.instance.chp_2.natural_gas_in,
            destination=self.instance.ngas_grid.ngas_out,
        )
        self.instance.arc20 = Arc(
            source=self.instance.chp_1.hydrogen_in,
            destination=self.instance.hydrogen_grid.hydrogen_out,
        )
        self.instance.arc21 = Arc(
            source=self.instance.chp_2.hydrogen_in,
            destination=self.instance.hydrogen_grid.hydrogen_out,
        )
        self.instance.arc22 = Arc(
            source=self.instance.electrolyzer_1.heat_out,
            destination=self.instance.heatpump.heat_in,
        )
        self.instance.arc23 = Arc(
            source=self.instance.electrolyzer_2.heat_out,
            destination=self.instance.heatpump.heat_in,
        )
        self.instance.arc24 = Arc(
            source=self.instance.electrolyzer_3.heat_out,
            destination=self.instance.heatpump.heat_in,
        )
        self.instance.arc25 = Arc(
            source=self.instance.electrolyzer_4.heat_out,
            destination=self.instance.heatpump.heat_in,
        )
        self.instance.arc26 = Arc(
            source=self.instance.electrolyzer_5.heat_out,
            destination=self.instance.heatpump.heat_in,
        )
        self.instance.arc27 = Arc(
            source=self.instance.electrolyzer_6.heat_out,
            destination=self.instance.heatpump.heat_in,
        )
        self.instance.arc28 = Arc(
            source=self.instance.heatpump.heat_out,
            destination=self.instance.heat_grid.heat_in,
        )
        self.instance.arc29 = Arc(
            source=self.instance.chp_1.heat_out,
            destination=self.instance.heat_grid.heat_in,
        )
        self.instance.arc30 = Arc(
            source=self.instance.chp_2.heat_out,
            destination=self.instance.heat_grid.heat_in,
        )
        self.instance.arc31 = Arc(
            source=self.instance.electrical_grid.power_out,
            destination=self.instance.heatpump.power_in,
        )
        self.instance.arc32 = Arc(
            source=self.instance.heat_storage.heat_out,
            destination=self.instance.heat_grid.heat_in,
        )
        self.instance.arc33 = Arc(
            source=self.instance.heat_grid.heat_out,
            destination=self.instance.heat_storage.heat_in,
        )

    def solve(self):
        """Solves the optimization problem."""
        self.results = self.solver.solve(
            self.instance,
            symbolic_solver_labels=True,
            tee=True,
            logfile=PATH_OUT + "solver.log",
            load_solutions=True,
            report_timing=True,
        )

    def write_results(self):
        """Writes the resulting time series to a dataframe."""
        self.results.write()

        df_variables = pd.DataFrame()
        df_parameters = pd.DataFrame()
        df_output = pd.DataFrame()

        for parameter in self.instance.component_objects(Param, active=True):
            name = parameter.name
            if "hydrogen_admixture_factor" in name:
                continue
            df_parameters[name] = [value(parameter[t]) for t in self.instance.t]

        for variable in self.instance.component_objects(Var, active=True):
            name = variable.name
            if "aux" in name:  # Filters auxiliary variables from the output data
                continue
            if "splitfrac" in name:
                continue
            df_variables[name] = [value(variable[t]) for t in self.instance.t]

        df_output = pd.concat([df_parameters, df_variables], axis=1)
        df_output.index = self.instance.t
        df_output.index.name = "t"

        self.result_data = df_output

    def save_result_data(self, filepath):
        """Saves the result data as csv to the given file path."""
        self.result_data.to_csv(filepath)

    def obj_expression(self, m):
        """Rule for the model objective."""
        return (
            quicksum(m.ngas_grid.ngas_balance[t] * m.gas_price[t] for t in m.t)
            + quicksum(m.chp_1.co2[t] * CO2_PRICE for t in m.t)
            + quicksum(m.chp_2.co2[t] * CO2_PRICE for t in m.t)
            + quicksum(
                m.electrical_grid.power_balance[t] * m.power_price[t] for t in m.t
            )
            + quicksum(m.hydrogen_grid.hydrogen_balance[t] * H2_PRICE for t in m.t)
            - quicksum(m.heat_grid.heat_feedin[t] * HEAT_PRICE for t in m.t)
        )


if __name__ == "__main__":
    lp = Model()

    print("SETTING SOLVER OPTIONS")
    lp.set_solver(
        solver_name="gurobi",
        TimeLimit=1800,  # solver will stop after x seconds
        MIPGap=0.01,
    )  # solver will stop if gap <= 1%

    print("PREPARING DATA")
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
    lp.solve()

    lp.write_results()
    lp.save_result_data(PATH_OUT + "output_time_series.csv")
