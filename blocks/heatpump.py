from pyomo.environ import *
from pyomo.network import *

class Heatpump:
    """ Class for constructing heatpump objects. """

    def __init__ (self, data, **kwargs) -> None:
        self.data = data
        self.kwargs = kwargs
        self.validate_kwargs()

    def validate_kwargs(self):
        allowed_kwargs = ['link_heatpump_to_electrolyzer']

        for key in self.kwargs:
            if key not in allowed_kwargs:
                raise(KeyError(f'Unexpected kwarg "{key}" detected.'))


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

        # Define Construction Rules
        def power_min_rule(_block, i):
            """Rule for the minimal power input."""
            return self.data.loc['min', 'power'] * _block.bin[i] <= _block.power[i]

        def heat_output_depends_on_power_rule(_block, i):
            """ Rule for the dependencies between heat output and power input """
            return _block.heat_output[i] == _block.bin[i]*(_block.heat_input[i] + 3 *_block.power[i]) # factor 3.0 considered

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
            rule=heat_output_depends_on_power_rule
        )

        if 'link_heatpump_to_electrolyzer' in self.kwargs and self.kwargs['link_heatpump_to_electrolyzer'] == 1:

            block.heat_consumption = Var(
                t,
                domain=NonNegativeReals
            )

            block.heat_input_equal_to_heat_consumption_constraint = Constraint(
                t,
                rule= lambda _block, i: block.heat_consumption[i] * block.bin[i] == block.heat_input[i]
            )

            block.heat_input_operation_constraint = Constraint(
                t,
                rule= lambda _block,i: (block.heat_input[i]-1)*block.bin[i] >= 0
            )
            block.heat_input_operation_constraint_2 = Constraint(
                t,
                rule=lambda _block, i: block.heat_input[i] >= 0.001 * block.bin[i]
            )


