from pyomo.environ import *
from pyomo.network import *

class Grid:
    """Class for constructing grid asset objects."""

    def __init__(self, data) -> None:
        self.data = data

    
    def electrcial_grid_block_rule(self, block):
        """Rule for creating a electrical power grid block with default components and 
        constraints."""
        # Get index from model
        t = block.model().t


        # Define components
        block.overall_power = Var(t, domain=Reals)
        block.supply_power = Var(t, domain=NonNegativeReals)
        block.feedin_power = Var(t, domain=NonNegativeReals)

        block.power_in = Port()
        block.power_in.add(block.feedin_power, 'power', Port.Extensive, include_splitfrac=False)
        block.power_out = Port()
        block.power_out.add(block.supply_power, 'power', Port.Extensive, include_splitfrac=False)


        # Define construction rules for constraints
        def max_supply_power_rule(_block, i):
            """Rule for the maximal supply power."""
            return _block.supply_power[i] <= self.data.loc['Max', 'Power']
        

        def max_feedin_power_rule(_block, i):
            """Rule for the maximal feed in power."""
            return _block.feedin_power[i] <= self.data.loc['Max', 'Power']
        

        def overall_power_rule(_block, i):
            """Rule for calculating the overall power."""
            return _block.overall_power[i] == _block.supply_power[i] - _block.feedin_power[i]
        

        # Define constraints
        block.max_supply_power_constraint = Constraint(
            t,
            rule=max_supply_power_rule
        )
        block.max_feedin_power_constraint = Constraint(
            t,
            rule=max_feedin_power_rule
        )
        block.overall_power_constraint = Constraint(
            t,
            rule=overall_power_rule
        )
        