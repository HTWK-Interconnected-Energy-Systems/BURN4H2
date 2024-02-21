import pandas as pd

from pyomo.opt import SolverFactory
from pyomo.environ import *
from pyomo.network import *

import blocks.chp as chp
import blocks.grid as grid
import blocks.storage as storage
import blocks.res as res
import blocks.electrolyzer as elec
import blocks.heatpump as hp


# Path
PATH_IN = 'data/input/'
PATH_OUT = 'data/output/'


# Declare constant prices
CO2_PRICE = 95.98   # price in €/t
HEAT_PRICE = 0      # price in €/MWh
H2_PRICE = 81.01    # price in €/MWh


class Model:
    
    def __init__(self) -> None:
        self.model = AbstractModel()
        self.instance = None
        self.solver = None
        self.timeseries_data = None
        self.asset_data = None
        self.asset_objects = {}
        self.results = None
        self.result_data = None
    

    def set_solver(self, solver_name, **kwargs):
        """Declare solver and solver options."""
        self.solver = SolverFactory(solver_name)

        for key in kwargs:
            self.solver.options[key] = kwargs[key]


    def prepare_timeseries_data(self, timeseries_data_dict):
        """Declare timeseries data for the optimization model.
        
        Parameters
        ----------
        timeseries_data_dict : dict
            A nested dictionary containing informations of the data files that
            should be loaded. Keys of the top level dictionary have to be the
            names of the parameter within the AbstractModel. Keys on the second 
            level have to be filename, index and param.

            # TODO: Methode für das Anlegen/Kontrollieren von dem dict 
            erstellen.

        """
        self.timeseries_data = DataPortal()

        for key in timeseries_data_dict:
            self.timeseries_data.load(
                filename=timeseries_data_dict[key]['filename'],
                index=timeseries_data_dict[key]['index'],
                param=key
            )
    

    def prepare_asset_data(self, asset_data_dict):
        """Declare asset data for the optimization model."""
        self.asset_data = {}
    
        for key, value in asset_data_dict.items():
            self.asset_data[key] = pd.read_csv(
                value,
                index_col=0
            )
    

    def add_asset_object(self, asset_name, asset_object):
        """Adds a asset constructor object to the model."""
        self.asset_objects[asset_name] = asset_object


    def add_model_component(self, component_name, component):
        """Adds a pyomo component to the model."""
        self.model.add_component(component_name, component)


    def add_instance_component(self, component_name, component):
        """Adds a pyomo component to the model instance."""
        self.instance.add_component(component_name, component)


    def instantiate(self):
        """Creates a concrete model from the abstract model."""
        self.instance = self.model.create_instance(self.timeseries_data)


    def transform(self):
        """Expands arcs and generate connection constraints."""
        TransformationFactory('network.expand_arcs').apply_to(self.instance)
    

    def solve(self):
        """Solves the optimization problem."""
        self.results = self.solver.solve(
            self.instance,
            symbolic_solver_labels=True,
            tee=True,
            logfile=PATH_OUT + 'solver.log', 
            load_solutions=True,
            report_timing=True)

    def write_results(self):
        """Writes the resulting time series to a dataframe."""
        self.results.write()

        df_variables = pd.DataFrame()
        df_parameters = pd.DataFrame()
        df_output = pd.DataFrame()

        for parameter in self.instance.component_objects(Param, active=True):
            name = parameter.name
            if 'hydrogen_admixture_factor' in name:
                continue
            df_parameters[name] = [value(parameter[t]) for t in self.instance.t]
        
        for variable in self.instance.component_objects(Var, active=True):
            name = variable.name
            if 'aux' in name:   # Filters auxiliary variables from the output data
                continue
            if 'splitfrac' in name:
                continue
            df_variables[name] = [value(variable[t]) for t in self.instance.t]

        df_output = pd.concat([df_parameters, df_variables], axis=1)
        df_output.index = self.instance.t
        df_output.index.name = 't'

        self.result_data = df_output
    

    def save_result_data(self, filepath):
        """Saves the result data as csv to the given file path"""
        self.result_data.to_csv(filepath)


if __name__ == "__main__":
    model = Model()

    model.set_solver(
        solver_name='gurobi',
        TimeLimit=1800,    # solver will stop after x seconds
        MIPGap=0.01)       # solver will stop if gap <= 1%
    
    timeseries_data_dict = {
        'gas_price' : {
            # 'filename' : PATH_IN + 'prices/dummy/gas_price.csv',
            'filename' : PATH_IN + 'prices/gee23/gas_price_2024.csv',
            'index' : 't'
            },
        'power_price' : {
            # 'filename' : PATH_IN + 'prices/dummy/power_price.csv',
            'filename' : PATH_IN + 'prices/gee23/power_price_2024.csv',
            'index' : 't'
            },
        'heat_demand' : {
            # 'filename' : PATH_IN + 'demands/heat_short.csv',
            'filename' : PATH_IN + 'demands/heat.csv',
            'index' : 't'
        }
    }

    asset_data_dict = {
        'chp' : PATH_IN + 'assets/chp.csv',
        'electrical_grid' : PATH_IN + 'assets/electrical_grid.csv',
        'battery_storage' : PATH_IN + 'assets/battery_storage.csv',
        'pv' : PATH_IN + 'assets/pv.csv',
        'pv_capacity_factors' : PATH_IN + 'pv_capacity_factors/leipzig_t45_a180.csv',
        'electrolyzer' : PATH_IN + 'assets/electrolyzer.csv',
        'hydrogen_grid' : PATH_IN + 'assets/hydrogen_grid.csv',
        'heatpump' : PATH_IN + 'assets/heatpump.csv',
        'heat_grid' : PATH_IN + 'assets/heat_grid.csv',
        'heat_storage' : PATH_IN + 'assets/heat_storage.csv'
    }

    model.prepare_timeseries_data(timeseries_data_dict)
    model.prepare_asset_data(asset_data_dict)

    model.add_asset_object(
        asset_name='chp',
        asset_object=chp.Chp(
            data=model.asset_data['chp'],
            hydrogen_admixture=0.0
        )
    )
    model.add_asset_object(
        asset_name='electrical_grid',
        asset_object=grid.Grid(
            data=model.asset_data['electrical_grid']
        )
    )
    model.add_asset_object(
        asset_name='battery_storage',
        asset_object=storage.BatteryStorage(
            data=model.asset_data['battery_storage']
            )
    )
    model.add_asset_object(
        asset_name='pv',
        asset_object=res.Photovoltaics(
            data=model.asset_data['pv'],
            capacity_factors=model.asset_data['pv_capacity_factors']
        )
    )
    model.add_asset_object(
        asset_name='electrolyzer',
        asset_object=elec.Electrolyzer(
            data=model.asset_data['electrolyzer']
        )
    )
    model.add_asset_object(
        asset_name='hydrogen_grid',
        asset_object=grid.Grid(
            data=model.asset_data['hydrogen_grid']
        )
    )
    model.add_asset_object(
        asset_name='ngas_grid',
        asset_object=grid.Grid()
    )
    model.add_asset_object(
        asset_name='heatpump',
        asset_object=hp.Heatpump(
            data=model.asset_data['heatpump']
        )
    )
    model.add_asset_object(
        asset_name='heat_grid',
        asset_object=grid.Grid(
            data=model.asset_data['heat_grid']
        )
    )
    model.add_asset_object(
        asset_name='heat_storage',
        asset_object=storage.HeatStorage(
            data=model.asset_data['heat_storage']
        )
    )

    # Define sets
    model.add_model_component(
        component_name='t',
        component=Set(ordered=True)
    )

    # Define parameters
    model.add_model_component(
        component_name='gas_price',
        component=Param(model.model.t)
    )
    model.add_model_component(
        component_name='power_price',
        component=Param(model.model.t)
    )
    model.add_model_component(
        component_name='heat_demand',
        component=Param(model.model.t)
    )

    # Define block components
    model.add_model_component(
        component_name='chp_1',
        component=Block(
            rule=model.asset_objects['chp'].chp_block_rule
        )
    )
    model.add_model_component(
        component_name='chp_2',
        component=Block(
            rule=model.asset_objects['chp'].chp_block_rule
        )
    )
    model.add_model_component(
        component_name='electrical_grid',
        component=Block(
            rule=model.asset_objects['electrical_grid'].electrical_grid_block_rule
        )
    )
    model.add_model_component(
        component_name='battery_storage',
        component=Block(
            rule=model.asset_objects['battery_storage'].battery_storage_block_rule
        )
    )
    model.add_model_component(
        component_name='pv',
        component=Block(
            rule=model.asset_objects['pv'].pv_block_rule
        )
    )
    model.add_model_component(
        component_name='electrolyzer_1',
        component=Block(
            rule=model.asset_objects['electrolyzer'].electrolyzer_block_rule
        )
    )
    model.add_model_component(
        component_name='electrolyzer_2',
        component=Block(
            rule=model.asset_objects['electrolyzer'].electrolyzer_block_rule
        )
    )
    model.add_model_component(
        component_name='electrolyzer_3',
        component=Block(
            rule=model.asset_objects['electrolyzer'].electrolyzer_block_rule
        )
    )
    model.add_model_component(
        component_name='electrolyzer_4',
        component=Block(
            rule=model.asset_objects['electrolyzer'].electrolyzer_block_rule
        )
    )
    model.add_model_component(
        component_name='electrolyzer_5',
        component=Block(
            rule=model.asset_objects['electrolyzer'].electrolyzer_block_rule
        )
    )
    model.add_model_component(
        component_name='electrolyzer_6',
        component=Block(
            rule=model.asset_objects['electrolyzer'].electrolyzer_block_rule
        )
    )
    model.add_model_component(
        component_name='hydrogen_grid',
        component=Block(
            rule=model.asset_objects['hydrogen_grid'].hydrogen_grid_block_rule
        )
    )
    model.add_model_component(
        component_name='ngas_grid',
        component=Block(
            rule=model.asset_objects['ngas_grid'].natural_gas_grid_block_rule
        )
    )
    model.add_model_component(
        component_name='heatpump',
        component=Block(
            rule=model.asset_objects['heatpump'].heatpump_block_rule
        )
    )
    model.add_model_component(
        component_name='heat_grid',
        component=Block(
            rule=model.asset_objects['heat_grid'].heat_grid_block_rule
        )
    )
    model.add_model_component(
        component_name='heat_storage',
        component=Block(
            rule=model.asset_objects['heat_storage'].heat_storage_block_rule
        )
    )

    # Define Objective
    print('DECLARING OBJECTIVE...')
    def obj_expression(m):
        """ Objective Function """
        return (quicksum(m.ngas_grid.ngas_balance[t] * m.gas_price[t] for t in m.t) +
                quicksum(m.chp_1.co2[t] * CO2_PRICE for t in m.t) +
                quicksum(m.chp_2.co2[t] * CO2_PRICE for t in m.t) +
                quicksum(m.electrical_grid.power_balance[t] * m.power_price[t] for t in m.t) +
                quicksum(m.hydrogen_grid.hydrogen_balance[t] * H2_PRICE for t in m.t) -
                quicksum(m.heat_grid.heat_feedin[t] * HEAT_PRICE for t in m.t))

    model.add_model_component(
        component_name='obj',
        component=Objective(
            rule=obj_expression,
            sense=minimize
        )
    )

    # Create instance
    print('CREATING INSTANCE...')
    model.instantiate()


    # Define arcs
    print('DECLARING ARCS...')
    model.add_instance_component(
        component_name='arc01',
        component=Arc(
            source=model.instance.chp_1.power_out,
            destination=model.instance.electrical_grid.power_in
        )
    )
    model.add_instance_component(
        component_name='arc02',
        component=Arc(
            source=model.instance.chp_2.power_out,
            destination=model.instance.electrical_grid.power_in
        )
    )
    model.add_instance_component(
        component_name='arc03',
        component=Arc(
            source=model.instance.pv.power_out,
            destination=model.instance.electrical_grid.power_in
        )
    )
    model.add_instance_component(
        component_name='arc04',
        component=Arc(
            source=model.instance.battery_storage.power_out,
            destination=model.instance.electrical_grid.power_in
        )
    )
    model.add_instance_component(
        component_name='arc05',
        component=Arc(
            source=model.instance.electrical_grid.power_out,
            destination=model.instance.battery_storage.power_in
        )
    )
    model.add_instance_component(
        component_name='arc06',
        component=Arc(
            source=model.instance.electrical_grid.power_out,
            destination=model.instance.electrolyzer_1.power_in
        )
    )
    model.add_instance_component(
        component_name='arc07',
        component=Arc(
            source=model.instance.electrical_grid.power_out,
            destination=model.instance.electrolyzer_2.power_in
        )
    )
    model.add_instance_component(
        component_name='arc08',
        component=Arc(
            source=model.instance.electrical_grid.power_out,
            destination=model.instance.electrolyzer_3.power_in
        )
    )
    model.add_instance_component(
        component_name='arc09',
        component=Arc(
            source=model.instance.electrical_grid.power_out,
            destination=model.instance.electrolyzer_4.power_in
        )
    )
    model.add_instance_component(
        component_name='arc10',
        component=Arc(
            source=model.instance.electrical_grid.power_out,
            destination=model.instance.electrolyzer_5.power_in
        )
    )
    model.add_instance_component(
        component_name='arc11',
        component=Arc(
            source=model.instance.electrical_grid.power_out,
            destination=model.instance.electrolyzer_6.power_in
        )
    )
    model.add_instance_component(
        component_name='arc12',
        component=Arc(
            source=model.instance.electrolyzer_1.hydrogen_out,
            destination=model.instance.hydrogen_grid.hydrogen_in
        )
    )
    model.add_instance_component(
        component_name='arc13',
        component=Arc(
            source=model.instance.electrolyzer_2.hydrogen_out,
            destination=model.instance.hydrogen_grid.hydrogen_in
        )
    )
    model.add_instance_component(
        component_name='arc14',
        component=Arc(
            source=model.instance.electrolyzer_3.hydrogen_out,
            destination=model.instance.hydrogen_grid.hydrogen_in
        )
    )
    model.add_instance_component(
        component_name='arc15',
        component=Arc(
            source=model.instance.electrolyzer_4.hydrogen_out,
            destination=model.instance.hydrogen_grid.hydrogen_in
        )
    )
    model.add_instance_component(
        component_name='arc16',
        component=Arc(
            source=model.instance.electrolyzer_5.hydrogen_out,
            destination=model.instance.hydrogen_grid.hydrogen_in
        )
    )
    model.add_instance_component(
        component_name='arc17',
        component=Arc(
            source=model.instance.electrolyzer_6.hydrogen_out,
            destination=model.instance.hydrogen_grid.hydrogen_in
        )
    )
    model.add_instance_component(
        component_name='arc18',
        component=Arc(
            source=model.instance.chp_1.natural_gas_in,
            destination=model.instance.ngas_grid.ngas_out
        )
    )
    model.add_instance_component(
        component_name='arc19',
        component=Arc(
            source=model.instance.chp_2.natural_gas_in,
            destination=model.instance.ngas_grid.ngas_out
        )
    )
    model.add_instance_component(
        component_name='arc20',
        component=Arc(
            source=model.instance.chp_1.hydrogen_in,
            destination=model.instance.hydrogen_grid.hydrogen_out
        )
    )
    model.add_instance_component(
        component_name='arc21',
        component=Arc(
            source=model.instance.chp_2.hydrogen_in,
            destination=model.instance.hydrogen_grid.hydrogen_out
        )
    )
    model.add_instance_component(
        component_name='arc22',
        component=Arc(
            source=model.instance.electrolyzer_1.heat_out,
            destination=model.instance.heatpump.heat_in
        )
    )
    model.add_instance_component(
        component_name='arc23',
        component=Arc(
            source=model.instance.electrolyzer_2.heat_out,
            destination=model.instance.heatpump.heat_in
        )
    )
    model.add_instance_component(
        component_name='arc24',
        component=Arc(
            source=model.instance.electrolyzer_3.heat_out,
            destination=model.instance.heatpump.heat_in
        )
    )
    model.add_instance_component(
        component_name='arc25',
        component=Arc(
            source=model.instance.electrolyzer_4.heat_out,
            destination=model.instance.heatpump.heat_in
        )
    )
    model.add_instance_component(
        component_name='arc26',
        component=Arc(
            source=model.instance.electrolyzer_5.heat_out,
            destination=model.instance.heatpump.heat_in
        )
    )
    model.add_instance_component(
        component_name='arc27',
        component=Arc(
            source=model.instance.electrolyzer_6.heat_out,
            destination=model.instance.heatpump.heat_in
        )
    )
    model.add_instance_component(
        component_name='arc28',
        component=Arc(
            source=model.instance.heatpump.heat_out,
            destination=model.instance.heat_grid.heat_in
        )
    )
    model.add_instance_component(
        component_name='arc29',
        component=Arc(
            source=model.instance.chp_1.heat_out,
            destination=model.instance.heat_grid.heat_in
        )
    )
    model.add_instance_component(
        component_name='arc30',
        component=Arc(
            source=model.instance.chp_2.heat_out,
            destination=model.instance.heat_grid.heat_in
        )
    )
    model.add_instance_component(
        component_name='arc31',
        component=Arc(
            source=model.instance.electrical_grid.power_out,
            destination=model.instance.heatpump.power_in
        )
    )
    model.add_instance_component(
        component_name='arc32',
        component=Arc(
            source=model.instance.heat_storage.heat_out,
            destination=model.instance.heat_grid.heat_in
        )
    )
    model.add_instance_component(
        component_name='arc33',
        component=Arc(
            source=model.instance.heat_grid.heat_out,
            destination=model.instance.heat_storage.heat_in
        )
    )

    model.transform()

    # Solve the optimization problem
    print('START SOLVING...')
    model.solve()

    model.write_results()
    model.save_result_data(PATH_OUT + 'output_time_series.csv')
