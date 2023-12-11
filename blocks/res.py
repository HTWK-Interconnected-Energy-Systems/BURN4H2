from pyomo.environ import *
from pyomo.network import *

class Photovoltaics:
    """Class for constructing photovoltaics asset objects"""

    def __init__(self, data, capacity_factors) -> None:
        self.data = data
        self.capacity_factors = capacity_factors
    

    def pv_block_rule(self, block):
        """Rule for creating a photovoltaics block with default components and constraints."""
        # Get index from model
        t = block.model().t


        # Declare components
        block.power = Var(t, domain=NonNegativeReals)

        block.power_out = Port()
        block.power_out.add(block.power, 'power', Port.Extensive, include_splitfrac=False)


        # Declare construction rules for constraints
        def power_generation_rule(_block, i):
            """Rule for calculating the power generation of the photovoltaics."""
            installed_power = self.data.loc['value', 'installed_power']
            inverter_efficiency = self.data.loc['value', 'inverter_efficiency']
            capacity_factors = self.capacity_factors['capacity_factor']
            return _block.power[i] == installed_power * inverter_efficiency * capacity_factors[i]
        

        # Declare constraints
        block.power_generation_constraint = Constraint(
            t,
            rule=power_generation_rule
        )