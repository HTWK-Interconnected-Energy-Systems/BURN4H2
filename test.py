import numpy as np

my_charge_list =    [1, 0, 0, 1, 0, 1, 0, 0, 0, 0, 1, 1]
my_discharge_list = [0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0]
print(my_charge_list, 'charging bin')
print(my_discharge_list, 'discharging bin')

my_switches = [my_charge_list[t] - my_discharge_list[t] for t, _ in enumerate(my_charge_list)]
print(my_switches, 'switches')

my_checks = []
#create auxiliary switches list to remember last switch status like switches: [1, 0, -1] -> [1, 1, -1]
aux_switches = [(lambda i : i if i else my_switches[j-1])(i) for j, i in enumerate(my_switches)]
print(aux_switches, 'aux_switches')

for pos, value in enumerate(my_switches):
    if pos%4 == 0:
        my_checks.append(0)
        continue

    check_value = abs(value - aux_switches[pos - 1])

    if check_value > 1:
        my_checks.append(check_value)
    else:
        my_checks.append(0)

print(my_checks, 'checks')


for pos, value in enumerate(my_checks):
    if pos%4 == 3:
        if pos == 3:
            print(sum(my_checks[0:pos+1]))
            continue

        print(sum(my_checks[pos:pos-4:-1]))


# Greift zu kurz. Ladezyklenbetrachtung muss zusätzlich noch zweite Binärvariable berücksichtigen