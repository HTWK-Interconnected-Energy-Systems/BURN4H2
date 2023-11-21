import pandas as pd
from pyomo.environ import *
from pyomo.network import *

class Grid:
    """Class for constructing grid objects."""

    def __init__(self, data) -> None:
        self.data = data

    
    def electrcial_grid_block_rule(self, block):
        """Rule for creating a electrical power grid block with default components and 
        constraints."""
        # Get index from model
        t = block.model().t

        # Define components
        block.max_power = Var(t, domain=NonNegativeReals)
        block.power = Var(t, domain=Reals)
        block.supply_bin = Var(t, within=Binary)
        block.feedin_bin = Var(t, within=Binary)


        # Define construction rules for constraints
        def power_max_rule(_block, i):
            """Rule for the maximal overall power."""
            return _block.max_power[i] == self.data.loc['Max', 'Power']
        

        def binary_rule(_block, i):
            """Rule for restricting simultaneous supply and feed in."""
            return _block.supply_bin[i] + _block.feedin_bin[i] <= 1
        

        # Define constraints
        block.power_max_constraint = Constraint(
            t,
            rule=power_max_rule
        )
        block.binary_constraint = Constraint(
            t,
            rule=binary_rule
        )