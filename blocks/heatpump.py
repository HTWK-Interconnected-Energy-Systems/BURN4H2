from pyomo.environ import *
from pyomo.network import *

class Heatpump:
    """ Class for constructing heatpump objects. """

    def __init__ (self, data) -> None:
        self.data = data


    def heatpump_block_rule(self, block):
        t = block.model().t

        # Define components
        block.bin = Var(t, within=Binary)
        block.power = Var(t, domain=NonNegativeReals)
        block.heat = Var(t, domain=NonNegativeReals)
        block.heat_input = Var(t, domain=NonNegativeReals)

        # Port 1
        block.power_in = Port()
        block.power_in.add(block.power,'power', Port.Extensive, include_splitfrac=False)

        # Port 2
        block.heat_in = Port()
        block.heat_in.add(block.heat_input,'heat',Port.Extensive,include_splitfrac=False)

        # Port 3
        block.heat_out = Port()
        block.heat_out.add(block.heat,'heat',Port.Extensive, include_splitfrac=False)


        def heat_max_rule(_block, i):
            """Rule for the maximal heat output."""
            return _block.heat[i] <= self.data.loc['max', 'heat'] * _block.bin[i]


        def heat_min_rule(_block, i):
            """Rule for the minimal heat output."""
            return self.data.loc['min', 'heat'] * _block.bin[i] <= _block.heat[i]


        def heat_output_depends_on_heat_input_rule(_block, i):
            """ Rule for the dependencies between heat output and power input."""
            return _block.heat[i] == _block.heat_input[i] * 3.4 * _block.bin[i]
        

        def power_depends_on_heat_output_rule(_block, i):
            """Rule for the dependencies between power demand and heat output."""

            power_max = self.data.loc['max', 'power']
            power_min = self.data.loc['min', 'power']        
            heat_max = self.data.loc['max', 'heat']
            heat_min = self.data.loc['min', 'heat']

            a = (power_max - power_min) / (heat_max - heat_min)
            b = power_max - a * heat_max

            return _block.power[i] == a * _block.heat[i] + b * _block.bin[i]


        # Define constraints
        block.heat_max_constraint = Constraint(
            t,
            rule=heat_max_rule
        )
        block.heat_min_constraint = Constraint(
            t,
            rule=heat_min_rule
        )
        block.heat_output_depends_on_power_input_constraint = Constraint(
            t,
            rule=heat_output_depends_on_heat_input_rule
        )
        block.power_depends_on_heat_output_constraint = Constraint(
            t,
            rule=power_depends_on_heat_output_rule
        )