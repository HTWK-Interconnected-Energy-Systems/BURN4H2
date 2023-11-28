from pyomo.environ import *
from pyomo.network import *

class BatteryStorage:
    """Class for constructing battery storage asset objects."""

    def __init__(self, data) -> None:
        self.data = data
    
    def battery_storage_block_rule(self, block):
        """Rule for creating a battery storage block with default components and constraints."""

        # Get index from model
        t = block.model().t
        
        # Define components
        block.overall_power = Var(t, domain=Reals)
        block.charging_power = Var(t, domain=NonNegativeReals)
        block.discharging_power = Var(t, domain=NonNegativeReals)
        block.energy = Var(t, domain=NonNegativeReals)
        block.discharge_bin = Var(t, within=Binary)
        block.charge_bin = Var(t, within=Binary)

        block.power_in = Port(initialize={'power': (block.charging_power, Port.Extensive)})
        block.power_out = Port(initialize={'power': (block.discharging_power, Port.Extensive)})


        # Define construction rules for constraints
        def max_charging_power_rule(_block, i):
            """Rule for the maximal charging power."""
            return _block.charging_power[i] <= self.data.loc['Max', 'Power'] * _block.charge_bin[i]
        

        def max_discharging_power_rule(_block, i):
            """Rule for the maximal discharging power."""
            return _block.discharging_power[i] <= self.data.loc['Max', 'Power'] * _block.discharge_bin[i]


        def overall_power_rule(_block, i):
            """Rule for calculating the overall power."""
            return _block.overall_power[i] ==  _block.discharging_power[i] - _block.charging_power[i]


        def binary_rule(_block, i):
            """Rule for restricting simultaneous charging and discharging."""
            return _block.charge_bin[i] + _block.discharge_bin[i] <= 1
        

        def max_energy_content_rule(_block, i):
            """Rule for the maximal energy content of the battery storage."""
            return _block.energy[i] <= self.data.loc['Max', 'Capacity']
        

        def min_energy_content_rule(_block, i):
            """Rule for the minimal energy content of the battery storage."""
            return _block.energy[i] >= self.data.loc['Min', 'Capacity']
        

        def actual_energy_content_rule(_block, i):
            """Rule for calculating the actual energy content of the battery storage."""
            if i == 1:
                return _block.energy[i] == 0 - _block.overall_power[i]
            else:
                return _block.energy[i] == _block.energy[i - 1] - _block.overall_power[i]
        

        # Define constraints
        block.max_charging_power_constraint = Constraint(
            t,
            rule=max_charging_power_rule
        )
        block.max_discharging_power_constraint = Constraint(
            t,
            rule=max_discharging_power_rule
        )
        block.overall_power_constraint = Constraint(
            t,
            rule=overall_power_rule
        )
        block.binary_constraint = Constraint(
            t,
            rule=binary_rule
        )
        block.max_energy_content_constraint = Constraint(
            t,
            rule=max_energy_content_rule
        )
        block.min_energy_content_constraint = Constraint(
            t,
            rule=min_energy_content_rule
        )
        block.actual_energy_content_constraint = Constraint(
            t,
            rule=actual_energy_content_rule
        )
