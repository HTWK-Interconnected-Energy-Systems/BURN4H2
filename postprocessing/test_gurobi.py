from pyomo.environ import ConcreteModel, Var, Objective, Constraint, SolverFactory, maximize

# Modell erstellen
model = ConcreteModel()

# Variable definieren mit unterer Grenze
model.x = Var(bounds=(0, None))  # x muss >= 0 sein

# Zielfunktion: Maximierung von x + 5
model.obj = Objective(expr=model.x + 5, sense=maximize)

# Restriktion hinzufügen
model.con = Constraint(expr=model.x <= 10)

# Solver definieren
solver = SolverFactory("gurobi")

# Solver ausführen
result = solver.solve(model, tee=True)

# Ergebnis anzeigen
model.x.display()