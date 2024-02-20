from pyomo.environ import *
from pyomo.network import *

class Electrolyzer:
    """Class for constructing chp asset objects."""

    def __init__(self, data) -> None:
        self.data = data

    
    def electrolyzer_block_rule(self, block):
        """Rule for creating a electrolyzer block with default components and constraints."""
        # Get index from model
        t = block.model().t

        # Declare components
        block.bin = Var(t, within=Binary)
        block.hydrogen = Var(t, domain=NonNegativeReals)
        block.power = Var(t, domain=NonNegativeReals)
        block.water = Var(t, domain=NonNegativeReals)
        block.heat = Var(t, domain=NonNegativeReals)

        block.power_in = Port()
        block.power_in.add(block.power, 'power', Port.Extensive, include_splitfrac=False)
        block.hydrogen_out = Port()
        block.hydrogen_out.add(block.hydrogen, 'hydrogen', Port.Extensive, include_splitfrac=False)

        block.heat_out = Port()
        block.heat_out.add(block.heat,'heat',Port.Extensive, include_splitfrac=False)



        # Declare construction rules for constraints
        def power_max_rule(_block, i):
            """Rule for the maximal power consumption."""
            return _block.power[i] <= self.data.loc['max', 'power'] * _block.bin[i]
        

        def power_min_rule(_block, i):
            """Rule for the minimal power consumption."""
            return self.data.loc['min', 'power'] * _block.bin[i] <= _block.power[i]
        

        def hydrogen_depends_on_power_rule(_block, i):
            """Rule for the dependencies between hydrogen output and power demand."""
            hydrogen_min = self.data.loc['min', 'hydrogen']
            hydrogen_max = self.data.loc['max', 'hydrogen']
            power_min = self.data.loc['min', 'power']
            power_max = self.data.loc['max', 'power']

            a = (hydrogen_max - hydrogen_min) / (power_max - power_min)
            b = hydrogen_max - a * power_max

            return _block.hydrogen[i] == a * _block.power[i] + b * _block.bin[i]
        

        def water_depends_on_hydrogen(_block, i):
            """Rule for the dependencies between hydrogen output and water demand."""
            hydrogen_min = self.data.loc['min', 'hydrogen']
            hydrogen_max = self.data.loc['max', 'hydrogen']
            water_min = self.data.loc['min', 'water']
            water_max = self.data.loc['max', 'water']

            a = (water_max - water_min) / (hydrogen_max - hydrogen_min)
            b = water_max - a * hydrogen_max

            return _block.water[i] == a * _block.hydrogen[i] + b * _block.bin[i]
        

        def heat_depends_on_power_rule(_block, i):
            """Rule for the dependencies between heat output and power demand."""
            heat_min = self.data.loc['min', 'heat']
            heat_max = self.data.loc['max', 'heat']
            power_min = self.data.loc['min', 'power']
            power_max = self.data.loc['max', 'power']

            a = (heat_max - heat_min) / (power_max - power_min)
            b = heat_max - a * power_max

            return _block.heat[i] == a * _block.power[i] + b * _block.bin[i]


        # Declare constraints
        block.power_max_constraint = Constraint(
            t,
            rule=power_max_rule
        )
        block.power_min_constraint = Constraint(
            t,
            rule=power_min_rule
        )
        block.hydrogen_depends_on_power_constraint = Constraint(
            t,
            rule=hydrogen_depends_on_power_rule
        )
        block.water_depends_on_hydrogen_constraint = Constraint(
            t,
            rule=water_depends_on_hydrogen
        )
        block.heat_depends_on_power_constraint = Constraint(
            t,
            rule=heat_depends_on_power_rule
        )