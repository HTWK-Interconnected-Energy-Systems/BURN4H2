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
        block.heat_output = Var(t, domain=NonNegativeReals)
        block.heat_input = Var(t, domain=NonNegativeReals)

        # Port 1
        block.power_in = Port()
        block.power_in.add(block.power,'power', Port.Extensive, include_spiltfrac=False)

        # Port 2
        block.heat_in = Port()
        block.heat_in.add(block.heat_input,'heat',Port.Extensive,include_splitfrac=False)

        # Port 3
        block.heat_out = Port()
        block.heat_out.add(block.heat_output,'heat',Port.Extensive, include_splitfrac=False)


        def power_max_rule(_block, i):
            """Rule for the maximal power input."""
            return _block.power[i] <= self.data.loc['max', 'power'] * _block.bin[i]


        def power_min_rule(_block, i):
            """Rule for the minimal power input."""
            return self.data.loc['min', 'power'] * _block.bin[i] <= _block.power[i]


        def heat_output_depends_on_heat_input_rule(_block, i):
            """ Rule for the dependencies between heat output and power input."""
            return _block.heat_output[i] * _block.bin[i] == _block.heat_input[i] * 3
        

        def power_depends_on_heat_output_rule(_block, i):
            return _block.power[i] == _block.heat_output[i] / 3
        

        # Define constraints
        block.power_max_constraint = Constraint(
            t,
            rule=power_max_rule
        )
        block.power_min_constraint = Constraint(
            t,
            rule=power_min_rule
        )
        block.heat_output_depends_on_power_input_constraint = Constraint(
            t,
            rule=heat_output_depends_on_heat_input_rule
        )
        block.power_depends_on_heat_output_constraint = Constraint(
            t,
            rule=power_depends_on_heat_output_rule
        )