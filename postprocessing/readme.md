# Postprocessing
## General information: 
Postprocessing is a folder with scripts that process data from folder output. 
It is coded in jupyter notebook. Typically it generates diagrams and plots for visualization results of linear optimization. 
The following document explains the structure, script functions and what users need to know and keep in mind to use the script. 
Detailed input and output information are documented in docstrings of functions. 

## Installation
Apart from standard installations like a python interpreter and jupyter notebook the following packages are necessary for installation:
- pandas
- numpy
- matplotlib.pyplot 
- Normalize, ListedColormap, LinearSegmentedColormap
- colorcet
- os
- datetime
- json
- Image

## share_of_assets.ipynb
### What is it for?
This script processes data from output_time_series.csv. 
Focus lies on generating stacked box plots, that show supply of different assets for a given time period (f. e. in summer) and granularity (weeks, months etc.). It is possible to add a tag in plot that shows the percentage of an asset or a group of assets on total supply.

### Structure
- 0.0 Import of packages
- 0.1 General Helpers
- 0.2 Helpers for Colormaps
- 0.3 Load data from csv output
- 1 Functions for filtering and calculating values for set time granularity
- 2 Functions for setting assets and parameters to be visualized
- 3 Functions for plotting and saving bar chart for share of assets
- 4 Main Script

### 0.0 Import of packages
Needs to be executed to load necessary libraries for following code.

### 0.1 General Helpers
**functions**: 
- print_df
- change_energy_units
- get_weeks_from_timestamp
- get_months_from_timestamp

General Helpers can be used all the time and may be **outsourced soon into a separate file** for easy access from anywhere in postprocessing.

**print_df**: 
Function helps printing DataFrames in an appropriate format for console output. It's usable for any DataFrame.

![print_df](data/postprocessing/zzz_pictures/print_df_example.png)

**change_energy_units**: 
If you input a list and the actual and target unit you want the data to appear you get a list as a return value with adjusted values in your target unit. It is at the moment just usable for: MWh, GWh, kWh and MW, GW, kW. Other units need to be added. If another unit is given you get a key error message, that the given unit is not fitting function. Values in lists are usually of type float. 

![change_energy_units](data/postprocessing/zzz_pictures/change_energy_unit_example.png)

**get_weeks_from_timestamp**: 
If a list of timestamps with start and enddates of weeks is given with the format "['YYYY-MM-DD/YYYY-MM-DD', ...]" the function takes the start date of the week and looks for fitting KW for plotting. It gives back the list with KWs. # Sagen, wieso die Werte so kommen und woher.

![get_weeks_from_timestamp](data/postprocessing/zzz_pictures/get_weeks_example.png)

**get_months_from_timestamp**: 
If a list of timestamps with months in this format is given ['YYYY-MM', ...], the function cuts of the string of the year, so just the month-date is left. The list of months is given back as return value. # Sagen, wieso die Werte so kommen und woher.

![get_months_from_timestamp](data/postprocessing/zzz_pictures/get_months_example.png)

### 0.2 Helpers for Colormaps
**functions**:
- register_colormap
- shift_colormap
- darken_colormap
- get_color_for_key
- load_color_data_from_json
- save_colors_for_key_json
- show_color_rgba

**register_colormap**: 
Sometimes colormaps are from another library or created by ourselves, so they are not listed in matplotlib. In this case they need to be registered if we want to process them as usual with plt commands. Therefore the function registers colormaps in plt from another library called "colorcet". Other libraries are at the moment not included. The function checks if the colorcet is registered in plt. If not it loads it from plt or registers it for cc. Afterwards the colormap can be used as any other plt colormap by name.

**shift_colormap**: 
Sometimes just special parts of a colormap are interesting for visualization. Especially black and white are colors that are not always requested. Therefore this function allows to shift the color spectrum to parts that are interesting. To shift a colormap we need to set a start and end parameter. Parameters need to be set between 0 and 1. Default values are start: 0 and end: 1. See the example below: 

```
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.colors import LinearSegmentedColormap

def register_colormap(cmap_name: str):
    """load colormap from plt and register in plt if colormap from cc.

    Args:
        cmap_name (str): colormap name as string registered in plt or cc.

    Returns:
       LinearSegmentedColormap : loaded colormap from plt.
    """
    if cmap_name not in plt.colormaps():
        colormap = cc.cm[cmap_name]  # load colormap from colorcet
        plt.register_cmap(name=cmap_name, cmap=ListedColormap(colormap(np.linspace(0, 1, 256))))  # only if not available register colormap
    else:
        colormap = plt.get_cmap(cmap_name) # if already registered in matplotlib load map from there.
    return colormap

def shift_colormap(cmap_name: str, start=0.0, end=1.0, amount_colors=256):
    """
    Returns a new colormap that contains a partial area of the original colormap.
    """
    colormap = register_colormap(cmap_name)
    return LinearSegmentedColormap.from_list(
        f"{cmap_name}_adjusted", colormap(np.linspace(start, end, amount_colors))
    )

# Define input data
cmap_name = "viridis"
start, end = 0.2, 0.8  # Shift colormap to focus on a subset
amount_colors = 256

# Generate original and modified colormaps
original_cmap = register_colormap(cmap_name)
modified_cmap = shift_colormap(cmap_name, start, end, amount_colors)

# Generate sample data for visualization
data = np.linspace(0, 1, 100).reshape(10, 10)

# Plot original and shifted colormaps
fig, axes = plt.subplots(1, 2, figsize=(10, 4))

# Original colormap
cbar_original = axes[0].imshow(data, cmap=original_cmap)
axes[0].set_title(f"Original {cmap_name} Colormap")
fig.colorbar(cbar_original, ax=axes[0])

# Shifted colormap
cbar_modified = axes[1].imshow(data, cmap=modified_cmap)
axes[1].set_title(f"Shifted {cmap_name} Colormap ({start} to {end})")
fig.colorbar(cbar_modified, ax=axes[1])

plt.show()
```

![shift_colormap](data/postprocessing/zzz_pictures/shift_colormap_example.png)

**important: This function is not used in main due to other color demands!**

**darken_colormap**:
Sometimes it can make sense to show references between different plots or you just want to make colors from a suiting colormap brighter oder darker. In this case it can be an idea to use same colormaps but change the brightness of these colors. In this case this function is designed to darken a given colormap. See the example below: 

```
def register_colormap(cmap_name: str):
    """load colormap from plt and register in plt if colormap from cc.

    Args:
        cmap_name (str): colormap name as string registered in plt or cc.

    Returns:
       LinearSegmentedColormap : loaded colormap from plt.
    """
    if cmap_name not in plt.colormaps():
        colormap = cc.cm[cmap_name]  # load colormap from colorcet
        plt.register_cmap(name=cmap_name, cmap=ListedColormap(colormap(np.linspace(0, 1, 256))))  # only if not available register colormap
    else:
        colormap = plt.get_cmap(cmap_name) # if already registered in matplotlib load map from there.
    return colormap

def darken_colormap(cmap_name: str, factor: float, spectrum_left=0.0, spectrum_right=1.0, amount_colors=256):
    """
    Darkens the color map by scaling the RGB values.
    """
    colormap = register_colormap(cmap_name)
    colors = colormap(np.linspace(spectrum_left, spectrum_right, amount_colors))  # Create a list of colors
    darkened_colors = colors.copy()  # Create a copy of the colors
    darkened_colors[:, :3] *= factor  # Only scale RGB values, alpha remains the same
    return LinearSegmentedColormap.from_list(f"{cmap_name}_darkened", darkened_colors)

# Define input data
cmap_name = "viridis"
factor = 0.5  # Darken by 50%
spectrum_left, spectrum_right = 0.0, 1.0
amount_colors = 256

# Generate original and modified colormaps
original_cmap = register_colormap(cmap_name)
darkened_cmap = darken_colormap(cmap_name, factor, spectrum_left, spectrum_right, amount_colors)

# Generate sample data for visualization
data = np.linspace(0, 1, 100).reshape(10, 10)

# Plot original and darkened colormaps
fig, axes = plt.subplots(1, 2, figsize=(10, 4))

# Original colormap
cbar_original = axes[0].imshow(data, cmap=original_cmap)
axes[0].set_title(f"Original {cmap_name} Colormap")
fig.colorbar(cbar_original, ax=axes[0])

# Darkened colormap
cbar_darkened = axes[1].imshow(data, cmap=darkened_cmap)
axes[1].set_title(f"Darkened {cmap_name} Colormap (Factor: {factor})")
fig.colorbar(cbar_darkened, ax=axes[1])

plt.show()
```

![darken_colormap](data/postprocessing/zzz_pictures/darken_colormap_example.png)

**important: This function is not used in main due to other color demands!**

**get_color_for_key**:
Sometimes it's senseful to link a color to a key (in this case asset). Colors are saved in assigend_colors_dict and can be saved in a json file to garantuee a color assignment over several executings of the script (function: save_colors_for_key_json). In this function a colormap and belonging parameters are given and as well as an asset name as a string. We want to give this asset a color and skip with the next asset to the next color and assign it. Look at the example below:  

````
def get_color_for_key(
    asset_name: str, 
    cmap_name:str, 
    assigned_colors:dict,
    spectrum_left = 0.0,
    spectrum_right = 1.0,
    amount_colors = 256
    ):
    """Assign colors for assets and save in dictionary with assigned_colors.

    Args:
        asset_name (str): String of asset name.
        cmap_name (str): colormap from which assets get colors assigned to
        assigned_colors (dict): existing color dictionary (can also be empty at the beginning)
        spectrum_left(float): starting point of colormap (0.0 = left, 1.0 = right). Defaults to 0.
        spectrum_right (float): end point of colormap (0.0 = left, 1.0 = right). Defaults to 1.
        amount_colors (int): Amounts of colors extracted from map. Defaults to 256.

    Returns:
        tuple: color tuple for one asset with color values in rgba data (values between 0 and 1).
    """
    colormap = register_colormap(cmap_name=cmap_name)
    colors = colormap(np.linspace(spectrum_left, spectrum_right, amount_colors))
    asset_name_split = asset_name.split(".")[0]
    if asset_name_split not in assigned_colors:
        # If key does not have a color, give it the next one: 
        next_color = len(assigned_colors) % len(colors)  # cyclic iterating through colormap
        assigned_colors[asset_name_split] = colors[next_color]
        print(f"neue farbe für: {asset_name_split}:", colors[next_color])
    return tuple(assigned_colors[asset_name_split])


# Define test data
cmap_name = "tab10"
assets = ["solar_panel", "wind_turbine", "battery_storage", "hydro_power", "geothermal"]
assigned_colors = {}

# Assign colors by calling the function multiple times with unique indices
for i, asset in enumerate(assets):
    get_color_for_key(asset, cmap_name, assigned_colors, spectrum_left=i/len(assets), spectrum_right=(i+1)/len(assets))

# Plot assigned colors
fig, ax = plt.subplots(figsize=(6, 3))
for i, (asset, color) in enumerate(assigned_colors.items()):
    ax.barh(i, 1, color=color)
ax.set_title("Assigned Colors for Assets")
ax.set_xticks([])
ax.set_yticks(range(len(assigned_colors)))
ax.set_yticklabels(assigned_colors.keys())
plt.show()
````
![get_color_for_key](data/postprocessing/zzz_pictures/get_color_for_key_example.png)

**load_color_data_from_json**:

**save_colors_for_key_json**
**show_color_rgba**



### 0.3 Load data from csv output


### 1 Functions for filtering and calculating values for set time granularity
### 2 Functions for setting assets and parameters to be visualized
### 3 Functions for plotting and saving bar chart for share of assets
### 4 Main Script


written by: Sophia Reker