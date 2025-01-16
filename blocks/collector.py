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
        
        # Declare components
        block.bin = Var(t, within=Binary)
        block.heat = Var(t, domain=NonNegativeReals)



        # Declare construction rules for constraints
        def heat_max_rule(_block, i):
            """Rule for the maximal heat production."""
            return _block.heat[i] <= self.data.loc['max', 'heat'] * _block.bin[i]
        
        def heat_min_rule(_block, i):
            """Rule for the minimal heat production."""
            return self.data.loc['min', 'heat'] * _block.bin[i] <= _block.heat[i]
        
        def heat_depends_on_radiation_rule(_block, i):
            """Rule heat production, which depends on the solar radiation."""
            efficiency = self.data.loc['value', 'efficiency']
            area = self.data.loc['value', 'area']
            radiation = self.data.loc['value', 'radiation']
            return _block.heat[i] == radiation * area * efficiency * _block.bin[i]       
          
        # Declare constraints
        block.heat_max = Constraint(t, rule=heat_max_rule)
        block.heat_min = Constraint(t, rule=heat_min_rule)
        block.heat_depends_on_radiation = Constraint(t, rule=heat_depends_on_radiation_rule)


