<!-- omit in toc -->
# BURN4H2-Framework

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Pyomo](https://img.shields.io/badge/pyomo-6.0+-orange.svg)](https://pyomo.readthedocs.io/)

<!-- omit in toc -->
## Table of Contents 
- [Overview](#overview)
- [Project Background](#project-background)
- [Framework Architecture](#framework-architecture)
- [System Boundaries and Assumptions](#system-boundaries-and-assumptions)
- [Components](#components)
- [Topology](#topology)
- [Installation and Usage](#installation-and-usage)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
  - [Running Simulations](#running-simulations)
- [Output and Results](#output-and-results)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

The BURN4H2-Framework is an open-source optimization framework for industrial energy systems with a focus on sector coupling between power and heat. The framework enables detailed modeling and optimization of complex energy systems including hydrogen integration, combined heat and power units, heat pumps, renewable energy sources, and various storage technologies.

## Project Background

This framework was developed as part of the BURN4H2 project, specifically within the sub-project "Systemmodellierung und Regelungskonzeptentwicklung" (System Modeling and Control Concept Development). The framework is based on scientifically established methods and utilizes the Python programming language in combination with the algebraic modeling language Pyomo to formulate a mixed-integer linear programming (MILP) problem, which is solved using the Gurobi solver.

### Key Features

- **Optimization Objective**: Minimization of total system operating costs
- **Modeling Approach**: Bottom-up analytical approach with detailed component modeling
- **Sector Coupling**: Integration of electrical, thermal, and hydrogen energy sectors
- **Modularity**: Flexible framework structure allowing easy adaptation without core modifications
- **Real-world Data**: Integration of actual plant data, load profiles, and site-specific infrastructure conditions
- **Transparency**: Complete disclosure of model structure and technical assumptions

The modular design enables flexible adaptation of energy system models without intervention in the core structure. High site-specific modeling depth is achieved through the use of real plant data, load profiles, and infrastructural site conditions. Complete disclosure of the model structure and technical assumptions ensures transparency and traceability of results.

## Framework Architecture

The framework follows a modular structure with the following core components:

```
burn4h2/
├── main.py              # Main optimization model and execution logic
└── blocks/              # Modular component definitions
    ├── chp.py          # Combined Heat and Power units
    ├── grid.py         # Grid connections (electrical, heat, hydrogen)
    ├── heatpump.py     # Heat pump systems
    ├── storage.py      # Storage systems (battery, thermal, hydrogen)
    ├── res.py          # Renewable energy sources
    ├── collector.py    # Solar thermal collectors
    └── electrolyzer.py # Hydrogen production
```

## System Boundaries and Assumptions

### General Model Assumptions

- **Optimization Method**: Mixed-integer linear programming (MILP)
- **Forecast Quality**: Perfect forecast assumed
- **Temporal Resolution**: Hourly time steps
- **Transmission**: No transmission losses between system components
- **Grid Infrastructure**: Unlimited flow capacity in network connections
- **System Operation**: No ramp rate constraints
- **Energy Balance**: Perfect balancing of supply and demand at each time step
- **Component Operation**: Ideal operation without degradation effects (unless specified)

## Components

The framework includes the following energy system components:

### Power Generation
- **Combined Heat and Power (CHP)**: Two identical units with configurable hydrogen admixture (0%, 30%, 50%, 100%)
- **Photovoltaics**: Solar power generation with capacity factor profiles
- **Grid Connection**: Electrical import/export capabilities

### Heat Generation
- **Heat Pumps**: Two-stage ammonia-based heat pump system
- **Solar Thermal**: Collector systems for thermal energy generation
- **Waste Heat Recovery**: Integration of waste heat from CHP units

### Storage Systems
- **Battery Storage**: Electrical energy storage
- **Thermal Storage**: Heat storage for district heating
- **Stratified Heat Storage**: Multi-zone thermal storage
- **Geothermal Storage**: Ground-coupled heat storage
- **Hydrogen Storage**: Hydrogen energy storage

### Grid Infrastructure
- **Electrical Grid**: Power import/export and distribution
- **Heat Grid**: District heating network
- **Local Heat Grid**: Localized heat distribution
- **Hydrogen Grid**: Hydrogen supply infrastructure
- **Natural Gas Grid**: Natural gas supply
- **Waste Heat Grid**: Waste heat collection and distribution

## Topology

The energy system topology demonstrates the interconnection of all components through a network of energy flows:

![System Topology](docs/images/Demomodell.png)
*Figure 1: Schematic topology of the energy system model*

The system uses a port-based connection approach where each component has defined input and output ports for different energy carriers (electrical power, heat, hydrogen, natural gas).

## Installation and Usage

### Prerequisites

- Python 3.8 or higher
- Gurobi optimization solver (license required)
- Required Python packages (see `requirements.txt`)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/0815Paul/BURN4H2.git
cd burn4h2-framework
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure Gurobi solver according to your license.

### Configuration

Configuration files are located in `config/templates/`. Each configuration defines:
- System parameters (prices, capacities, etc.)
- Time series data references
- Component specifications
- Scenario-specific settings

Available configurations:
- `dummy.json` - Basic demonstration scenario
- Scenario-specific configurations for different use cases

### Running Simulations

#### Default Configuration
```bash
python main.py
```

#### Specific Configuration
```bash
python main.py --config your_config.json
```

#### Use Case Batch Processing
```bash
python main.py --use-case uc1
```

## Output and Results

### Result Files

The framework generates timestamped output files:

- **CSV Output**: `{config}_{timestamp}_output.csv`
  - Time series results for all variables and parameters
  - Component operational states and energy flows
  - Cost and emission data

- **Metadata**: `{config}_{timestamp}_metadata.json`
  - Solver settings and performance
  - Configuration parameters
  - System specifications

- **Cost Analysis**: `{config}_{timestamp}_costs.json`
  - Detailed cost breakdown
  - Revenue analysis
  - Economic performance indicators

### Directory Structure
```
data/output/
├── use_case_1/
│   ├── scenario_1/
│   │   ├── config_timestamp_output.csv
│   │   ├── config_timestamp_metadata.json
│   │   └── config_timestamp_costs.json
│   └── scenario_2/
└── dummy/
```

## Contributing

**Please note: This project is now closed and is no longer under active development.**

This framework was developed as part of the BURN4H2 research project and represents a completed research deliverable. While the code is made available for transparency and reproducibility, no further development or feature additions are planned.

### Data Availability

The framework includes sample data in the `dummy.json` configuration for demonstration purposes. However, please note:

- **Real operational data** (electricity prices, gas prices, load profiles, etc.) used in the original research cannot be shared due to **data protection and confidentiality agreements**
- Only **anonymized dummy data** is provided in the public repository
- The dummy configuration demonstrates the framework's functionality but does not represent actual operational scenarios

## License

This project is licensed under the [MIT License](LICENSE) - see the LICENSE file for details.

---

**Contact**: This is an archived research project. For technical questions, please refer to the documentation within the repository.
