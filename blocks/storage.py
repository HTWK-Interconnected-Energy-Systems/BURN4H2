from pyomo.environ import *
from pyomo.network import *

import pandas as pd


class BatteryStorage:
    """Class for constructing battery storage asset objects."""

    def __init__(self, name, filepath, index_col=0, **kwargs) -> None:
        self.name = name
        self.get_data(filepath, index_col)
        self.kwargs = kwargs
        self.validate_kwargs()
    

    def validate_kwargs(self):
        """Checks for unknown kwargs and returns a KeyError if some are found."""
        allowed_kwargs = ['cyclic_behaviour']

        for key in self.kwargs:
            if key not in allowed_kwargs:
                raise(KeyError(f'Unexpected kwarg "{key}" detected.'))
    

    def get_data(self, filepath, index_col):
        """Collects data from a csv."""
        self.data = pd.read_csv(
            filepath,
            index_col=index_col
        )
    

    def add_to_model(self, model):
        """Adds the asset as a pyomo block component to a given model."""
        model.add_component(
            self.name,
            Block(rule=self.battery_storage_block_rule)
        )

    
    def battery_storage_block_rule(self, block):
        """Rule for creating a battery storage block with default components and constraints."""

        # Get index from model
        t = block.model().t
        
        # Declare components
        block.power_balance = Var(t, domain=Reals)
        block.power_charging = Var(t, domain=NonNegativeReals)
        block.power_discharging = Var(t, domain=NonNegativeReals)
        block.power_content = Var(t, domain=NonNegativeReals)
        block.bin_discharge = Var(t, within=Binary)
        block.bin_charge = Var(t, within=Binary)
        block.bin_switch = Var(t, within=Binary)

        # Auxiliary variables for calculating the modulo values in the switch constraints
        block.aux_remainder = Var(t, domain=Integers, bounds=(0,3))    
        block.aux_quotient = Var(t, domain=Integers, initialize=0)

        block.power_in = Port()
        block.power_in.add(block.power_charging, 'power', Port.Extensive, include_splitfrac=False)
        block.power_out = Port()
        block.power_out.add(block.power_discharging, 'power', Port.Extensive, include_splitfrac=False)


        # Declare construction rules for constraints
        def max_power_charging_rule(_block, i):
            """Rule for the maximal charging power."""
            return _block.power_charging[i] <= self.data.loc['max', 'power'] * _block.bin_charge[i]
                

        def max_power_discharging_rule(_block, i):
            """Rule for the maximal discharging power."""
            return _block.power_discharging[i] <= self.data.loc['max', 'power'] * _block.bin_discharge[i]


        def power_balance_rule(_block, i):
            """Rule for calculating the overall power balance."""
            return _block.power_balance[i] ==  _block.power_discharging[i] - _block.power_charging[i]


        def binary_rule(_block, i):
            """Rule for restricting simultaneous charging and discharging."""
            return _block.bin_charge[i] + _block.bin_discharge[i] == 1
        

        def max_power_content_rule(_block, i):
            """Rule for the maximal energy content of the battery storage."""
            return _block.power_content[i] <= self.data.loc['max', 'capacity']
        

        def min_power_content_rule(_block, i):
            """Rule for the minimal energy content of the battery storage."""
            return _block.power_content[i] >= self.data.loc['min', 'capacity']
        

        def actual_power_content_rule(_block, i):
            """Rule for calculating the actual energy content of the battery storage."""
            if i == 1:
                return _block.power_content[i] == 0 - _block.power_balance[i]
            else:
                return _block.power_content[i] == _block.power_content[i - 1] - _block.power_balance[i]


        def switch_from_charge_to_discharge_rule(_block, i):
            """Rule for determining the switch state when the storage operation changes from 
            charging to discharging."""
            if i == 1:
                return _block.bin_switch[i] == 0
            
            current_state = _block.bin_charge[i] - _block.bin_discharge[i]
            previous_state = _block.bin_charge[i - 1] - _block.bin_discharge[i - 1]
            switch_state = current_state - previous_state

            return switch_state >= -2 * _block.bin_switch[i]
        

        def switch_from_discharge_to_charge_rule(_block, i):
            """Rule for determining the switch state when the storage operation changes from
            discharging to charging."""
            if i == 1:
                return _block.bin_switch[i] == 0
        
            current_state = _block.bin_charge[i] - _block.bin_discharge[i]
            previous_state = _block.bin_charge[i - 1] - _block.bin_discharge[i - 1]
            switch_state = current_state - previous_state

            return 2 * _block.bin_switch[i] >= switch_state
        

        def no_operational_switch_rule(_block, i):
            """Rule for determining the switch state when the storage operation does not change."""
            if i == 1:
                return _block.bin_switch[i] == 0

            return _block.aux_remainder[i] * _block.bin_switch[i] == 0
        

        def modulo_switch_rule(_block, i):
            """Rule for the modulo operation for usage within the "no_operational_switch" rule."""
            if i == 1:
                return _block.aux_remainder[i] == 0
            
            current_state = _block.bin_charge[i] - _block.bin_discharge[i]
            previous_state = _block.bin_charge[i - 1] - _block.bin_discharge[i - 1]
            switch_state = current_state - previous_state + 2

            return switch_state == 4 * _block.aux_quotient[i] + _block.aux_remainder[i]


        # Declare constraints
        block.max_power_charging_constraint = Constraint(
            t,
            rule=max_power_charging_rule
        )
        block.max_power_discharging_constraint = Constraint(
            t,
            rule=max_power_discharging_rule
        )
        block.power_balance_constraint = Constraint(
            t,
            rule=power_balance_rule
        )
        block.binary_constraint = Constraint(
            t,
            rule=binary_rule
        )
        block.max_power_content_constraint = Constraint(
            t,
            rule=max_power_content_rule
        )
        block.min_power_content_constraint = Constraint(
            t,
            rule=min_power_content_rule
        )
        block.actual_power_content_constraint = Constraint(
            t,
            rule=actual_power_content_rule
        )
        block.switch_from_charge_to_discharge_constraint = Constraint(
            t,
            rule=switch_from_charge_to_discharge_rule
        )
        block.switch_from_discharge_to_charge_constraint = Constraint(
            t,
            rule=switch_from_discharge_to_charge_rule
        )
        block.no_operational_switch_constraint = Constraint(
            t,
            rule=no_operational_switch_rule
        )
        block.modulo_constraint = Constraint(
            t,
            rule=modulo_switch_rule
        )


        # Declare optional constraint via expression when right kwarg is given.
        if 'cyclic_behaviour' in self.kwargs:             
            
            block.cyclic_switch_bin = Var(t, within=Binary)
            kwarg_value = self.kwargs['cyclic_behaviour']

            def cyclic_switch_rule(_block, i):
                if (i - 1) % kwarg_value == 0:
                    return _block.cyclic_switch_bin[i] == 0
                
                return _block.cyclic_switch_bin[i] == _block.bin_switch[i]


            def cyclic_behaviour_rule(_block, i):

                if i % kwarg_value == 0:
                    return sum(_block.cyclic_switch_bin[j] for j in range(i, i - kwarg_value, -1)) <= 1
                else:
                    return Constraint.Skip
            

            block.cyclic_switch_constraint = Constraint(
                t,
                rule=cyclic_switch_rule
            )
            block.cyclic_behavior_constaint = Constraint(
                t,
                rule=cyclic_behaviour_rule
            )


class HydrogenStorage:
    """Class for constructing hydrogen storage asset objects."""

    def __init__(self, name, filepath, index_col=0) -> None:
        self.name = name
        self.get_data(filepath, index_col)


    def get_data(self, filepath, index_col):
        """Collects data from a csv."""
        self.data = pd.read_csv(
            filepath,
            index_col=index_col
        )
    

    def add_to_model(self, model):
        """Adds the asset as a pyomo block component to a given model."""
        model.add_component(
            self.name,
            Block(rule=self.hydrogen_storage_block_rule)
        )
    

    def hydrogen_storage_block_rule(self, block):
        """Rule for creating a hydrogen storage block with default components and constraints."""

        # Get index from model
        t = block.model().t
        
        # Declare components
        block.hydrogen_balance = Var(t, domain=Reals)
        block.hydrogen_charging = Var(t, domain=NonNegativeReals)
        block.hydrogen_discharging = Var(t, domain=NonNegativeReals)
        block.hydrogen_content = Var(t, domain=NonNegativeReals)
        block.bin_charge = Var(t, within=Binary)
        block.bin_discharge = Var(t, within=Binary)

        block.hydrogen_in = Port()
        block.hydrogen_in.add(block.hydrogen_charging, 'hydrogen', Port.Extensive, include_splitfrac=False)
        block.hydrogen_out = Port()
        block.hydrogen_out.add(block.hydrogen_discharging, 'hydrogen', Port.Extensive, include_splitfrac=False)


        # Declare construction rules for constraints
        def max_hydrogen_charging_rule(_block, i):
            """Rule for the maximum charging capacity of hydrogen."""
            return _block.hydrogen_charging[i] <= self.data.loc['max', 'hydrogen'] * _block.bin_charge[i]
                

        def max_hydrogen_discharging_rule(_block, i):
            """Rule for the maximum discharging capacity of hydrogen."""
            return _block.hydrogen_discharging[i] <= self.data.loc['max', 'hydrogen'] * _block.bin_discharge[i]


        def hydrogen_balance_rule(_block, i):
            """Rule for calculating the overall hydrogen capacity balance."""
            return _block.hydrogen_balance[i] == _block.hydrogen_discharging[i] - _block.hydrogen_charging[i]


        def binary_rule(_block, i):
            """Rule for restricting simultaneous charging and discharging."""
            return _block.bin_charge[i] + _block.bin_discharge[i] == 1
        

        def max_hydrogen_content_rule(_block, i):
            """Rule for the maximum amount of hydrogen in the hydrogen storage."""
            return _block.hydrogen_content[i] <= self.data.loc['max', 'content']
        

        def min_hydrogen_content_rule(_block, i):
            """Rule for the minimum amount of hydrogen in the hydrogen storage."""
            return _block.hydrogen_content[i] >= self.data.loc['min', 'content']
        

        def actual_hydrogen_content_rule(_block, i):
            """Rule for calculating the actual energy content of the hydrogen storage."""
            if i == 1:
                return _block.hydrogen_content[i] == 0 - _block.hydrogen_balance[i]
            else:
                return _block.hydrogen_content[i] == _block.hydrogen_content[i - 1] - _block.hydrogen_balance[i]


        # Declare constraints
        block.max_hydrogen_charging_constraint = Constraint(
            t,
            rule=max_hydrogen_charging_rule
        )
        block.max_hydrogen_discharging_constraint = Constraint(
            t,
            rule=max_hydrogen_discharging_rule
        )
        block.hydrogen_balance_constraint = Constraint(
            t,
            rule=hydrogen_balance_rule
        )
        block.binary_constraint = Constraint(
            t,
            rule=binary_rule
        )
        block.max_hydrogen_content_constraint = Constraint(
            t,
            rule=max_hydrogen_content_rule
        )
        block.min_hydrogen_content_constraint = Constraint(
            t,
            rule=min_hydrogen_content_rule
        )
        block.actual_hydrogen_content_rule = Constraint(
            t,
            rule=actual_hydrogen_content_rule
        )
    

class HeatStorage:
    """Class for constructing heat storage asset objects."""

    def __init__(self, name, filepath, index_col=0) -> None:
        self.name = name
        self.get_data(filepath, index_col)
    

    def get_data(self, filepath, index_col):
        """Collects data from a csv."""
        self.data = pd.read_csv(
            filepath,
            index_col=index_col
        )
    

    def add_to_model(self, model):
        """Adds the asset as a pyomo block component to a given model."""
        model.add_component(
            self.name,
            Block(rule=self.heat_storage_block_rule)
        )


    def heat_storage_block_rule(self, block):
        """Rule for creating a heat storage block with default components
        and constraints."""

        # Get index from model
        t = block.model().t

        # Declare components
        block.heat_balance = Var(t, domain=Reals)
        block.heat_charging = Var(t, domain=NonNegativeReals)
        block.heat_discharging = Var(t, domain=NonNegativeReals)
        block.heat_content = Var(t, domain=NonNegativeReals)
        block.bin_charge = Var(t, within=Binary)
        block.bin_discharge = Var(t, within=Binary)

        block.heat_in = Port()
        block.heat_in.add(block.heat_charging, 'heat', Port.Extensive, include_splitfrac=False)
        block.heat_out = Port()
        block.heat_out.add(block.heat_discharging, 'heat', Port.Extensive, include_splitfrac=False)


        # Declare construction rules for constraints
        def max_heat_charging_rule(_block, i):
            """Rule for the maximum charging capacity of heat."""
            return _block.heat_charging[i] <= self.data.loc['max', 'heat'] * _block.bin_charge[i]
                

        def max_heat_discharging_rule(_block, i):
            """Rule for the maximum discharging capacity of heat."""
            return _block.heat_discharging[i] <= self.data.loc['max', 'heat'] * _block.bin_discharge[i]


        def heat_balance_rule(_block, i):
            """Rule for calculating the overall heat balance."""
            return _block.heat_balance[i] == _block.heat_discharging[i] - _block.heat_charging[i]


        def binary_rule(_block, i):
            """Rule for restricting simultaneous charging and discharging."""
            return _block.bin_charge[i] + _block.bin_discharge[i] == 1
        

        def max_heat_content_rule(_block, i):
            """Rule for the maximum amount of heat in the heat storage."""
            return _block.heat_content[i] <= self.data.loc['max', 'content']
        

        def min_heat_content_rule(_block, i):
            """Rule for the minimum amount of heat in the heat storage."""
            return _block.heat_content[i] >= self.data.loc['min', 'content']
        

        def actual_heat_content_rule(_block, i):
            """Rule for calculating the actual energy content of the heat storage."""
            if i == 1:
                return _block.heat_content[i] == 0 - _block.heat_balance[i]
            else:
                return _block.heat_content[i] == _block.heat_content[i - 1] - _block.heat_balance[i]
        

        # Declare constraints
        block.max_heat_charging_constraint = Constraint(
            t,
            rule=max_heat_charging_rule
        )
        block.max_heat_discharging_constraint = Constraint(
            t,
            rule=max_heat_discharging_rule
        )
        block.heat_balance_constraint = Constraint(
            t,
            rule=heat_balance_rule
        )
        block.binary_constraint = Constraint(
            t,
            rule=binary_rule
        )
        block.max_heat_content_constraint = Constraint(
            t,
            rule=max_heat_content_rule
        )
        block.min_heat_content_rule = Constraint(
            t,
            rule=min_heat_content_rule
        )
        block.actual_heat_content_constraint = Constraint(
            t,
            rule=actual_heat_content_rule
        )

# class LocalHeatStorage:
#     """Class for constructing local heat storage asset objects."""

#     def __init__(self, name, filepath, index_col=0) -> None:
#         self.name = name
#         self.get_data(filepath, index_col)
    

#     def get_data(self, filepath, index_col):
#         """Collects data from a csv."""
#         self.data = pd.read_csv(
#             filepath,
#             index_col=index_col
#         )
    

#     def add_to_model(self, model):
#         """Adds the asset as a pyomo block component to a given model."""
#         model.add_component(
#             self.name,
#             Block(rule=self.heat_storage_block_rule)
#         )


#     def heat_storage_block_rule(self, block):
#         """Rule for creating a heat storage block with default components
#         and constraints."""

#         # Get index from model
#         t = block.model().t

#         # Declare components
#         block.heat_balance = Var(t, domain=Reals)
#         block.heat_charging = Var(t, domain=NonNegativeReals)
#         block.heat_discharging = Var(t, domain=NonNegativeReals)
#         block.excess_heat_discharging = Var(t, domain=NonNegativeReals)
        
#         block.heat_content = Var(t, domain=NonNegativeReals)
#         block.bin_charge = Var(t, within=Binary)
#         block.bin_discharge = Var(t, within=Binary)

#         block.heat_in = Port()
#         block.heat_in.add(block.heat_charging, 'local_heat', Port.Extensive, include_splitfrac=False)
        
#         block.heat_out = Port()
#         block.heat_out.add(block.heat_discharging, 'local_heat', Port.Extensive, include_splitfrac=False)
    
#         block.excess_heat_out = Port()
#         block.excess_heat_out.add(block.excess_heat_discharging, 'excess_heat', Port.Extensive, include_splitfrac=False)


        

#         # Declare construction rules for constraints
#         def max_heat_charging_rule(_block, i):
#             """Rule for the maximum charging capacity of heat."""
#             return _block.heat_charging[i] <= self.data.loc['max', 'heat'] * _block.bin_charge[i]
                
#         def max_heat_discharging_rule(_block, i):
#             """Rule for the maximum discharging capacity of heat."""
#             max_profile = max(value(_block.model().local_heat_demand[t]) for t in _block.model().t)
#             # print(max_profile)
#             return _block.heat_discharging[i] <= max_profile * _block.bin_discharge[i]
        
#         def max_excess_heat_discharging_rule(_block, i):
#             """Rule for the maximum discharging capacity of excess heat."""
#             max_profile = max(value(_block.model().local_heat_demand[t]) for t in _block.model().t)
#             return _block.excess_heat_discharging[i] <= max_profile * _block.bin_discharge[i]

#         block.max_excess_heat_discharging_constraint = Constraint(
#             t,
#             rule=max_excess_heat_discharging_rule
#         )

#         def heat_balance_rule(_block, i):
#             """Rule for calculating the overall heat balance."""
#             return _block.heat_balance[i] == _block.heat_discharging[i] + _block.excess_heat_discharging[i] - _block.heat_charging[i]

#         def max_heat_content_rule(_block, i):
#             """Rule for the maximum amount of heat in the heat storage."""
#             return _block.heat_content[i] <= self.data.loc['max', 'content']
        

#         def min_heat_content_rule(_block, i):
#             """Rule for the minimum amount of heat in the heat storage."""
#             return _block.heat_content[i] >= self.data.loc['min', 'content']
        

#         def actual_heat_content_rule(_block, i):
#             """Rule for calculating the actual energy content of the heat storage."""
#             if i == 1:
#                 return _block.heat_content[i] == 0 - _block.heat_balance[i]
#             else:
#                 return _block.heat_content[i] == _block.heat_content[i - 1] - _block.heat_balance[i]
        

#         # Declare constraints
#         block.max_heat_charging_constraint = Constraint(
#             t,
#             rule=max_heat_charging_rule
#         )
#         block.max_heat_discharging_constraint = Constraint(
#             t,
#             rule=max_heat_discharging_rule
#         )
#         block.heat_balance_constraint = Constraint(
#             t,
#             rule=heat_balance_rule
#         )
#         block.max_heat_content_constraint = Constraint(
#             t,
#             rule=max_heat_content_rule
#         )
#         block.min_heat_content_rule = Constraint(
#             t,
#             rule=min_heat_content_rule
#         )
#         block.actual_heat_content_constraint = Constraint(
#             t,
#             rule=actual_heat_content_rule
#         )
    
class GeoHeatStorage:
    """Class for constructing geo heat storage asset objects."""

    def __init__(self, name, filepath, index_col=0) -> None:
        self.name = name
        self.get_data(filepath, index_col)
    

    def get_data(self, filepath, index_col):
        """Collects data from a csv."""
        self.data = pd.read_csv(
            filepath,
            index_col=index_col
        )
    

    def add_to_model(self, model):
        """Adds the asset as a pyomo block component to a given model."""
        model.add_component(
            self.name,
            Block(rule=self.geo_heat_storage_block_rule)
        )


    def geo_heat_storage_block_rule(self, block):
        """Rule for creating a heat storage block with default components
        and constraints."""

        # Get index from model
        t = block.model().t

        # Declare components
        block.heat_balance = Var(t, domain=Reals)
        block.heat_charging = Var(t, domain=NonNegativeReals)
        block.heat_discharging = Var(t, domain=NonNegativeReals)
        block.heat_content = Var(t, domain=NonNegativeReals)
        block.bin_charge = Var(t, within=Binary)
        block.bin_discharge = Var(t, within=Binary)

        block.heat_in = Port()
        block.heat_in.add(block.heat_charging, 'waste_heat', Port.Extensive, include_splitfrac=False)
        block.heat_out = Port()
        block.heat_out.add(block.heat_discharging, 'waste_heat', Port.Extensive, include_splitfrac=False)


        # Declare construction rules for constraints
        def max_heat_charging_rule(_block, i):
            """Rule for the maximum charging capacity of heat."""
            return _block.heat_charging[i] <= self.data.loc['max', 'heat'] * _block.bin_charge[i]
                

        def max_heat_discharging_rule(_block, i):
            """Rule for the maximum discharging capacity of heat."""
            return _block.heat_discharging[i] <= self.data.loc['max', 'heat'] * _block.bin_discharge[i]


        def heat_balance_rule(_block, i):
            """Rule for calculating the overall heat balance."""
            return _block.heat_balance[i] == _block.heat_discharging[i] - _block.heat_charging[i]


        def binary_rule(_block, i):
            """Rule for restricting simultaneous charging and discharging."""
            return _block.bin_charge[i] + _block.bin_discharge[i] == 1
        

        def max_heat_content_rule(_block, i):
            """Rule for the maximum amount of heat in the heat storage."""
            return _block.heat_content[i] <= self.data.loc['max', 'content']
        

        def min_heat_content_rule(_block, i):
            """Rule for the minimum amount of heat in the heat storage."""
            return _block.heat_content[i] >= self.data.loc['min', 'content']
        

        def actual_heat_content_rule(_block, i):
            """Rule for calculating the actual energy content of the heat storage."""
            if i == 1:
                return _block.heat_content[i] == 0 - _block.heat_balance[i]
            else:
                return _block.heat_content[i] == _block.heat_content[i - 1] - _block.heat_balance[i]
        

        # Declare constraints
        block.max_heat_charging_constraint = Constraint(
            t,
            rule=max_heat_charging_rule 
        )
        block.max_heat_discharging_constraint = Constraint(
            t,
            rule=max_heat_discharging_rule
        )
        block.heat_balance_constraint = Constraint(
            t,
            rule=heat_balance_rule
        )
        # block.binary_constraint = Constraint(
        #     t,
        #     rule=binary_rule
        # )
        block.max_heat_content_constraint = Constraint(
            t,
            rule=max_heat_content_rule
        )
        block.min_heat_content_rule = Constraint(
            t,
            rule=min_heat_content_rule
        )
        block.actual_heat_content_constraint = Constraint(
            t,
            rule=actual_heat_content_rule
        )

# Version 1

# class StratifiedHeatStorage:
#     """Class for constructing stratified heat storage asset objects."""

#     def __init__(self, name, filepath, index_col=0) -> None:
#         self.name = name
#         self.get_data(filepath, index_col)

#     def get_data(self, filepath, index_col):
#         """Collects data from a csv."""
#         self.data = pd.read_csv(
#             filepath,
#             index_col=index_col
#         )
    
#     def add_to_model(self, model):
#         """Adds the asset as a pyomo block component to a given model."""
#         model.add_component(
#             self.name,
#             Block(rule=self.stratified_storage_block_rule)
#         )

#     def stratified_storage_block_rule(self, block):
#         """Rule for creating a stratified heat storage block with default components
#         and constraints."""

#         # Get index from model
#         t = block.model().t # [hours]
#         temp_sup_C = block.model().supply_temperature # [°C] 
#         temp_ret_C = block.model().return_temperature # [°C]

#         # Conversionfactor from seconds to hours
#         block.sec_to_hour = Param(initialize=3600) # [s/h]

#         # Set Layers
#         block.layers = Set(initialize=[1, 2, 3])
        
#         # Spezifiscer Wärmekapazität von Wasser in MJ/kg·K für MW-Berechnung
#         block.c_w = Param(initialize=4.1218 / 1000)  # [MJ/(kg·K)], konvertiert von kJ/(kg·K)

#         # Masse jeder Schicht in kg
#         block.m_sto = Param(block.layers, initialize={
#             1: 2000000/3, 
#             2: 2000000/3, 
#             3: 2000000/3})  # [kg] laut Gabriel Schumm 2000 m³, dh 2 Mio kg bei Dichte 1000 kg/m³ für Wasser


#         # Initial temperature of each layer in K
#         block.T_sto_init = Param(block.layers, initialize={
#             1: 95 + 273.15, # [K] 
#             2: 80 + 273.15, # [K]
#             3: 55 + 273.15})  # [K]
        
#         # Zeitschritt
#         block.delta_t = Param(initialize=1)  # [h]

#         # Fernwärmenetz
#         block.T_supply_FW = Param(initialize=95 + 273.15)  # [K] konstante Vorlauftemperatur der Fernwärme
#         block.T_return_FW = Param(initialize=55 + 273.15)  # [K] konstante Rücklauftemperatur der Fernwärme

#         # Convert temperatures to K
#         def temp_C_to_K(temp_C):
#             return temp_C + 273.15 if temp_C is not None else None
    
#         # Temperatur des Rücklaufs und Vorlaufs in Kelvin
#         def get_temp_ret_K(_block, i):
#             return temp_C_to_K(temp_ret_C[i])
        
#         def get_temp_sup_K(_block, i):
#             return temp_C_to_K(temp_sup_C[i])
        
#         # Temperature of each layer
#         block.T_sto = Var(t, block.layers, domain=NonNegativeReals) # [K]
        
#         # Temperatur des Rücklaufs und Vorlaufs in Kelvin
#         # Nahwärmenetz
#         block.T_return_NW = Expression(t, rule=get_temp_ret_K)  # [K]
#         block.T_supply_NW = Expression(t, rule=get_temp_sup_K)  # [K]

#         # Massenströme und Wärmeeinträge
#         block.Q_dot_ST = Var(t, domain=NonNegativeReals)   # Wärmeeintrag durch Solarthermie [MW]
#         block.Q_dot_WP = Var(t, domain=NonNegativeReals)   # Wärmeeintrag durch Wärmepumpe [MW]
#         block.Q_dot_NW_out = Var(t, domain=NonNegativeReals)  # Wärmeabgabe an Nahwärmenetz [MW]
#         block.Q_dot_FW_out = Var(t, domain=NonNegativeReals)  # Wärmeabgabe an Fernwärmenetz [MW]
#         block.Q_dot_FW_in = Var(t, domain=NonNegativeReals)  # Wärmeeintrag durch Fernwärme [MW]
#         block.m_dot_STO_out = Var(t, domain=NonNegativeReals)  # Massenstrom in Nahwärme [kg/s]

#         # Ports für die Wärmeeingänge
#         # Solar-Thermie Eingang (obere Schicht)
#         block.st_heat_in = Port()
#         block.st_heat_in.add(block.Q_dot_ST, 'st_heat', Port.Extensive, include_splitfrac=False)
        
#         # Wärmepumpen-Eingang (mittlere Schicht)
#         block.wp_heat_in = Port()
#         block.wp_heat_in.add(block.Q_dot_WP, 'wp_heat', Port.Extensive, include_splitfrac=False)
        

#         # Ports für die Wärmeausgänge 
#         # Wärmeabgabe an das Nahwärmenetz 
#         block.nw_heat_out = Port()
#         block.nw_heat_out.add(block.Q_dot_NW_out, 'local_heat', Port.Extensive, include_splitfrac=False)

#         # Wärmeabgabe an das Fernwärmenetz 
#         block.fw_heat_out = Port()
#         block.fw_heat_out.add(block.Q_dot_FW_out, 'excess_heat', Port.Extensive, include_splitfrac=False)
     
#         # Port für Wärmeeingang nach dem Speicher 
#         # Fernwärme-Eingang 
#         block.fw_heat_in = Port()
#         block.fw_heat_in.add(block.Q_dot_FW_in, 'fw_heat', Port.Extensive, include_splitfrac=False)

#         # Expression 
#         def m_dot_FW_in_rule(_block, i):
#             return (_block.Q_dot_FW_in[i] / (_block.c_w * (_block.T_supply_FW - _block.T_return_FW)))
        
#         block.m_dot_FW_in = Expression(
#             t,
#             rule=m_dot_FW_in_rule
#         )
        
#         def m_dot_FW_out_rule(_block, i):
#             return (_block.Q_dot_FW_out[i] / (_block.c_w * (_block.T_supply_FW - _block.T_return_FW)))
        
#         block.m_dot_FW_out = Expression(
#             t,
#             rule=m_dot_FW_out_rule
#         )

#         def m_dot_NW_out_rule(_block, i):
#             return (_block.Q_dot_NW_out[i] / (_block.c_w * (_block.T_supply_NW[i] - _block.T_return_NW[i])))
        
#         block.m_dot_NW_out = Expression(
#             t,
#             rule=m_dot_NW_out_rule
#         )

#         # Constraints
#         # Constraint for the mass flow bilanz at the outlet
#         def mass_flow_rule(_block, i):
#             return _block.m_dot_FW_in[i] + _block.m_dot_STO_out[i] == _block.m_dot_FW_out[i] + _block.m_dot_NW_out[i]
        
#         block.mass_flow = Constraint(
#             t,  
#             rule=mass_flow_rule
#         )

#         def ST_excess_heat_rule(_block, i):
#             return block.m_dot_FW_out[i] == 0
        
#         block.ST_excess_heat = Constraint(
#             t, 
#             rule=ST_excess_heat_rule
#         )
        
#         def m_dot_STO_out_rule(_block, i):
#             return _block.m_dot_STO_out[i] ==  _block.Q_dot_NW_out[i] / (_block.c_w * (_block.T_supply_NW[i] - _block.T_return_NW[i]))

#         block.m_dot_STO_out_x = Constraint(
#             t, 
#             rule=m_dot_STO_out_rule
#         )

#         # Constraint für die Energiebilanz im Speicher
#         # Obere Schicht (l=1)
#         def upper_layer_energy_balance_rule(_block, i):
#             if i == 1:
#                 # Initial condition
#                 return _block.T_sto[i, 1] == _block.T_sto_init[1]  # Starttemperatur [K]
#             else:
#                 # Energieänderung [MJ] = [kg] * [MJ/(kg·K)] * [K]
#                 energy_change = _block.m_sto[1] * _block.c_w * (_block.T_sto[i, 1] - _block.T_sto[i-1, 1])
                
#                 # Konvektionsterm: [MJ/(kg·K)] * [kg/s] * [K] * [s/h] * [h] = [MJ]
#                 convection = _block.c_w * _block.m_dot_STO_out[i] * (_block.T_sto[i, 2] - _block.T_sto[i, 1]) * _block.sec_to_hour * _block.delta_t
                
#                 # Solarthermie: [MW] * [h] * [MJ/MWh] = [MJ]
#                 solar_heat = _block.Q_dot_ST[i] * _block.delta_t * 3600

#                 return energy_change == convection + solar_heat
            

#         # Mittlere Schicht (l=2)
#         def middle_layer_energy_balance_rule(_block, i):
#             if i == 1:
#                 # Initial condition
#                 return _block.T_sto[i, 2] == _block.T_sto_init[2]  # Starttemperatur [K]
#             else:
#                 # Energieänderung [MJ]
#                 energy_change = _block.m_sto[2] * _block.c_w * (_block.T_sto[i, 2] - _block.T_sto[i-1, 2])
                
#                 # Konvektionsterme [MJ]
#                 convection = _block.c_w * _block.m_dot_STO_out[i] * (_block.T_sto[i, 3] - _block.T_sto[i, 2]) * _block.sec_to_hour * _block.delta_t
                
#                 # Wärmepumpe [MJ]
#                 heat_pump = _block.Q_dot_WP[i] * _block.delta_t * 3600
                
#                 return energy_change == convection + heat_pump
        
#         # Untere Schicht (l=3)
#         def lower_layer_energy_balance_rule(_block, i):
#             if i == 1:
#                  # Initial condition - wie bei den anderen Schichten
#                 return _block.T_sto[i, 3] == _block.T_sto_init[3]  # Starttemperatur [K]
#             else:
#                 # Energieänderung [MJ]
#                 energy_change = _block.m_sto[3] * _block.c_w * (_block.T_sto[i, 3] - _block.T_sto[i-1, 3])
                
#                 # Konvektionsterme [MJ]
#                 convection = _block.c_w * _block.m_dot_STO_out[i] * (_block.T_return_NW[i] - _block.T_sto[i, 3]) * _block.sec_to_hour * _block.delta_t
                
                
#                 return energy_change == convection
        
#         # Temperaturschichtungs-Constraints [K]
#         def temp_startification_upper_supply_rule_max(_block, i):
#             return _block.T_sto[i, 1] <= 98 + 273.15  # [K] max. Temperatur der oberen Schicht 

#         def temp_startification_upper_supply_rule_min(_block, i):
#             return _block.T_sto[i, 1] >= _block.T_supply_NW[i] 
        
#         def temp_stratification_upper_middle_rule(_block, i):
#             return _block.T_sto[i, 1] >= _block.T_sto[i, 2]
        
#         def temp_stratification_middle_lower_rule(_block, i):
#             return _block.T_sto[i, 2] >= _block.T_sto[i, 3]
        
#         def temp_stratification_lower_return_rule(_block, i):
#             return _block.T_sto[i, 3] >= _block.T_return_NW[i]
        
    

#         # Variable
#         block.bin_fw_in = Var(t, within=Binary)  # Binary variable for the mass flow in the storage
#         block.bin_fw_out = Var(t, within=Binary)  # Binary variable for the mass flow out of the storage

#         def max_massflow_fw_in_rule(_block, i):
#             max_Q = 100
#             return _block.Q_dot_FW_in[i] <= max_Q * _block.bin_fw_in[i]
        
#         def max_massflow_fw_out_rule(_block, i):
#             max_Q = 100
#             return _block.Q_dot_FW_out[i] <= max_Q * _block.bin_fw_out[i]
        
#         def Q_binary_rule(_block, i):
#             return _block.bin_fw_in[i] + _block.bin_fw_out[i] == 1
        
        
#         # block.max_massflow_fw_in = Constraint(
#         #     t,
#         #     rule=max_massflow_fw_in_rule
#         # )

#         # block.max_massflow_fw_out = Constraint(
#         #     t,
#         #     rule=max_massflow_fw_out_rule
#         # )
        
#         # block.Q_binary = Constraint(
#         #     t,
#         #     rule=Q_binary_rule
#         # )

#         # Create constraints
#         block.upper_layer_balance = Constraint(
#             t,
#             rule=upper_layer_energy_balance_rule
#         )
        
#         block.middle_layer_balance = Constraint(
#             t,
#             rule=middle_layer_energy_balance_rule
#         )
        
#         block.lower_layer_balance = Constraint(
#             t,
#             rule=lower_layer_energy_balance_rule
#         )
        
#         block.temp_stratification_1 = Constraint(
#             t,
#             rule=temp_stratification_upper_middle_rule
#         )
        
#         block.temp_stratification_2 = Constraint(
#             t,
#             rule=temp_stratification_middle_lower_rule
#         )
        
#         block.temp_stratification_3 = Constraint(
#             t,
#             rule=temp_stratification_lower_return_rule
#         )

#         block.temp_stratification_4 = Constraint(
#             t,
#             rule=temp_startification_upper_supply_rule_max
#         )

#         # block.temp_stratification_5 = Constraint(
#         #     t,
#         #     rule=temp_startification_upper_supply_rule_min
#         # )
        
#         # block.max_massflow_constraint = Constraint(
#         #     t,
#         #     rule=max_massflow_rule
#         # )   


#         # Constraint für die Energiebilanz am Ausgangsstrang
#         # def energy_balance_outlet_rule(_block, i):
#         #     return _block.Q_dot_FW_in[i] + block.Q_dot_STO_out[i] == _block.Q_dot_FW_out[i] + _block.Q_dot_NW_out[i]
        
#         # block.energy_balance_outlet = Constraint(
#         #     t,
#         #     rule=energy_balance_outlet_rule
#         # )

#         # # Time when feed-in of heat in distict heating network is not possible
#         # block.no_feed_in_periods = Set(initilaize=[24, 25, 26, 27, 28, 29, 30]) # [h]
        
#         # # Constraint für die Fernwärmeeinspeisung-Beschränkung
#         # def fw_feed_restriction_rule(_block, i):
#         #     if i in _block.no_feed_periods:
#         #         return _block.Q_dot_FW[i] == 0
#         #     else:
#         #         return Constraint.Skip

#         # block.fw_feed_restriction = Constraint(
#         #     t,
#         #     rule=fw_feed_restriction_rule
#         # )

# Version 2

# class StratifiedHeatStorage:
#     """Class for constructing stratified heat storage asset objects."""

#     def __init__(self, name, filepath, index_col=0) -> None:
#         self.name = name
#         self.get_data(filepath, index_col)

#     def get_data(self, filepath, index_col):
#         """Collects data from a csv."""
#         self.data = pd.read_csv(
#             filepath,
#             index_col=index_col
#         )
    
#     def add_to_model(self, model):
#         """Adds the asset as a pyomo block component to a given model."""
#         model.add_component(
#             self.name,
#             Block(rule=self.stratified_storage_block_rule)
#         )

#     def stratified_storage_block_rule(self, block):
#         """Rule for creating a stratified heat storage block with default components
#         and constraints."""

#         # Get index from model
#         t = block.model().t # [hours]
#         temp_sup_C = block.model().supply_temperature # [°C] 
#         temp_ret_C = block.model().return_temperature # [°C]

#         # Conversionfactor from seconds to hours
#         block.sec_to_hour = Param(initialize=3600) # [s/h]

#         # Set Layers
#         block.layers = Set(initialize=[1, 2, 3])
        
#         # Spezifiscer Wärmekapazität von Wasser in MJ/kg·K für MW-Berechnung
#         block.c_w = Param(initialize=4.1218 / 1000)  # [MJ/(kg·K)], konvertiert von kJ/(kg·K)

#         # Masse jeder Schicht in kg
#         block.m_sto = Param(block.layers, initialize={
#             1: 2000000/3, 
#             2: 2000000/3, 
#             3: 2000000/3})  # [kg] laut Gabriel Schumm 2000 m³, dh 2 Mio kg bei Dichte 1000 kg/m³ für Wasser

#         # Initial temperature of each layer in K
#         block.T_sto_init = Param(block.layers, initialize={
#             1: 95 + 273.15, # [K] 
#             2: 80 + 273.15, # [K]
#             3: 55 + 273.15})  # [K]
        
#         # Zeitschritt
#         block.delta_t = Param(initialize=1)  # [h]

#         # Fernwärmenetz
#         block.T_supply_FW = Param(initialize=95 + 273.15)  # [K] konstante Vorlauftemperatur der Fernwärme
#         block.T_return_FW = Param(initialize=55 + 273.15)  # [K] konstante Rücklauftemperatur der Fernwärme

#         # Convert temperatures to K
#         def temp_C_to_K(temp_C):
#             return temp_C + 273.15 if temp_C is not None else None
    
#         # Temperatur des Rücklaufs und Vorlaufs in Kelvin
#         def get_temp_ret_K(_block, i):
#             return temp_C_to_K(temp_ret_C[i])
        
#         def get_temp_sup_K(_block, i):
#             return temp_C_to_K(temp_sup_C[i])
        
#         # Temperature of each layer
#         block.T_sto = Var(t, block.layers, domain=NonNegativeReals) # [K]
        
#         # Temperatur des Rücklaufs und Vorlaufs in Kelvin
#         # Nahwärmenetz
#         block.T_return_NW = Expression(t, rule=get_temp_ret_K)  # [K]
#         block.T_supply_NW = Expression(t, rule=get_temp_sup_K)  # [K]

#         # Wärmeleistungseinträge
#         block.Q_dot_ST = Var(t, domain=NonNegativeReals)   # Wärmeeintrag durch Solarthermie [MW]
#         block.Q_dot_WP = Var(t, domain=NonNegativeReals)   # Wärmeeintrag durch Wärmepumpe [MW]
#         block.Q_dot_NW_out = Var(t, domain=NonNegativeReals)  # Wärmeabgabe an Nahwärmenetz [MW]
#         block.Q_dot_FW_out = Var(t, domain=NonNegativeReals)  # Wärmeabgabe an Fernwärmenetz [MW]
#         block.Q_dot_FW_in = Var(t, domain=NonNegativeReals)  # Wärmeeintrag durch Fernwärme [MW]
        
#         # Massenströme als Parameter - wichtig für Linearisierung
#         block.m_dot_STO_out = Var(t, domain=NonNegativeReals)  # Massenstrom in Nahwärme [kg/s]
        
#         # Hilfsvariablen für die Linearisierung - Wärmeflüsse zwischen Schichten [MW]
#         block.Q_conv_1_2 = Var(t, domain=Reals)  # Wärmefluss zwischen Schicht 1 und 2
#         block.Q_conv_2_3 = Var(t, domain=Reals)  # Wärmefluss zwischen Schicht 2 und 3
#         block.Q_conv_3_ret = Var(t, domain=Reals)  # Wärmefluss zwischen Schicht 3 und Rücklauf

#         # Ports für die Wärmeeingänge
#         block.st_heat_in = Port()
#         block.st_heat_in.add(block.Q_dot_ST, 'st_heat', Port.Extensive, include_splitfrac=False)
        
#         block.wp_heat_in = Port()
#         block.wp_heat_in.add(block.Q_dot_WP, 'wp_heat', Port.Extensive, include_splitfrac=False)
        
#         # Ports für die Wärmeausgänge 
#         block.nw_heat_out = Port()
#         block.nw_heat_out.add(block.Q_dot_NW_out, 'local_heat', Port.Extensive, include_splitfrac=False)

#         block.fw_heat_out = Port()
#         block.fw_heat_out.add(block.Q_dot_FW_out, 'excess_heat', Port.Extensive, include_splitfrac=False)
     
#         # Port für Wärmeeingang
#         block.fw_heat_in = Port()
#         block.fw_heat_in.add(block.Q_dot_FW_in, 'fw_heat', Port.Extensive, include_splitfrac=False)

#         # Massenströme über Expressions definieren
#         def m_dot_FW_in_rule(_block, i):
#             return (_block.Q_dot_FW_in[i] / (_block.c_w * (_block.T_supply_FW - _block.T_return_FW)))
        
#         block.m_dot_FW_in = Expression(t, rule=m_dot_FW_in_rule)
        
#         def m_dot_FW_out_rule(_block, i):
#             return (_block.Q_dot_FW_out[i] / (_block.c_w * (_block.T_supply_FW - _block.T_return_FW)))
        
#         block.m_dot_FW_out = Expression(t, rule=m_dot_FW_out_rule)

#         def m_dot_NW_out_rule(_block, i):
#             return (_block.Q_dot_NW_out[i] / (_block.c_w * (_block.T_supply_NW[i] - _block.T_return_NW[i])))
        
#         block.m_dot_NW_out = Expression(t, rule=m_dot_NW_out_rule)

#         # Constraints

#         # Massenbilanz
#         def mass_flow_rule(_block, i):
#             return _block.m_dot_FW_in[i] + _block.m_dot_STO_out[i] == _block.m_dot_FW_out[i] + _block.m_dot_NW_out[i]
        
#         block.mass_flow = Constraint(t, rule=mass_flow_rule)

#         # Annahme: Kein Fernwärmeausspeichern in diesem Modell
#         def ST_excess_heat_rule(_block, i):
#             return block.m_dot_FW_out[i] == 0
        
#         # block.ST_excess_heat = Constraint(t, rule=ST_excess_heat_rule)
        
#         # Berechnung des Massenstroms aus dem Speicher
#         def m_dot_STO_out_rule(_block, i):
#             delta_T_NW = _block.T_supply_NW[i] - _block.T_return_NW[i]
#             return _block.m_dot_STO_out[i] * _block.c_w * delta_T_NW == _block.Q_dot_NW_out[i]
        
#         block.m_dot_STO_out_constraint = Constraint(t, rule=m_dot_STO_out_rule)

#         # LINEARISIERTE Konvektionswärmeflüsse
#         def conv_heat_flow_1_2_rule(_block, i):
#             # Q_conv = m_dot * c_w * (T2 - T1)
#             # Linearisiert: Direkter Wärmefluss zwischen den Schichten
#             return _block.Q_conv_1_2[i] == _block.m_dot_STO_out[i] * _block.c_w * (_block.T_sto[i, 2] - _block.T_sto[i, 1])
        
#         def conv_heat_flow_2_3_rule(_block, i):
#             return _block.Q_conv_2_3[i] == _block.m_dot_STO_out[i] * _block.c_w * (_block.T_sto[i, 3] - _block.T_sto[i, 2])
        
#         def conv_heat_flow_3_ret_rule(_block, i):
#             return _block.Q_conv_3_ret[i] == _block.m_dot_STO_out[i] * _block.c_w * (_block.T_return_NW[i] - _block.T_sto[i, 3])
        
#         block.conv_heat_flow_1_2 = Constraint(t, rule=conv_heat_flow_1_2_rule)
#         block.conv_heat_flow_2_3 = Constraint(t, rule=conv_heat_flow_2_3_rule)
#         block.conv_heat_flow_3_ret = Constraint(t, rule=conv_heat_flow_3_ret_rule)

#         # Energiebilanz für jede Schicht mit linearisierten Konvektionsflüssen
#         # Obere Schicht (l=1)
#         def upper_layer_energy_balance_rule(_block, i):
#             if i == 1:
#                 # Initial condition
#                 return _block.T_sto[i, 1] == _block.T_sto_init[1]
#             else:
#                 # Energieänderung [MJ]
#                 energy_change = _block.m_sto[1] * _block.c_w * (_block.T_sto[i, 1] - _block.T_sto[i-1, 1])
                
#                 # Konvektion (linearisiert) [MJ]
#                 convection = _block.Q_conv_1_2[i] * _block.sec_to_hour * _block.delta_t
                
#                 # Solarthermie [MJ]
#                 solar_heat = _block.Q_dot_ST[i] * _block.delta_t * 3600

#                 return energy_change == convection + solar_heat

#         # Mittlere Schicht (l=2)
#         def middle_layer_energy_balance_rule(_block, i):
#             if i == 1:
#                 return _block.T_sto[i, 2] == _block.T_sto_init[2]
#             else:
#                 # Energieänderung [MJ]
#                 energy_change = _block.m_sto[2] * _block.c_w * (_block.T_sto[i, 2] - _block.T_sto[i-1, 2])
                
#                 # Konvektion (linearisiert) [MJ]
#                 convection = _block.Q_conv_2_3[i] * _block.sec_to_hour * _block.delta_t
                
#                 # Wärmepumpe [MJ]
#                 heat_pump = _block.Q_dot_WP[i] * _block.delta_t * 3600
                
#                 return energy_change == convection + heat_pump

#         # Untere Schicht (l=3)
#         def lower_layer_energy_balance_rule(_block, i):
#             if i == 1:
#                 return _block.T_sto[i, 3] == _block.T_sto_init[3]
#             else:
#                 # Energieänderung [MJ]
#                 energy_change = _block.m_sto[3] * _block.c_w * (_block.T_sto[i, 3] - _block.T_sto[i-1, 3])
                
#                 # Konvektion (linearisiert) [MJ]
#                 convection = _block.Q_conv_3_ret[i] * _block.sec_to_hour * _block.delta_t
                
#                 return energy_change == convection
        
#         # Temperaturschichtungs-Constraints
#         def temp_startification_upper_supply_rule_max(_block, i):
#             return _block.T_sto[i, 1] <= 100 + 273.15  # [K] max. Temperatur der oberen Schicht 
        
#         def temp_stratification_upper_middle_rule(_block, i):
#             return _block.T_sto[i, 1] >= _block.T_sto[i, 2]
        
#         def temp_stratification_middle_lower_rule(_block, i):
#             return _block.T_sto[i, 2] >= _block.T_sto[i, 3]
        
#         def temp_stratification_lower_return_rule(_block, i):
#             return _block.T_sto[i, 3] >= _block.T_return_NW[i]

#         # Fernwärme-Steuerung (optional)
#         block.bin_fw_in = Var(t, within=Binary)  # Binary variable for the mass flow in the storage
#         block.bin_fw_out = Var(t, within=Binary)  # Binary variable for the mass flow out of the storage

#         def max_fw_in_rule(_block, i):
#             max_Q = 100
#             return _block.Q_dot_FW_in[i] <= max_Q * _block.bin_fw_in[i]
        
#         def max_fw_out_rule(_block, i):
#             max_Q = 100
#             return _block.Q_dot_FW_out[i] <= max_Q * _block.bin_fw_out[i]
        
#         def fw_binary_rule(_block, i):
#             return _block.bin_fw_in[i] + _block.bin_fw_out[i] == 1

#         # Constraints zu Modell hinzufügen
#         block.upper_layer_balance = Constraint(t, rule=upper_layer_energy_balance_rule)
#         block.middle_layer_balance = Constraint(t, rule=middle_layer_energy_balance_rule)
#         block.lower_layer_balance = Constraint(t, rule=lower_layer_energy_balance_rule)
        
#         block.temp_stratification_1 = Constraint(t, rule=temp_stratification_upper_middle_rule)
#         block.temp_stratification_2 = Constraint(t, rule=temp_stratification_middle_lower_rule)
#         block.temp_stratification_3 = Constraint(t, rule=temp_stratification_lower_return_rule)
#         block.temp_stratification_4 = Constraint(t, rule=temp_startification_upper_supply_rule_max)
        
#         # Optionale Fernwärme-Constraints
#         block.max_fw_in = Constraint(t, rule=max_fw_in_rule)
#         block.max_fw_out = Constraint(t, rule=max_fw_out_rule)
#         block.fw_binary = Constraint(t, rule=fw_binary_rule)       


#         # Neue Regeln für Überschusswärme
#         def excess_heat_management_rule(_block, i):
#             # Wenn Temperatur in oberster Schicht sehr hoch, erlaube Fernwärmeeinspeisung
#             return _block.Q_dot_FW_out[i] >= (_block.T_sto[i, 1] - (95 + 273.15)) * 0.001  # 0.1 MW pro K über 95°C
                
#         block.excess_heat_management = Constraint(t, rule=excess_heat_management_rule)

# Version 3

# class StratifiedHeatStorage:
#     """Class for constructing stratified heat storage asset objects."""

#     def __init__(self, name, filepath, index_col=0) -> None:
#         self.name = name
#         self.get_data(filepath, index_col)

#     def get_data(self, filepath, index_col):
#         """Collects data from a csv."""
#         self.data = pd.read_csv(
#             filepath,
#             index_col=index_col
#         )
    
#     def add_to_model(self, model):
#         """Adds the asset as a pyomo block component to a given model."""
#         model.add_component(
#             self.name,
#             Block(rule=self.stratified_storage_block_rule)
#         )

#     def stratified_storage_block_rule(self, block):
#         """Rule for creating a stratified heat storage block with default components
#         and constraints."""

#         # Get index from model
#         t = block.model().t # [hours]
#         temp_sup_C = block.model().supply_temperature # [°C] 
#         temp_ret_C = block.model().return_temperature # [°C]

#         # Conversionfactor from seconds to hours
#         block.sec_to_hour = Param(initialize=3600) # [s/h]

#         # Set Layers
#         block.layers = Set(initialize=[1, 2, 3])
        
#         # Spezifiscer Wärmekapazität von Wasser in MJ/kg·K für MW-Berechnung
#         block.c_w = Param(initialize=4.1218 / 1000)  # [MJ/(kg·K)], konvertiert von kJ/(kg·K)

#         # Masse jeder Schicht in kg
#         block.m_sto = Param(block.layers, initialize={
#             1: 2000000/3, 
#             2: 2000000/3, 
#             3: 2000000/3})  # [kg] laut Gabriel Schumm 2000 m³, dh 2 Mio kg bei Dichte 1000 kg/m³ für Wasser

#         # Initial temperature of each layer in K
#         block.T_sto_init = Param(block.layers, initialize={
#             1: 95 + 273.15, # [K] 
#             2: 80 + 273.15, # [K]
#             3: 55 + 273.15})  # [K]
        
#         # Zeitschritt
#         block.delta_t = Param(initialize=1)  # [h]

#         # Fernwärmenetz
#         block.T_supply_FW = Param(initialize=95 + 273.15)  # [K] konstante Vorlauftemperatur der Fernwärme
#         block.T_return_FW = Param(initialize=55 + 273.15)  # [K] konstante Rücklauftemperatur der Fernwärme

#         # Convert temperatures to K
#         def temp_C_to_K(temp_C):
#             return temp_C + 273.15 if temp_C is not None else None
    
#         # Temperatur des Rücklaufs und Vorlaufs in Kelvin
#         def get_temp_ret_K(_block, i):
#             return temp_C_to_K(temp_ret_C[i])
        
#         def get_temp_sup_K(_block, i):
#             return temp_C_to_K(temp_sup_C[i])
        
#         # Temperature of each layer
#         block.T_sto = Var(t, block.layers, domain=NonNegativeReals) # [K]
        
#         # Temperatur des Rücklaufs und Vorlaufs in Kelvin
#         # Nahwärmenetz
#         block.T_return_NW = Expression(t, rule=get_temp_ret_K)  # [K]
#         block.T_supply_NW = Expression(t, rule=get_temp_sup_K)  # [K]

#         # Wärmeleistungseinträge
#         block.Q_dot_ST = Var(t, domain=NonNegativeReals)   # Wärmeeintrag durch Solarthermie [MW]
#         block.Q_dot_WP = Var(t, domain=NonNegativeReals)   # Wärmeeintrag durch Wärmepumpe [MW]
#         block.Q_dot_NW_out = Var(t, domain=NonNegativeReals)  # Wärmeabgabe an Nahwärmenetz [MW]
#         block.Q_dot_FW_out = Var(t, domain=NonNegativeReals)  # Wärmeabgabe an Fernwärmenetz [MW]
#         block.Q_dot_FW_in = Var(t, domain=NonNegativeReals)  # Wärmeeintrag durch Fernwärme [MW]
        
#         # Massenströme
#         block.m_dot_STO_out = Var(t, domain=NonNegativeReals)  # Massenstrom aus dem Speicher [kg/s]
        
#         # ======== LINEARISIERUNG: Feste Temperaturdifferenzen ========
#         # Definieren fester Temperaturdifferenzen zur Linearisierung
#         block.delta_T_1_2 = Param(initialize=15)  # [K] Temperaturdifferenz zwischen Schicht 1 und 2
#         block.delta_T_2_3 = Param(initialize=20)  # [K] Temperaturdifferenz zwischen Schicht 2 und 3
#         block.delta_T_3_ret = Param(initialize=15)  # [K] Temperaturdifferenz zwischen Schicht 3 und Rücklauf
        
#         # Hilfsvariablen für die Linearisierung - Wärmeflüsse zwischen Schichten [MW]
#         block.Q_conv_1_2 = Var(t, domain=Reals)  # Wärmefluss zwischen Schicht 1 und 2
#         block.Q_conv_2_3 = Var(t, domain=Reals)  # Wärmefluss zwischen Schicht 2 und 3
#         block.Q_conv_3_ret = Var(t, domain=Reals)  # Wärmefluss zwischen Schicht 3 und Rücklauf

#         # Ports für die Wärmeeingänge
#         block.st_heat_in = Port()
#         block.st_heat_in.add(block.Q_dot_ST, 'st_heat', Port.Extensive, include_splitfrac=False)
        
#         block.wp_heat_in = Port()
#         block.wp_heat_in.add(block.Q_dot_WP, 'wp_heat', Port.Extensive, include_splitfrac=False)
        
#         # Ports für die Wärmeausgänge 
#         block.nw_heat_out = Port()
#         block.nw_heat_out.add(block.Q_dot_NW_out, 'local_heat', Port.Extensive, include_splitfrac=False)

#         block.fw_heat_out = Port()
#         block.fw_heat_out.add(block.Q_dot_FW_out, 'excess_heat', Port.Extensive, include_splitfrac=False)
     
#         # Port für Wärmeeingang
#         block.fw_heat_in = Port()
#         block.fw_heat_in.add(block.Q_dot_FW_in, 'fw_heat', Port.Extensive, include_splitfrac=False)

#         # Massenströme über Expressions definieren
#         def m_dot_FW_in_rule(_block, i):
#             delta_T_FW = _block.T_supply_FW - _block.T_return_FW
#             return (_block.Q_dot_FW_in[i] / (_block.c_w * delta_T_FW))
        
#         block.m_dot_FW_in = Expression(t, rule=m_dot_FW_in_rule)
        
#         def m_dot_FW_out_rule(_block, i):
#             delta_T_FW = _block.T_supply_FW - _block.T_return_FW
#             return (_block.Q_dot_FW_out[i] / (_block.c_w * delta_T_FW))
        
#         block.m_dot_FW_out = Expression(t, rule=m_dot_FW_out_rule)

#         def m_dot_NW_out_rule(_block, i):
#             delta_T_NW = _block.T_supply_NW[i] - _block.T_return_NW[i]
#             return (_block.Q_dot_NW_out[i] / (_block.c_w * delta_T_NW))
        
#         block.m_dot_NW_out = Expression(t, rule=m_dot_NW_out_rule)

#         # ======== CONSTRAINTS ========

#         # Massenbilanz
#         def mass_flow_rule(_block, i):
#             return _block.m_dot_FW_in[i] + _block.m_dot_STO_out[i] == _block.m_dot_NW_out[i] + _block.m_dot_FW_out[i]
        
#         block.mass_flow = Constraint(t, rule=mass_flow_rule)
        
#         # Berechnung des Massenstroms aus dem Speicher
#         def m_dot_STO_out_rule(_block, i):
#             delta_T_NW = _block.T_supply_NW[i] - _block.T_return_NW[i]
#             return _block.m_dot_STO_out[i] * _block.c_w * delta_T_NW == _block.Q_dot_NW_out[i]
        
#         block.m_dot_STO_out_constraint = Constraint(t, rule=m_dot_STO_out_rule)

#         # ======== LINEARISIERTE Konvektionswärmeflüsse ========
#         # Mit FESTEN Temperaturdifferenzen anstatt Variablen
#         def conv_heat_flow_1_2_rule(_block, i):
#             return _block.Q_conv_1_2[i] == _block.m_dot_STO_out[i] * _block.c_w * _block.delta_T_1_2
        
#         def conv_heat_flow_2_3_rule(_block, i):
#             return _block.Q_conv_2_3[i] == _block.m_dot_STO_out[i] * _block.c_w * _block.delta_T_2_3
        
#         def conv_heat_flow_3_ret_rule(_block, i):
#             return _block.Q_conv_3_ret[i] == _block.m_dot_STO_out[i] * _block.c_w * _block.delta_T_3_ret
        
#         block.conv_heat_flow_1_2 = Constraint(t, rule=conv_heat_flow_1_2_rule)
#         block.conv_heat_flow_2_3 = Constraint(t, rule=conv_heat_flow_2_3_rule)
#         block.conv_heat_flow_3_ret = Constraint(t, rule=conv_heat_flow_3_ret_rule)

#         # Energiebilanz für jede Schicht mit linearisierten Konvektionsflüssen
#         # Obere Schicht (l=1)
#         def upper_layer_energy_balance_rule(_block, i):
#             if i == 1:
#                 # Initial condition
#                 return _block.T_sto[i, 1] == _block.T_sto_init[1]
#             else:
#                 # Energieänderung [MJ]
#                 energy_change = _block.m_sto[1] * _block.c_w * (_block.T_sto[i, 1] - _block.T_sto[i-1, 1])
                
#                 # Konvektion (linearisiert) [MJ]
#                 convection = _block.Q_conv_1_2[i] * _block.sec_to_hour * _block.delta_t
                
#                 # Solarthermie [MJ]
#                 solar_heat = _block.Q_dot_ST[i] * _block.delta_t * 3600

#                 return energy_change == convection + solar_heat

#         # Mittlere Schicht (l=2)
#         def middle_layer_energy_balance_rule(_block, i):
#             if i == 1:
#                 return _block.T_sto[i, 2] == _block.T_sto_init[2]
#             else:
#                 # Energieänderung [MJ]
#                 energy_change = _block.m_sto[2] * _block.c_w * (_block.T_sto[i, 2] - _block.T_sto[i-1, 2])
                
#                 # Konvektion (linearisiert) [MJ]
#                 convection = _block.Q_conv_2_3[i] * _block.sec_to_hour * _block.delta_t
                
#                 # Wärmepumpe [MJ]
#                 heat_pump = _block.Q_dot_WP[i] * _block.delta_t * 3600
                
#                 return energy_change == convection + heat_pump

#         # Untere Schicht (l=3)
#         def lower_layer_energy_balance_rule(_block, i):
#             if i == 1:
#                 return _block.T_sto[i, 3] == _block.T_sto_init[3]
#             else:
#                 # Energieänderung [MJ]
#                 energy_change = _block.m_sto[3] * _block.c_w * (_block.T_sto[i, 3] - _block.T_sto[i-1, 3])
                
#                 # Konvektion (linearisiert) [MJ]
#                 convection = _block.Q_conv_3_ret[i] * _block.sec_to_hour * _block.delta_t
                
#                 return energy_change == convection
        
#         # Temperaturschichtungs-Constraints
#         def temp_startification_upper_supply_rule_max(_block, i):
#             return _block.T_sto[i, 1] <= 1000 + 273.15  # [K] max. Temperatur der oberen Schicht 
        
#         def temp_stratification_upper_middle_rule(_block, i):
#             return _block.T_sto[i, 1] >= _block.T_sto[i, 2]
        
#         def temp_stratification_middle_lower_rule(_block, i):
#             return _block.T_sto[i, 2] >= _block.T_sto[i, 3]
        
#         def temp_stratification_lower_return_rule(_block, i):
#             return _block.T_sto[i, 3] >= _block.T_return_NW[i]

#         # Fernwärme-Steuerung (optional)
#         block.bin_fw_in = Var(t, within=Binary)  # Binary variable for the mass flow in the storage
#         block.bin_fw_out = Var(t, within=Binary)  # Binary variable for the mass flow out of the storage

#         def max_fw_in_rule(_block, i):
#             max_Q = 100
#             return _block.Q_dot_FW_in[i] <= max_Q * _block.bin_fw_in[i]
        
#         def max_fw_out_rule(_block, i):
#             max_Q = 100
#             return _block.Q_dot_FW_out[i] <= max_Q * _block.bin_fw_out[i]
        
#         def fw_binary_rule(_block, i):
#             return _block.bin_fw_in[i] + _block.bin_fw_out[i] == 1

#         # ======== LINEARISIERTE Überschusswärme-Management ========
#         # Option 1: Temperaturabhängiger Ausdruck durch zeitabhängigen Ausdruck ersetzen
#         block.peak_hours = Set(initialize=[10, 11, 12, 13, 14, 15, 16, 17, 18])  # Stunden für FW-Einspeisung
        
#         def fw_discharge_periods_rule(_block, i):
#             hour_of_day = i % 24 if i % 24 > 0 else 24
#             if hour_of_day in _block.peak_hours:
#                 return Constraint.Skip  # Während Spitzenzeiten Fernwärmeeinspeisung erlauben
#             else:
#                 return _block.Q_dot_FW_out[i] == 0  # Sonst keine Fernwärmeeinspeisung
            
#         def fw_rule(_block, i):
#             return _block.Q_dot_FW_out[i] == 0
        
#         block.fw_rule = Constraint(t, rule=fw_rule)

#         # Constraints zu Modell hinzufügen
#         block.upper_layer_balance = Constraint(t, rule=upper_layer_energy_balance_rule)
#         block.middle_layer_balance = Constraint(t, rule=middle_layer_energy_balance_rule)
#         block.lower_layer_balance = Constraint(t, rule=lower_layer_energy_balance_rule)
        
#         block.temp_stratification_1 = Constraint(t, rule=temp_stratification_upper_middle_rule)
#         block.temp_stratification_2 = Constraint(t, rule=temp_stratification_middle_lower_rule)
#         block.temp_stratification_3 = Constraint(t, rule=temp_stratification_lower_return_rule)
#         block.temp_stratification_4 = Constraint(t, rule=temp_startification_upper_supply_rule_max)
        
#         # Optionale Fernwärme-Constraints
#         block.max_fw_in = Constraint(t, rule=max_fw_in_rule)
#         block.max_fw_out = Constraint(t, rule=max_fw_out_rule)
#         block.fw_binary = Constraint(t, rule=fw_binary_rule)
        
#         # Zeitabhängige Fernwärmeeinspeisung statt temperaturabhängiger Regelung
#         # block.fw_discharge_periods = Constraint(t, rule=fw_discharge_periods_rule)
        
#         # Alternative: Einfache Obergrenze für Fernwärmeeinspeisung
#         def excess_heat_max_rule(_block, i):
#             return _block.Q_dot_FW_out[i] <= 5.0  # Maximal 5 MW Fernwärmeeinspeisung
            
#         # block.excess_heat_max = Constraint(t, rule=excess_heat_max_rule)


class StratifiedHeatStorage:
    """Class for constructing a double heat storage system with district heating and local heating components."""

    def __init__(self, name, filepath, index_col=0) -> None:
        self.name = name
        self.get_data(filepath, index_col)

    def get_data(self, filepath, index_col):
        """Collects data from a csv."""
        self.data = pd.read_csv(
            filepath,
            index_col=index_col
        )
    
    def add_to_model(self, model):
        """Adds the asset as a pyomo block component to a given model."""
        model.add_component(
            self.name,
            Block(rule=self.double_storage_block_rule)
        )

    def double_storage_block_rule(self, block):
        """Rule for creating a double heat storage block with district and local heating components.

        This block includes two storage layers: 
        S1: First Layer Storage
        S2: Second Layer Storage

        """

        # Get index from model
        t = block.model().t # [hours]
        
        # Zeitschritt
        block.delta_t = Param(initialize=1)  # [h]
        
        # Verlustkoeffizient für beide Speicher
        block.k_loss_S1 = Param(initialize=0.0534)  # [%] Wärmeverlustrate Fernwärmespeicher
        block.k_loss_S2 = Param(initialize=0.0534)  # [%] Wärmeverlustrate Nahwärmespeicher
        
        # Maximale Speicherkapazitäten [MWh]
        block.max_capacity_S1 = Param(initialize=100)  # Fernwärmespeicher
        block.max_capacity_S2 = Param(initialize=50)   # Nahwärmespeicher
        block.max_total_capacity = Param(initialize=150)  # Gesamtmaximale Speicherkapazität
        
        # Initiale Speicherkapazitäten [MWh]
        block.init_capacity_S1 = Param(initialize=30)  # Fernwärmespeicher
        block.init_capacity_S2 = Param(initialize=20)  # Nahwärmespeicher
        
        # Wärmeleistungseinträge und Speicherzustand
        block.Q_dot_ST = Var(t, domain=NonNegativeReals)       # Solarthermie-Eintrag [MW]
        block.Q_dot_WP = Var(t, domain=NonNegativeReals)       # Wärmepumpen-Eintrag [MW]
        
        # Wärmeabgabe S1
        block.Q_dot_S1_FW = Var(t, domain=NonNegativeReals)  # Wärmeabgabe vom S1-Speicher an Fernwärmenetz [MW]
        block.Q_dot_S1_NW = Var(t, domain=NonNegativeReals)  # Wärmeabgabe vom S1-Speicher an Nahwärmenetz [MW]
        
        # Wärmeabgabe S2
        block.Q_dot_S2_NW = Var(t, domain=NonNegativeReals)  # Wärmeabgabe vom S2-Speicher an Nahwärmenetz [MW]

        # Speicherzustände
        block.U_S1 = Var(t, domain=NonNegativeReals)  # Speicherinhalt Fernwärmespeicher [MWh]
        block.U_S2 = Var(t, domain=NonNegativeReals)  # Speicherinhalt Nahwärmespeicher [MWh]
        
        # Binärvariablen für Steuerungslogik
        block.bin_S1_charge = Var(t, within=Binary)     # 1 wenn S1-Speicher geladen wird
        block.bin_S1_discharge = Var(t, within=Binary)  # 1 wenn S1-Speicher entladen wird
        block.bin_S2_charge = Var(t, within=Binary)     # 1 wenn S2-Speicher geladen wird
        block.bin_S2_discharge = Var(t, within=Binary)  # 1 wenn S2-Speicher entladen wird
        
        # Ports für die Wärmeeingänge
        block.st_heat_in = Port()
        block.st_heat_in.add(block.Q_dot_ST, 'st_heat', Port.Extensive, include_splitfrac=False)
        
        block.wp_heat_in = Port()
        block.wp_heat_in.add(block.Q_dot_WP, 'wp_heat', Port.Extensive, include_splitfrac=False)
        
        # Ports für die Wärmeausgänge
        block.S1_FW_heat_out = Port()
        block.S1_FW_heat_out.add(block.Q_dot_S1_FW, 'nw_excess_heat', Port.Extensive, include_splitfrac=False)
        
        block.S1_NW_heat_out = Port()
        block.S1_NW_heat_out.add(block.Q_dot_S1_NW, 'local_heat', Port.Extensive, include_splitfrac=False)

        block.S2_NW_heat_out = Port()
        block.S2_NW_heat_out.add(block.Q_dot_S2_NW, 'local_heat', Port.Extensive, include_splitfrac=False)

        # Grenzen für maximalen Wärmestrom
        block.max_heat_flow = Param(initialize=20)  # [MW]
        
        # ======== CONSTRAINTS ========
        
        # Maximale Lade-/Entladeraten
        def max_fw_discharge_rule(_block, i):
            return _block.Q_dot_S1_FW[i] + _block.Q_dot_S1_NW[i] <= _block.max_heat_flow 
        
        def max_nw_discharge_rule(_block, i):
            return _block.Q_dot_S2_NW[i] <= _block.max_heat_flow 
        
      
        # Energiebilanzgleichungen nach dem Kapazitätsmodell:
        # U(t) = [1−k_v] ⋅ U(t−1) + [Q_in(t) - Q_out(t)] ⋅ Δt
        
        # Fernwärmespeicher-Bilanz
        def S1_storage_balance_rule(_block, i):
            if i == 1:
                return _block.U_S1[i] == _block.init_capacity_S1
            else:
                return _block.U_S1[i] == (1 - _block.k_loss_S1) * _block.U_S1[i-1] + \
                    (_block.Q_dot_ST[i] - _block.Q_dot_S1_FW[i] - _block.Q_dot_S1_NW[i]) * _block.delta_t
        
        # Nahwärmespeicher-Bilanz
        def S2_storage_balance_rule(_block, i):
            if i == 1:
                return _block.U_S2[i] == _block.init_capacity_S2
            else:
                return _block.U_S2[i] == (1 - _block.k_loss_S2) * _block.U_S2[i-1] + \
                    (_block.Q_dot_WP[i] - _block.Q_dot_S2_NW[i]) * _block.delta_t
        
        # Maximale Speicherkapazitäten
        # Gemeinsame Kapazitätsbegrenzung
        def total_capacity_rule(_block, i):
            return _block.U_S1[i] + _block.U_S2[i] <= _block.max_total_capacity
        
        # Minimale Speicherkapazitäten
        def min_S1_capacity_rule(_block, i):
            return _block.U_S1[i] >= 0
        
        def min_S2_capacity_rule(_block, i):
            return _block.U_S2[i] >= 0
        
        # Constraints zu Modell hinzufügen
        block.max_fw_discharge = Constraint(t, rule=max_fw_discharge_rule)
        block.max_nw_discharge = Constraint(t, rule=max_nw_discharge_rule)

        
        block.fw_storage_balance = Constraint(t, rule=S1_storage_balance_rule)
        block.nw_storage_balance = Constraint(t, rule=S2_storage_balance_rule)
        
        # block.max_fw_capacity = Constraint(t, rule=max_S1_capacity_rule)
        # block.max_nw_capacity = Constraint(t, rule=max_S2_capacity_rule)
        # block.total_capacity = Constraint(t, rule=total_capacity_rule)
        block.min_fw_capacity = Constraint(t, rule=min_S1_capacity_rule)
        block.min_nw_capacity = Constraint(t, rule=min_S2_capacity_rule)

        # Physikalische Eigenschaften des Wassers
        block.water_density = Param(initialize=1000)  # [kg/m³]
        block.spec_heat_capacity = Param(initialize=4.1868/1000)  # [MJ/(kg·K)]
        
        # Temperaturdifferenzen
        block.delta_T_S1 = Param(initialize=40)  # [K] (95°C - 55°C)
        block.delta_T_S2 = Param(initialize=25)  # [K] (80°C - 55°C)
        
        # Spezifische Energiedichten [MWh/m³]
        block.energy_density_S1 = Param(
            initialize=block.water_density.value * block.spec_heat_capacity.value * 
            block.delta_T_S1.value / 3600
        )
        block.energy_density_S2 = Param(
            initialize=block.water_density.value * block.spec_heat_capacity.value * 
            block.delta_T_S2.value / 3600
        )
        
        # Maximales Gesamtvolumen
        block.max_total_volume = Param(initialize=2000)  # [m³]
        
        # Constraint für das physische Volumen
        def physical_volume_constraint_rule(_block, i):
            # Umrechnung von Energie [MWh] zu Volumen [m³]
            volume_S1 = _block.U_S1[i] / _block.energy_density_S1
            volume_S2 = _block.U_S2[i] / _block.energy_density_S2
            return volume_S1 + volume_S2 <= _block.max_total_volume
        
        block.physical_volume_constraint = Constraint(t, rule=physical_volume_constraint_rule)

        # Hinzufügen

        # Begrenzen der maximale Leistung
        # Einspeichern ins Fernwärmenetz nur zu bestimmten Zeiträumen möglich 
        