import pyomo.environ as pyo

model = pyo.ConcreteModel()

# Diskrete Stützstellen für Umgebungstemperatur und Vorlauftemperatur
env_temps = [0, 10, 20]       # Beispielwerte
flow_temps = [30, 40, 50]     # Beispielwerte


# Vorgabewerte für CoP (Index (i, j) entspricht (env_temps[i], flow_temps[j]))
cop_data = {
    (0, 0): 3.1, (0, 1): 2.9, (0, 2): 2.6,
    (1, 0): 3.5, (1, 1): 3.2, (1, 2): 2.8,
    (2, 0): 4.0, (2, 1): 3.6, (2, 2): 3.2,
}

# Sets
model.I = pyo.RangeSet(0, len(env_temps) - 1)
model.J = pyo.RangeSet(0, len(flow_temps) - 1)

# Variablen für die Gewichte (gamma_ij)
model.gamma = pyo.Var(model.I, model.J, bounds=(0, None))

# CoP-Variable
model.cop = pyo.Var()

# Zusätzliche Variablen für Tenv und Tflow optional:
# model.Tenv = pyo.Var()
# model.Tflow = pyo.Var()

model.Tenv = pyo.Param(initialize=20)
#model.Tenv = pyo.Param()
model.Tflow = pyo.Param(initialize=40)

model.linear = pyo.Var()

# Gewichtssumme == 1
def sum_gamma_rule(m):
    return sum(m.gamma[i, j] for i in m.I for j in m.J) == 1
model.sum_gamma_con = pyo.Constraint(rule=sum_gamma_rule)

# Umgebungstemperatur und Vorlauftemperatur als Linearkombination
def t_env_rule(m):
    return m.Tenv == sum(env_temps[i] * m.gamma[i, j] for i in m.I for j in m.J)
model.t_env_con = pyo.Constraint(rule=t_env_rule)

def t_flow_rule(m):
    return m.Tflow == sum(flow_temps[j] * m.gamma[i, j] for i in m.I for j in m.J)
model.t_flow_con = pyo.Constraint(rule=t_flow_rule)

# CoP als Linearkombination (lineare Approximation)
def cop_rule(m):
    return m.cop == sum(cop_data[(i, j)] * m.gamma[i, j] for i in m.I for j in m.J)
model.cop_con = pyo.Constraint(rule=cop_rule)


# def linear_rule_1(m):
#     return m.linear == m.Tflow * m.Tenv * m.cop
# model.linear_con = pyo.Constraint(rule=linear_rule_1)


def linear_rule_2(m):
    return m.linear == m.Tflow * m.Tenv + m.cop
model.linear_con = pyo.Constraint(rule=linear_rule_2)

# Beispiel: Maximierung des CoP
model.obj = pyo.Objective(expr=model.linear, sense=pyo.maximize)

# Danach wie gewohnt lösen (z.B. mit CBC oder GLPK)
solver = pyo.SolverFactory('gurobi')
solver.solve(model, tee=True)

print(len(env_temps), len(flow_temps))
print(model.Tenv.value, model.Tflow.value, model.cop.value)