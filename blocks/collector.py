from pyomo.environ import *
from pyomo.network import *
import pandas as pd

class Collector:
    """Class for constructing collector asset objects."""

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
            Block(rule=self.collector_block_rule)
            )
        

    def collector_block_rule(self, block):
        """Rule for creating a collector block with default components and constraints."""
        # Get index from model
        t = block.model().t

        # Get profile from model
        solar_profile = block.model().solar_thermal_heat_profile

        # Declare components
        block.bin = Var(t, initialize=0, within=Binary)
        block.heat = Var(t, domain=NonNegativeReals)
    
        # Declare blocks
        block.heat_out = Port()
        block.heat_out.add(
            block.heat,
            'local_heat',
            Port.Extensive,
            include_splitfrac=False
        )

        # Constraints
        def profile_rule(_block, i):
            """Rule for the profile constraint. """
            return _block.heat[i] == solar_profile[i] 
        
        def bin_rule(_block, i):
            """Rule for the binary variable."""
            if solar_profile[i] <= 0:
                return _block.bin[i] == 0
            else:
                return _block.bin[i] == 1


        # Declare constraints
        block.bin_rule = Constraint(
            t, 
            rule=bin_rule
        )

        block.profile_constraint = Constraint(
            t, 
            rule=profile_rule
        )







