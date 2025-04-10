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

        # Declare ports
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

        # Declare ports
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

        # Declare ports
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

        # Declare ports
        block.heat_in = Port()
        block.heat_in.add(block.heat_charging, 'waste_heat', Port.Extensive, include_splitfrac=False)
        block.heat_out = Port()
        block.heat_out.add(block.heat_discharging, 'waste_heat', Port.Extensive, include_splitfrac=False)


        # Declare construction rules for constraints
        def max_heat_charging_rule(_block, i):
            """Rule for the maximum charging capacity of heat."""
            return _block.heat_charging[i] <= self.data.loc['max', 'heat_in'] * _block.bin_charge[i]
                

        def max_heat_discharging_rule(_block, i):
            """Rule for the maximum discharging capacity of heat."""
            return _block.heat_discharging[i] <= self.data.loc['max', 'heat_out'] * _block.bin_discharge[i]
        

        def min_heat_charging_rule(_block, i):
            """Rule for the minimum charging capacity of heat."""
            return _block.heat_charging[i] >= self.data.loc['min', 'heat_in'] * _block.bin_charge[i]
        

        def min_heat_discharging_rule(_block, i):
            """Rule for the minimum discharging capacity of heat."""
            return _block.heat_discharging[i] >= self.data.loc['min', 'heat_out'] * _block.bin_discharge[i]


        def heat_balance_rule(_block, i):
            """Rule for calculating the overall heat balance."""
            return _block.heat_balance[i] == _block.heat_discharging[i] - _block.heat_charging[i]


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
        block.min_heat_charging_constraint = Constraint(
            t,
            rule=min_heat_charging_rule
        )
        block.min_heat_discharging_constraint = Constraint(
            t,
            rule=min_heat_discharging_rule
        )
        block.heat_balance_constraint = Constraint(
            t,
            rule=heat_balance_rule
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



class StratifiedHeatStorage:
    """Class for constructing a double heat storage system with district heating and local heating components."""

    def __init__(self, name, filepath, index_col=0, **kwargs) -> None:
        self.name = name
        self.get_data(filepath, index_col)
        self.kwargs = kwargs
        self.validate_kwargs()

    def validate_kwargs(self):
        allowed_kwargs = ['seasonal_discharge_restriction']
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
            Block(rule=self.stratified_storage_block_rule)
        )

    def stratified_storage_block_rule(self, block):
        """Rule for creating a double heat storage block with district and local heating components.

        This block includes two storage layers: 
        Z1: First Layer Storage
        Z2: Second Layer Storage

        """

        # Get index from model
        t = block.model().t # [hours]
        
        # Declare components
        block.delta_t = Param(initialize=1)  # [h]
        block.k_loss_Z1 = Param(initialize=0.0534)  # [%] Wärmeverlustrate Fernwärmespeicher
        block.k_loss_Z2 = Param(initialize=0.0534)  # [%] Wärmeverlustrate Nahwärmespeicher
        block.water_density = Param(initialize=1000)  # # Water density [kg/m³]
        block.spec_heat_capacity = Param(initialize=4.1868/1000)  # Specific heat capacity [MJ/(kg·K)]
        block.delta_T_Z1 = Param(initialize=38)  # Temperature difference in zone 1 [K] (95°C - 57°C)
        block.delta_T_Z2 = Param(initialize=23)  # Temperature difference in zone 2 [K] (80°C - 57°C)
        block.max_total_volume = Param(initialize=2000)  # Maximum total storage volume [m³]
        

        block.energy_density_Z1 = Param(
            initialize=block.water_density.value * block.spec_heat_capacity.value * 
            block.delta_T_Z1.value / 3600
        )   # Specific energy density for zone 1 [MWh/m³]
        block.energy_density_Z2 = Param(
            initialize=block.water_density.value * block.spec_heat_capacity.value * 
            block.delta_T_Z2.value / 3600
        )   # Specific energy density for zone 2 [MWh/m³]

        block.initial_fill_percentage = Param(initialize=0) # Initial fill level, 1 = 100% energy content according to volume shares
        block.initial_volume_share_Z1 = Param(initialize=0.5)  # Share of district heating storage volume in total volume
        
        # Functions for calculating the maximum capacities
        def calc_max_capacity_Z1():
            return block.energy_density_Z1 * block.max_total_volume * block.initial_volume_share_Z1

        def calc_max_capacity_Z2():
            return block.energy_density_Z2 * block.max_total_volume * (1 - block.initial_volume_share_Z1)

        block.init_capacity_Z1 = Param(initialize=calc_max_capacity_Z1() * block.initial_fill_percentage)  # Initial capacity of Z1 storage
        block.init_capacity_Z2 = Param(initialize=calc_max_capacity_Z2() * block.initial_fill_percentage)  # Initial capacity of Z2 storage
        
        block.Q_dot_ST = Var(t, domain=NonNegativeReals) # Solar thermal input [MW]
        block.Q_dot_WP = Var(t, domain=NonNegativeReals) # Heat pump input [MW]
        block.Q_dot_Z1_FW = Var(t, domain=NonNegativeReals)  # Heat output from Z1 storage to district heating network [MW]
        block.Q_dot_Z1_NW = Var(t, domain=NonNegativeReals)  # Heat output from Z1 storage to local heating network [MW]
        block.Q_dot_Z2_NW = Var(t, domain=NonNegativeReals)  # Heat output from Z2 storage to local heating network [MW]


        block.U_Z1 = Var(t, domain=NonNegativeReals)  # District heating storage Z1 content [MWh]
        block.U_Z2 = Var(t, domain=NonNegativeReals)  # Local heating storage Z2 content [MWh]
        
        block.bin_Z1_charge = Var(t, within=Binary)     # 1 if Z1 storage is being charged
        block.bin_Z1_discharge = Var(t, within=Binary)  # 1 if Z1 storage is being discharged
        block.bin_Z2_charge = Var(t, within=Binary)     # 1 if Z2 storage is being charged
        block.bin_Z2_discharge = Var(t, within=Binary)  # 1 if Z2 storage is being discharged
        

        # Declare ports
        block.st_heat_in = Port()
        block.st_heat_in.add(block.Q_dot_ST, 'st_heat', Port.Extensive, include_splitfrac=False)
        block.wp_heat_in = Port()
        block.wp_heat_in.add(block.Q_dot_WP, 'wp_heat', Port.Extensive, include_splitfrac=False)
        block.Z1_FW_heat_out = Port()
        block.Z1_FW_heat_out.add(block.Q_dot_Z1_FW, 'nw_excess_heat', Port.Extensive, include_splitfrac=False)
        block.Z1_NW_heat_out = Port()
        block.Z1_NW_heat_out.add(block.Q_dot_Z1_NW, 'local_heat', Port.Extensive, include_splitfrac=False)
        block.Z2_NW_heat_out = Port()
        block.Z2_NW_heat_out.add(block.Q_dot_Z2_NW, 'local_heat', Port.Extensive, include_splitfrac=False)
        
        # Declare construction rules for constraints
        def max_fw_discharge_rule(_block, i):
            return _block.Q_dot_Z1_FW[i]  <= self.data.loc['max', 'heat']
        

        def max_nw_discharge_rule(_block, i):
            return _block.Q_dot_Z1_NW[i] + _block.Q_dot_Z2_NW[i] <= self.data.loc['max', 'heat']
        
      
        # Energy balance equations according to the capacity model:
        # U(t) = [1−k_v] ⋅ U(t−1) + [Q_in(t) - Q_out(t)] ⋅ Δt
        
        # District heating storage Z1 balance
        def Z1_storage_balance_rule(_block, i):
            if i == 1:
                return _block.U_Z1[i] == _block.init_capacity_Z1 + \
                    (_block.Q_dot_ST[i] - _block.Q_dot_Z1_FW[i] - _block.Q_dot_Z1_NW[i]) * _block.delta_t 
            else:
                return _block.U_Z1[i] == (1 - _block.k_loss_Z1) * _block.U_Z1[i-1] + \
                    (_block.Q_dot_ST[i] - _block.Q_dot_Z1_FW[i] - _block.Q_dot_Z1_NW[i]) * _block.delta_t
        

        # Local heating storage Z2 balance
        def Z2_storage_balance_rule(_block, i):
            if i == 1:
                return _block.U_Z2[i] == _block.init_capacity_Z2 + \
                    (_block.Q_dot_WP[i] - _block.Q_dot_Z2_NW[i]) * _block.delta_t
            else:
                return _block.U_Z2[i] == (1 - _block.k_loss_Z2) * _block.U_Z2[i-1] + \
                    (_block.Q_dot_WP[i] - _block.Q_dot_Z2_NW[i]) * _block.delta_t
        

        def min_Z1_capacity_rule(_block, i):
            return _block.U_Z1[i] >= 0
        

        def min_Z2_capacity_rule(_block, i):
            return _block.U_Z2[i] >= 0
        

        def physical_volume_constraint_rule(_block, i):
            volume_Z1 = _block.U_Z1[i] / _block.energy_density_Z1
            volume_Z2 = _block.U_Z2[i] / _block.energy_density_Z2
            return volume_Z1 + volume_Z2 <= _block.max_total_volume
        
              


        # Declare constraints
        block.max_fw_discharge = Constraint(
            t, 
            rule=max_fw_discharge_rule
        )
        block.max_nw_discharge = Constraint(
            t, 
            rule=max_nw_discharge_rule
        )
        block.fw_storage_balance = Constraint(
            t, 
            rule=Z1_storage_balance_rule
        )
        block.nw_storage_balance = Constraint(
            t, 
            rule=Z2_storage_balance_rule
        )
        block.min_fw_capacity = Constraint(
            t, 
            rule=min_Z1_capacity_rule
        )
        block.min_nw_capacity = Constraint(
            t, 
            rule=min_Z2_capacity_rule
        )
        block.physical_volume_constraint = Constraint(
            t, 
            rule=physical_volume_constraint_rule
        )

        if self.kwargs.get('seasonal_discharge_restriction'):

            block.fw_discharge_restricted_periods_dummy = Set(initialize=list(range(1, 11)) + list(range(12,14))) # Dummy periods for testing
            block.fw_discharge_restricted_periods = Set(initialize=list(range(1, 2879)) + list(range(7296, 8761))) # Regular year restriction: Nov 1 to Apr 30
            block.fw_discharge_restricted_periods_leap = Set(initialize=list(range(1, 2903)) + list(range(7320, 8785)))  # Leap year restriction: Nov 1 to Apr 30

            def storage_fw_discharge_rule(_block, i):
                # Dummy period for short simulations (1 week)
                if t.last() == 168 and i in _block.fw_discharge_restricted_periods_dummy:
                    return _block.Q_dot_Z1_FW[i] == 0
                
                # Leap year simulation (8784 hours)
                elif t.last() == 8784 and i in _block.fw_discharge_restricted_periods_leap:
                    return _block.Q_dot_Z1_FW[i] == 0
                
                # Standard year simulation (8760 hours)
                elif t.last() == 8760 and i in _block.fw_discharge_restricted_periods:
                    return _block.Q_dot_Z1_FW[i] == 0

                else:
                    return Constraint.Skip
            
            
            block.storage_fw_discharge_constraint = Constraint(
                t,
                rule=storage_fw_discharge_rule
            )