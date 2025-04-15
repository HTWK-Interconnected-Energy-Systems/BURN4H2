from pyomo.environ import *
from pyomo.network import *

import pandas as pd


class HeatpumpStageOne:
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

        # Heatpump Variables
        block.bin = Var(t, within=Binary) # Binärvariable
        block.power = Var(t, domain=NonNegativeReals) # Power needed for the heat pump 
        block.heat_input = Var(t, domain=NonNegativeReals) # Q_zu 
        block.heat = Var(t, domain=NonNegativeReals) # Q_0
        
        # Parameters
        block.delta_T_min = Param(t, initialize=5)  
    
        # Parameters Kältemittel
        block.R = Param(t, initialize=488) #spezifischer Gaskonstante R-717 [J/kgK]
        block.k = Param(t, initialize=1.31) # Iseotropenexponent R-717  

        
        # Zustandsgrößen Kreisprozess 

        # Äußere Verhältnisse für Medium Wasser
        block.T_q  = Param(t, initialize=16+273.15) # Temperatur Quelle in Kelvin -> äußeres Medium
        block.T_k = Param(t, initialize=35+273.15) # Temperatur Senke in Kelvin -> äußeres Medium
          
        # Innere Verhältnisse für Kältemittel R-717
        # Parameters Druck p
        block.p1 = Param(t, initialize=5.5 * 10**5) # bar in Pa Eintrittsdruck Verdichter  
        block.p2 = Param(t, initialize=16 * 10**5) # bar in Pa Austrittsdruck Verdichter
        block.p3 = Param(t, initialize=16 * 10**5) # bar in Pa Austrittsdruck Kondensator
        block.p4 = Param(t, initialize=5.5 * 10**5) # bar in Pa Eintrittsdruck Verdampfer

        # Parameter Temperatur T
        block.T1 = Param(t, initialize=8+273.15) # Grad Celsius in Kelvin 
        block.T2 = Param(t, initialize=85+273.15) # Grad Celsius in Kelvin 
        block.T3 = Param(t, initialize=40+273.15) # Grad Celsius in Kelvin 
        block.T4 = Param(t, initialize=8+273.15) # Grad Celsius in Kelvin 

        # Parameter Enthalpie h
        block.h1 = Param(t, initialize=1480) # Enthalpie kJ/kg 
        block.h2 = Param(t, initialize=1625) # Enthalpie kJ/kg
        block.h3 = Param(t, initialize=395) # Enthalpie kJ/kg
        block.h4 = Param(t, initialize=395) # Enthalpie kJ/kg

        # Verdichter 

        # Variables
        block.capacity_compressor = Var(t, domain=NonNegativeReals) # Verdichterleistung [MW]
        block.volume_flow = Var(t, domain=NonNegativeReals) # Volumenstrom Verdichter [m^3/s]
        block.massflow_refigerant = Var(t, domain=NonNegativeReals) # Massenstrom Kältemittel [kg/s]
        block.swept_volume = Var(t, domain=NonNegativeReals) # Hubraum Verdichter [m^3/s]

        # Parameters
        block.electrical_efficiency_compressor = Param(t, initialize=0.9) # Elektrische Effizienz Verdichter
        block.n = Param(t, initialize=1500/60) # Drehzahl Verdichter [1/min] in [1/s] !!! muss zwischen 500 und 1500 liegen !!!
        block.z = Param(t, initialize=6) # Anzahl der Zylinder Verdichter


        # Port 1
        block.power_in = Port()
        block.power_in.add(block.power,'power', Port.Extensive, include_splitfrac=False)

        # Port 2
        block.heat_in = Port()
        block.heat_in.add(block.heat_input,'waste_heat',Port.Extensive,include_splitfrac=False)

        # Port 3
        block.heat_out = Port()
        block.heat_out.add(block.heat,'waste_heat',Port.Extensive, include_splitfrac=False)
     
       
        # Expressions
        def ideal_cop_rule(_block, i):
            """
            Expression: COP_Ideal
            Rule for the ideal COP. Carnot-Wirkungsgrad für Wärmepumpen.
            COP_ideal = T_k / (T_k - T_q) 
            """
            return (_block.T3[i]) / ((_block.T3[i]) - (_block.T1[i]))
        
        def efficiency_rule(_block, i):
            """
            Expression: d 
            Rule for the factor to calculate the real COP.
            """
            # Factors for working fluid R-717 
            A = 0.6932
            B = -0.4851
            return A + B / _block.ideal_cop[i]
        
        def real_cop_rule(_block, i):
            """
            Expression: COP_ideal
            Rule for the real coefficient of performance.
            """
            return _block.ideal_cop[i] * _block.d[i]
        

        # Define expressions
        block.ideal_cop = Expression(
            t, 
            rule=ideal_cop_rule
        )

        block.d = Expression(
            t, 
            rule=efficiency_rule
        )

        block.real_cop = Expression(
            t, 
            rule=real_cop_rule
        )   


        # Constraints
        def heat_pump_operation_rule(_block, i):
            """Rule for the heat pump operation."""
            return _block.heat[i] == _block.real_cop[i]  * _block.capacity_compressor[i]  # in MW
        
        def capacity_compressor_rule(_block, i):
            """
            Variable: P_v
            Rule for the compressor capacity. P_v depends on the mass flow and the enthalpy difference.
            Assuption: isentropic compression
            """
            return _block.capacity_compressor[i]  == (_block.massflow_refigerant[i]) * (_block.h2[i]-_block.h1[i]) / 1000  # in MW
        
        def massflow_depends_on_heat_input_rule(_block, i):
            """
            Variable: m_0
            Rule for the dependencies between mass flow and heat input.
            """
            return _block.massflow_refigerant[i] == ((_block.heat_input[i]*1000)/ (_block.h1[i] - _block.h4[i])) # in kg/s
        
        def volume_flow_rule(_block, i):
            """
            Variable: V
            Rule for the volume flow.
            """
            return _block.volume_flow[i] == (_block.massflow_refigerant[i] * (_block.R[i] * _block.T1[i])) / _block.p1[i] # in m^3/s
       
        def swept_volume_rule(_block, i):
            """
            Variable: swept_volume
            Rule for the swept volume.
            """
            return _block.swept_volume[i] == _block.volume_flow[i] / _block.n[i] * _block.z[i] # m^3/s
        
        def power_rule(_block, i):
            """Rule for the power input. (Elektrische Leistung  Verdichter in MW)"""
            return _block.power[i]  == _block.capacity_compressor[i] / _block.electrical_efficiency_compressor[i]


        # Define constraints
        block.heat_pump_operation_constraint = Constraint(
            t,
            rule=heat_pump_operation_rule
        )

        block.capacity_compressor_constraint = Constraint(
            t,
            rule=capacity_compressor_rule
        )

        block.massflow_depends_on_heat_input_constraint = Constraint(
            t,
            rule=massflow_depends_on_heat_input_rule
        )

        block.power_constraint = Constraint(
            t,
            rule=power_rule
        )

        block.volume_flow_constraint = Constraint(
            t,
            rule=volume_flow_rule
        )

        block.swept_volume_constraint = Constraint(
            t,
            rule=swept_volume_rule
        )



class HeatpumpStageTwo:
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

        # Heatpump Variables
        block.bin = Var(t, within=Binary) # Binary operation variable
        block.power = Var(t, domain=NonNegativeReals) # Electrical power consumption [MW]
        block.heat_input = Var(t, domain=NonNegativeReals) # Q_zu: Heat input to the heat pump [MW]
        block.heat = Var(t, domain=NonNegativeReals) # Q_0: Heat output from the heat pump [MW]
        
        # Parameters
        block.delta_T_min = Param(t, initialize=5) 
    
        # Parameters Kältemittel
        block.R = Param(t, initialize=488) # Specific gas constant for R-717 [J/kgK]
        block.k = Param(t, initialize=1.31) # Isentropic exponent for R-717

        
        # Zustandsgrößen Kreisprozess 

        # Äußere Verhältnisse für Medium Wasser
        block.T_q  = Param(t, initialize=30+273.15) # Source temperature, outer medium [K]
        block.T_k = Param(t, initialize=80+273.15) # Sink temperature, outer medium [K]
          
        # Internal conditions for R-717 refrigerant
        # Pressure parameters [Pa]  
        block.p1 = Param(t, initialize=10 * 10**5) # Compressor inlet pressure [Pa]
        block.p2 = Param(t, initialize=45 * 10**5) # Compressor outlet pressure [Pa]
        block.p3 = Param(t, initialize=45 * 10**5) # Condenser outlet pressure [Pa]
        block.p4 = Param(t, initialize=10 * 10**5) # Evaporator inlet pressure [Pa]

        # Temperature parameters [K]
        block.T1 = Param(t, initialize=25+273.15) # Compressor inlet temperature [K]
        block.T2 = Param(t, initialize=145+273.15) # Compressor outlet temperature [K]
        block.T3 = Param(t, initialize=85+273.15) # Condenser outlet temperature [K]
        block.T4 = Param(t, initialize=25+273.15) # Evaporator inlet temperature [K]

        # Enthalpy parameters [kJ/kg]
        block.h1 = Param(t, initialize=1490) # Compressor inlet enthalpy [kJ/kg]
        block.h2 = Param(t, initialize=1710)  # Compressor outlet enthalpy [kJ/kg]
        block.h3 = Param(t, initialize=650) # Condenser outlet enthalpy [kJ/kg]
        block.h4 = Param(t, initialize=650) # Evaporator inlet enthalpy [kJ/kg]

        # Compressor Variables
        block.capacity_compressor = Var(t, domain=NonNegativeReals) # Compressor power output [MW]
        block.volume_flow = Var(t, domain=NonNegativeReals) # Compressor volume flow [m³/s]
        block.massflow_refigerant = Var(t, domain=NonNegativeReals) # Refrigerant mass flow [kg/s]
        block.swept_volume = Var(t, domain=NonNegativeReals) # Compressor swept volume [m³]

        # Compressor Parameters
        block.electrical_efficiency_compressor = Param(t, initialize=0.9)  # Electrical efficiency of compressor
        block.n = Param(t, initialize=1500/60) # Compressor speed [1/s] (converted from rpm)
        block.z = Param(t, initialize=6)  # Number of compressor cylinders


        # Port 1
        block.power_in = Port()
        block.power_in.add(block.power,'power', Port.Extensive, include_splitfrac=False)

        # Port 2
        block.waste_heat_in = Port()
        block.waste_heat_in.add(block.heat_input,'waste_heat',Port.Extensive, include_splitfrac=False)

        # Port 3
        block.heat_out = Port()
        block.heat_out.add(block.heat,'wp_heat',Port.Extensive, include_splitfrac=False)
     
       
        # Expressions
        def ideal_cop_rule(_block, i):
            """
            Expression: COP_Ideal
            Rule for the ideal COP. Carnot-Wirkungsgrad für Wärmepumpen.
            COP_ideal = T_k / (T_k - T_q) 
            """
            return (_block.T3[i]) / ((_block.T3[i]) - (_block.T1[i]))
        
        def efficiency_rule(_block, i):
            """
            Expression: d 
            Rule for the factor to calculate the real COP.
            """
            # Factors for working fluid R-717 
            A = 0.6932
            B = -0.4851
            return A + B / _block.ideal_cop[i]
        
        def real_cop_rule(_block, i):
            """
            Expression: COP_ideal
            Rule for the real coefficient of performance.
            """
            return _block.ideal_cop[i] * _block.d[i]
        

        # Define expressions
        block.ideal_cop = Expression(
            t, 
            rule=ideal_cop_rule
        )

        block.d = Expression(
            t, 
            rule=efficiency_rule
        )

        block.real_cop = Expression(
            t, 
            rule=real_cop_rule
        )   


        # Constraints
        def heat_pump_operation_rule(_block, i):
            """Rule for the heat pump operation."""
            return _block.heat[i] == _block.real_cop[i]  * _block.capacity_compressor[i]  # in MW
        
        def capacity_compressor_rule(_block, i):
            """
            Variable: P_v
            Rule for the compressor capacity. P_v depends on the mass flow and the enthalpy difference.
            Assuption: isentropic compression
            """
            return _block.capacity_compressor[i]  == (_block.massflow_refigerant[i]) * (_block.h2[i]-_block.h1[i]) / 1000 # in MW
        
        def massflow_depends_on_heat_input_rule(_block, i):
            """
            Variable: m_0
            Rule for the dependencies between mass flow and heat input.
            """
            return _block.massflow_refigerant[i] == ((_block.heat_input[i]*1000)/ (_block.h1[i] - _block.h4[i])) # in kg/s
        
        def volume_flow_rule(_block, i):
            """
            Variable: V
            Rule for the volume flow.
            """
            return _block.volume_flow[i] == (_block.massflow_refigerant[i] * (_block.R[i] * _block.T1[i])) / _block.p1[i] # in m^3/s
       
        def swept_volume_rule(_block, i):
            """
            Variable: swept_volume
            Rule for the swept volume.
            """
            return _block.swept_volume[i] == _block.volume_flow[i] / _block.n[i] * _block.z[i] # m^3/s
        
        def power_rule(_block, i):
            """Rule for the power input. (Elektrische Leistung  Verdichter in MW)"""
            return _block.power[i]  == _block.capacity_compressor[i] / _block.electrical_efficiency_compressor[i]


        # Define constraints
        block.heat_pump_operation_constraint = Constraint(
            t,
            rule=heat_pump_operation_rule
        )

        block.capacity_compressor_constraint = Constraint(
            t,
            rule=capacity_compressor_rule
        )

        block.massflow_depends_on_heat_input_constraint = Constraint(
            t,
            rule=massflow_depends_on_heat_input_rule
        )

        block.power_constraint = Constraint(
            t,
            rule=power_rule
        )

        block.volume_flow_constraint = Constraint(
            t,
            rule=volume_flow_rule
        )

        block.swept_volume_constraint = Constraint(
            t,
            rule=swept_volume_rule
        )

    


   



       

