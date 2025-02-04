from pyomo.environ import *
from pyomo.network import *

import pandas as pd


class Heatpump:
    """ Class for constructing heatpump objects. """

    def __init__ (self, name, filepath, index_col=0) -> None:
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
            Block(rule=self.heatpump_block_rule)
        )


    def heatpump_block_rule(self, block):
        t = block.model().t

        # Variables
        block.bin = Var(t, within=Binary)
        block.power = Var(t, domain=NonNegativeReals)
        block.heat = Var(t, domain=NonNegativeReals)
        block.heat_input = Var(t, domain=NonNegativeReals)
    

        # Parameters
        block.Tenv  = Param(t, initialize=20)
        block.Tflow = Param(t, initialize=50)
        block.cop = Param(t)

        # Port 1
        block.power_in = Port()
        block.power_in.add(block.power,'power', Port.Extensive, include_splitfrac=False)

        # Port 2
        block.heat_in = Port()
        block.heat_in.add(block.heat_input,'heat',Port.Extensive,include_splitfrac=False)

        # Port 3
        block.heat_out = Port()
        block.heat_out.add(block.heat,'heat',Port.Extensive, include_splitfrac=False)


        # Define constraints
        def heat_max_rule(_block, i):
            """Rule for the maximal heat output."""
            return _block.heat[i] <= self.data.loc['max', 'heat'] * _block.bin[i]


        def heat_min_rule(_block, i):
            """Rule for the minimal heat output."""
            return self.data.loc['min', 'heat'] * _block.bin[i] <= _block.heat[i]
        
        
        def cop_depends_on_temperature_rule(_block, i):
            """Rule for the dependencies between the coefficient of performance and the temperature."""


           # Diskrete Stützstellen für Umgebungstemperatur und Vorlauftemperatur
            env_temps = [0, 10, 20]       # Beispielwerte
            flow_temps = [30, 40, 50]     # Beispielwerte

            cop_data = {
                (0, 0): 3.1, (0, 1): 2.9, (0, 2): 2.6,
                (1, 0): 3.5, (1, 1): 3.2, (1, 2): 2.8,
                (2, 0): 4.0, (2, 1): 3.6, (2, 2): 3.2,
            }
             
            # Define Sets
            block.I = RangeSet(0, len(env_temps) - 1)
            block.J = RangeSet(0, len(flow_temps) - 1)
           

            # Variables for the weights (gamma_ij)
            block.gamma = Var(block.I, block.J, bounds=(0, None))

            # CoP-Variable
            block.cop = Var()

            # Weight sum == 1
            def sum_gamma_rule(m):
                return sum(m.gamma[i, j] for i in m.I for j in m.J) == 1
            block.sum_gamma_con = Constraint(rule=sum_gamma_rule)

            # Environment temperature as a linear combination
            def t_env_rule(m):
                return m.Tenv == sum(env_temps[i] * m.gamma[i, j] for i in m.I for j in m.J)
            block.t_env_con = Constraint(rule=t_env_rule)

            # Flow temperature as a linear combination
            def t_flow_rule(m):
                return m.Tflow == sum(flow_temps[j] * m.gamma[i, j] for i in m.I for j in m.J)
            block.t_flow_con = Constraint(rule=t_flow_rule)

            # CoP as a linear combination (linear approximation)
            def cop_rule(m):
                return m.cop == sum(cop_data[(i, j)] * m.gamma[i, j] for i in m.I for j in m.J)
            block.cop_con = Constraint(rule=cop_rule)



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
        block.cop_depends_on_heat_output_constraint = Constraint(
            t,
            rule=power_depends_on_heat_output_rule
        )