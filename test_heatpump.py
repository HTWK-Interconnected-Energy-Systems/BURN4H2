from pyomo.environ import *
import blocks.heatpump_new as hp  # Annahme: Die Klasse ist in einer Datei namens heatpump.py

# Testmodell
def test_heatpump():
    model = ConcreteModel()

    # Path
    PATH_IN = "data/input/"
    PATH_OUT = "data/output/"
    
    # Zeitstufen (Dummy-Zeitschritte)
    model.t = RangeSet(1, 3)  # Drei Zeitschritte

    # Instanziiere eine Heatpump
    heatpump = hp.Heatpump(
        "test_hp",
        PATH_IN + "assets/heatpump.csv"
    )

    # Füge die Heatpump dem Modell hinzu
    heatpump.add_to_model(model)

    # Beispielobjektiv: Maximiere die Wärmeerzeugung
    model.obj = Objective(expr=sum(model.test_hp.heat[t] for t in model.t), sense=maximize)

    # Löse das Modell
    solver = SolverFactory('gurobi')  
    result = solver.solve(model, tee=True)

    # Ergebnisse ausgeben
    print("Lösungsstatus:", result.solver.termination_condition)
    print("Heat-Ausgabe:")
    for t in model.t:
        print(f"t={t}: {model.test_hp.heat[t].value} kW")


# Hauptfunktion für den Test
if __name__ == "__main__":
    test_heatpump()
