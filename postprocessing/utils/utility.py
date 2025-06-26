import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from matplotlib.dates import HourLocator, DateFormatter
import plotly.graph_objects as go
import plotly.io as pio
import json

# Set plotly theme to match matplotlib dark background
pio.templates.default = "plotly_dark"

def load_color_dict(json_path):
    """Loads the color dictionary from a JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        color_dict = json.load(f)
    return {k: tuple(v) for k, v in color_dict.items()}

def ensure_datetime_index(df):
    """Ensures that the DataFrame has a DatetimeIndex."""
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    return df

def filter_daily_data(df, date_str):
    """Filters DataFrame for a specific day."""
    start_datetime = pd.Timestamp(date_str)
    end_datetime = start_datetime + pd.Timedelta(days=1)
    return df.loc[start_datetime:end_datetime - pd.Timedelta(hours=1)].copy()

def extract_year_from_scenario(scenario_name):
    """Extract year from scenario name."""
    if '_2040' in scenario_name:
        return 2040
    elif '_2050' in scenario_name:
        return 2050
    elif '_2030' in scenario_name:
        return 2030
    else:
        return 2030  # Default fallback

def filter_scenarios_by_year(scenario_data, year):
    """Filter scenarios by year."""
    filtered = {}
    for scenario_name, data in scenario_data.items():
        scenario_year = extract_year_from_scenario(scenario_name)
        if scenario_year == year:
            filtered[scenario_name] = data
    return filtered

class HeatProducerAnalyzer:
    """Consolidated class for heat producer analyses."""
    
    def __init__(self, color_dict):
        self.color_dict = color_dict
        
    def analyze_brutto_heat_production(self, df_hourly_data, analysis_type="local_heating"):
        """
        Analyzes gross heat production.
        
        Args:
            df_hourly_data: DataFrame with hourly data
            analysis_type: "local_heating" or "district_heating"
        """
        metrics_df = pd.DataFrame(index=df_hourly_data.index)
        
        if analysis_type == "local_heating":
            potential_cols = {
                'CHP 1 Waste Heat': 'chp_1.waste_heat',
                'CHP 2 Waste Heat': 'chp_2.waste_heat',
                'Solar Thermal': 'solar_thermal.heat',
                'Geothermal': 'geo_heat_storage.heat_discharging',
                'Heat Pump Stage 1': 'heatpump_s1.heat',
                'Heat Pump Stage 2': 'heatpump_s2.heat'
            }
            color_keys = [
                "chp_1.waste_heat", "chp_2.waste_heat", "solar_thermal",
                "geo_heat_storage.heat_charging", "heatpump_s1", "heatpump_s2"
            ]
        elif analysis_type == "district_heating":
            potential_cols = {
                'CHP 1 Heat': 'chp_1.heat',
                'CHP 2 Heat': 'chp_2.heat',
                'CHP 1 Waste Heat': 'chp_1.waste_heat',
                'CHP 2 Waste Heat': 'chp_2.waste_heat'
            }
            color_keys = ["chp_1", "chp_2", "chp_1.waste_heat", "chp_2.waste_heat"]
        
        # Extract data
        for display_name, col_name in potential_cols.items():
            if col_name in df_hourly_data.columns:
                metrics_df[display_name] = df_hourly_data[col_name]
            else:
                print(f"Warning: Column '{col_name}' not found.")
                metrics_df[display_name] = 0
        
        # Assign colors
        colors = [self.color_dict.get(key, (0.5, 0.5, 0.5, 1.0)) 
                 for key in color_keys[:len(metrics_df.columns)]]
        metrics_df.attrs['colors'] = colors
        
        return metrics_df
    
    def plot_stacked_bars_with_power_price(self, daily_data, df_brutto, scenario_name, 
                                         selected_date, title_prefix="Heat Production"):
        """Creates stacked bar charts with power price."""
        fig, ax = plt.subplots(figsize=(11, 6), dpi=300)
        
        x = np.arange(len(df_brutto.index))
        width = 1.0
        colors = df_brutto.attrs.get('colors', plt.cm.tab10.colors)
        
        # Stacked bars
        bottom = np.zeros(len(df_brutto))
        for i, (col, color) in enumerate(zip(df_brutto.columns, colors)):
            values = df_brutto[col].values
            ax.bar(x, values, width=width, bottom=bottom, label=col, 
                  color=color, align='edge', edgecolor='none')
            bottom += values
        
        # X-axis formatting
        ax.set_xticks(x)
        ax.set_xticklabels([ts.strftime("%H:%M") for ts in df_brutto.index], 
                          rotation=45, ha='right', fontsize=10)
        ax.set_xlabel(f'Time on {selected_date.strftime("%d.%m.%Y")}', fontsize=12)
        
        # Y-axis formatting
        y_max = bottom.max()
        ax.set_ylim(0, y_max * 1.15 if y_max > 0 else 1)
        ax.set_ylabel('Heat Production (MWh)', fontsize=12)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=10))
        
        # Power price on second y-axis
        ax2 = ax.twinx()
        if 'power_price' in daily_data.columns:
            power_price_max = daily_data['power_price'].max()
            # Step plot
            if len(x) > 1:
                x_last = x[-1] + (x[-1] - x[-2])
            else:
                x_last = x[-1] + 1
            x_step = np.append(x, x_last)
            y_step = np.append(daily_data['power_price'].values, 
                             daily_data['power_price'].values[-1])
            
            color_power_price = self.color_dict.get('power_price', (1.0, 0.0, 0.0, 1.0))
            ax2.step(x_step, y_step, where='post', color=color_power_price, 
                    linestyle='--', linewidth=2, label='Power Price')
            ax2.set_ylim(0, power_price_max * 1.15 if power_price_max > 0 else 1)
            ax2.set_ylabel('Power Price (€/MWh)', fontsize=12)
            ax2.legend(loc='upper left', fontsize=10)
        
        # Grid and legend
        ax.grid(which="major", axis='y', linestyle='--', color='gray', alpha=0.5)
        ax.grid(which="major", axis='x', linestyle='--', color='gray', alpha=0.3)
        
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles, labels, loc='lower center', 
                 bbox_to_anchor=(0.5, 1.0, 0, 0),
                 ncol=max(1, int(np.ceil(len(df_brutto.columns)/2))), 
                 frameon=True)
        
        plt.tight_layout()
        plt.show()

    def plot_combined_heat_production_comparison(self, scenarios_data, selected_date):
        """Creates a 2x2 subplot comparison of heat production for all scenarios."""
        selected_timestamp = pd.Timestamp(selected_date)
        
        # Prepare data for all scenarios
        scenario_plot_data = {}
        for scenario_name, data in scenarios_data.items():
            daily_data = filter_daily_data(data['output'], selected_date)
            if not daily_data.empty:
                # Local heating analysis
                df_local = self.analyze_brutto_heat_production(
                    daily_data, analysis_type="local_heating"
                )
                # District heating analysis
                df_district = self.analyze_brutto_heat_production(
                    daily_data, analysis_type="district_heating"
                )
                scenario_plot_data[scenario_name] = {
                    'daily_data': daily_data,
                    'local': df_local,
                    'district': df_district
                }
        
        if len(scenario_plot_data) < 2:
            print("Not enough scenario data available for comparison.")
            return
        
        # Calculate max values for consistent scaling
        district_max = 0
        local_max = 0
        power_price_max = 0
        
        for scenario_name, data in scenario_plot_data.items():
            # District heating max
            district_total = data['district'].sum(axis=1)
            if len(district_total) > 0:
                district_max = max(district_max, district_total.max())
            
            # Local heating max
            local_total = data['local'].sum(axis=1)
            if len(local_total) > 0:
                local_max = max(local_max, local_total.max())
            
            # Power price max
            if 'power_price' in data['daily_data'].columns:
                power_price_max = max(power_price_max, data['daily_data']['power_price'].max())
        
        # Create 2x2 subplot figure
        fig, axes = plt.subplots(2, 2, figsize=(20, 12), dpi=300)
        
        # Get scenario names (assuming we have 0% and 100% H2)
        scenario_names = list(scenario_plot_data.keys())
        
        # Define subplot positions and titles
        subplot_configs = [
            (0, 0, scenario_names[0], 'district', 'District Heat Production'),
            (0, 1, scenario_names[1], 'district', 'District Heat Production'),
            (1, 0, scenario_names[0], 'local', 'Local Heat Production'),
            (1, 1, scenario_names[1], 'local', 'Local Heat Production')
        ]
        
        # Collect all unique legend elements from both heating types (excluding Power Price)
        all_handles = []
        all_labels = []
        legend_collected = set()  # To avoid duplicates
        power_price_handle = None  # Store Power Price handle separately
        
        for idx, (row, col, scenario_name, heat_type, title_prefix) in enumerate(subplot_configs):
            ax = axes[row, col]
            
            # Get data for this subplot
            daily_data = scenario_plot_data[scenario_name]['daily_data']
            df_brutto = scenario_plot_data[scenario_name][heat_type]
            
            # Create stacked bar plot
            x = np.arange(len(df_brutto.index))
            width = 1.0
            colors = df_brutto.attrs.get('colors', plt.cm.tab10.colors)
            
            # Stacked bars
            bottom = np.zeros(len(df_brutto))
            for i, (col_name, color) in enumerate(zip(df_brutto.columns, colors)):
                values = df_brutto[col_name].values
                bar = ax.bar(x, values, width=width, bottom=bottom, label=col_name, 
                            color=color, align='edge', edgecolor='none')
                
                # Collect legend elements from first district (idx=0) and first local (idx=2)
                if (idx == 0 or idx == 2) and col_name not in legend_collected:
                    all_handles.append(bar)
                    all_labels.append(col_name)
                    legend_collected.add(col_name)
                
                bottom += values
            
            # X-axis formatting
            ax.set_xticks(x[::2])  # Show every 2nd tick for all plots
            
            if row == 1:  # Bottom row - with labels
                ax.set_xticklabels([ts.strftime("%H:%M") for ts in df_brutto.index[::2]], 
                                rotation=45, ha='right', fontsize=16)
                # ax.set_xlabel(f'Time on {selected_timestamp.strftime("%d.%m.%Y")}', fontsize=12)
            else:  # Top row - ticks but no labels
                ax.set_xticklabels([])  # Remove x-tick labels for top row
                ax.tick_params(axis='x', labelsize=16, which='major', bottom=True, top=False, labelbottom=False)
            
            # Y-axis formatting with consistent scaling
            if heat_type == 'district':
                y_max_scaled = district_max * 1.15 if district_max > 0 else 1
            else:  # local
                y_max_scaled = local_max * 1.15 if local_max > 0 else 1
            
            ax.set_ylim(0, y_max_scaled)
            ax.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))
            
            ax.tick_params(axis='y', labelsize=16)

            # Y-axis label only for left column
            if col == 0:  # Left column
                ax.set_ylabel('Heat Production (MWh)', fontsize=16)
            
            # Title only for top row with H2 percentage
            if row == 0:  # Only top plots get titles
                if col == 0:  # Left column
                    ax.set_title(r'$\mathbf{0\ Vol.\%\ H_2}$', fontsize=20, pad=15)
                else:  # Right column
                    ax.set_title(r'$\mathbf{100\ Vol.\%\ H_2}$', fontsize=20, pad=15)
        
            
            # Power price on secondary y-axis
            ax2 = ax.twinx()
            if 'power_price' in daily_data.columns:
                # Step plot for power price
                if len(x) > 1:
                    x_last = x[-1] + (x[-1] - x[-2])
                else:
                    x_last = x[-1] + 1
                x_step = np.append(x, x_last)
                y_step = np.append(daily_data['power_price'].values, 
                                daily_data['power_price'].values[-1])
                
                color_power_price = self.color_dict.get('power_price', (1.0, 0.0, 0.0, 1.0))
                power_line = ax2.step(x_step, y_step, where='post', color=color_power_price, 
                                    linestyle='--', linewidth=1.5, label='Power Price', alpha=0.8)
                
                # Store power price handle from first subplot for separate legend
                if idx == 0 and power_price_handle is None:
                    power_price_handle = power_line[0]
                
                # Consistent power price scaling for all plots
                ax2.set_ylim(0, power_price_max * 1.15 if power_price_max > 0 else 1)
                
                # Power Price y-axis label only for right column
                if col == 1:  # Right column
                    ax2.set_ylabel('Power Price (€/MWh)', fontsize=16)
                
                # Y-ticks for all plots but label only for right column
                ax2.tick_params(axis='y', labelsize=16)
                if col == 0:  # Left column - remove y-tick labels
                    ax2.set_yticklabels([])
            
            # Grid
            ax.grid(which="major", axis='y', linestyle='--', color='gray', alpha=0.5)
            ax.grid(which="major", axis='x', linestyle='--', color='gray', alpha=0.3)
        
        # Create unified legend above the plots (without Power Price)
        fig.legend(all_handles, all_labels, 
                loc='outside upper center', 
                # bbox_to_anchor=(0.5, 0.02),  # Centered below the plots
                ncol=min(len(all_labels), 4),  # Increased to 8 columns for more items
                frameon=True, 
                fontsize=16,  # Slightly smaller font to fit more items
                # fancybox=True,
                shadow=True)
        
        # Add separate Power Price legend to upper left subplot
        if power_price_handle is not None:
            axes[0, 0].legend([power_price_handle], ['Power Price'], 
                            loc='upper left', 
                            #bbox_to_anchor=(0.98, 0.98),
                            frameon=True, 
                            fontsize=16,
                            fancybox=True,
                            shadow=True)
        
        # Adjust layout to accommodate legend
        plt.tight_layout()
        plt.subplots_adjust(top=0.87)  # More room for larger legend
        plt.show()
        
        # Print summary for each scenario
        print(f"\n=== HEAT PRODUCTION SUMMARY FOR {selected_date} ===")
        for scenario_name, data in scenario_plot_data.items():
            print(f"\n--- {scenario_name.upper()} ---")
            
            # Local heating totals
            local_total = data['local'].sum(axis=1).sum()
            print(f"Total Local Heat Production:    {local_total:>8.1f} MWh")
            
            # District heating totals
            district_total = data['district'].sum(axis=1).sum()
            print(f"Total District Heat Production: {district_total:>8.1f} MWh")
            
            # Combined total
            combined_total = local_total + district_total
            print(f"Combined Total:                 {combined_total:>8.1f} MWh")
        
        print("-" * 55)

class CriticalSparkSpreadCalculator:
    """Consolidated CSS calculation."""
    
    def __init__(self):
        # Energy densities [MJ/m³]
        self.HV_H2 = 120.0
        self.HV_NG = 47.0
        self.RHO_H2 = 0.09
        self.RHO_NG = 0.68
        self.energy_density_h2 = self.RHO_H2 * self.HV_H2
        self.energy_density_ng = self.RHO_NG * self.HV_NG
    
    def calculate_energy_fractions(self, h2_admixture_fraction):
        """Calculates energy fractions for H2 and natural gas."""
        vol_h2 = h2_admixture_fraction
        vol_ng = 1 - vol_h2
        
        denominator = (vol_h2 * self.energy_density_h2 + vol_ng * self.energy_density_ng)
        if denominator == 0:
            raise ValueError("Total energy density is zero.")
        
        energy_fraction_h2 = (vol_h2 * self.energy_density_h2) / denominator
        energy_fraction_ng = (vol_ng * self.energy_density_ng) / denominator
        
        return energy_fraction_h2, energy_fraction_ng, vol_ng
    
    def calculate_css(self, scenario):
        """Calculates Critical Spark Spread for a scenario."""
        output_data = scenario.load_output_data()
        metadata = scenario.load_metadata()
        chp_asset_data = scenario.load_chp_asset_data()
        
        if chp_asset_data is None:
            raise ValueError(f"CHP asset data not available for {scenario.scenario_name_identifier}")
        
        # Extract parameters
        co2_price = metadata['CO2_PRICE']
        h2_admixture_fraction = metadata['hydrogen_admixture']['chp_1']
        
        # Asset parameters
        max_power = chp_asset_data.loc['max', 'power']
        min_power = chp_asset_data.loc['min', 'power']
        max_gas = chp_asset_data.loc['max', 'gas']
        min_gas = chp_asset_data.loc['min', 'gas']
        max_co2 = chp_asset_data.loc['max', 'co2']
        min_co2 = chp_asset_data.loc['min', 'co2']
        
        # Calculate energy fractions
        energy_fraction_h2, energy_fraction_ng, vol_ng = self.calculate_energy_fractions(h2_admixture_fraction)
        
        # CSS calculation
        results_df = pd.DataFrame(index=output_data.index)
        results_df['power_price'] = output_data['power_price']
        results_df['gas_price'] = output_data['gas_price']
        results_df['hydrogen_price'] = output_data['hydrogen_price']
        
        # Fuel costs
        results_df['max_fuel_costs'] = (max_gas * energy_fraction_ng * results_df['gas_price'] + 
                                       max_gas * energy_fraction_h2 * results_df['hydrogen_price'])
        results_df['min_fuel_costs'] = (min_gas * energy_fraction_ng * results_df['gas_price'] + 
                                       min_gas * energy_fraction_h2 * results_df['hydrogen_price'])
        
        # CO2 costs
        max_co2_costs = max_co2 * vol_ng * co2_price
        min_co2_costs = min_co2 * vol_ng * co2_price
        
        results_df['max_total_costs'] = results_df['max_fuel_costs'] + max_co2_costs
        results_df['min_total_costs'] = results_df['min_fuel_costs'] + min_co2_costs
        
        additional_power = max_power - min_power
        if additional_power == 0:
            results_df['critical_spark_spread_EUR_per_MWh'] = pd.NA
        else:
            results_df['critical_spark_spread_EUR_per_MWh'] = (
                (results_df['max_total_costs'] - results_df['min_total_costs']) / additional_power
            )
        
        return results_df

class WasteHeatAnalyzer:
    """Consolidated waste heat analysis (formerly DistrictHeatingAnalyzer)."""
    
    def __init__(self, color_dict):
        self.color_dict = color_dict
    
    def calculate_waste_heat_metrics(self, output_data, scenario_name):
        """Calculates waste heat network metrics."""
        metrics = {
            'Heat Feedin (MWh)': output_data['waste_heat_grid.heat_feedin'].sum(),
            'Heat Supply (MWh)': output_data['waste_heat_grid.heat_supply'].sum(),
            'Heat Dissipation (MWh)': output_data['waste_heat_grid.heat_dissipation'].sum()
        }
        
        # Calculate utilization rate
        if metrics['Heat Feedin (MWh)'] > 0:
            metrics['Utilization Rate (%)'] = (metrics['Heat Supply (MWh)'] / 
                                             metrics['Heat Feedin (MWh)']) * 100
        else:
            metrics['Utilization Rate (%)'] = 0
            
        return pd.Series(metrics, name=scenario_name)
    
    def plot_monthly_dissipation(self, scenarios_data):
        """Creates plot for monthly waste heat dissipation."""
        fig, ax = plt.subplots(figsize=(16, 9))
        
        colors = [self.color_dict.get('0 % H₂', (0.0, 1.0, 1.0, 1.0)), 
                 self.color_dict.get('100 % H₂', (1.0, 0.0, 1.0, 1.0))]
        markers = ['o', 'x']
        linestyles = ['-', '--']
        
        for i, (scenario_name, data) in enumerate(scenarios_data.items()):
            monthly_sum = data['output']['waste_heat_grid.heat_dissipation'].resample('ME').sum()
            
            ax.plot(monthly_sum.index, monthly_sum, 
                   label=f'Monthly Dissipation {scenario_name}',
                   color=colors[i % len(colors)], 
                   marker=markers[i % len(markers)],
                   linestyle=linestyles[i % len(linestyles)])
        
        ax.set_title('Monthly Waste Heat Dissipation Comparison (UC1 2030)', fontsize=16)
        ax.set_xlabel('Month', fontsize=14)
        ax.set_ylabel('Heat Amount (MWh)', fontsize=14)
        ax.legend(fontsize=12)
        ax.tick_params(axis='both', which='major', labelsize=12)
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()
        plt.show()
    
    def plot_waste_heat_sankey(self, output_data, scenario_name):
        """Creates Sankey diagram for waste heat flow analysis."""
        # Calculate total values
        total_feedin = output_data['waste_heat_grid.heat_feedin'].sum()
        total_supply = output_data['waste_heat_grid.heat_supply'].sum()
        total_dissipation = output_data['waste_heat_grid.heat_dissipation'].sum()
        
        # Convert color tuples to RGB strings for plotly
        def color_to_rgb(color_tuple, alpha=0.8):
            if len(color_tuple) >= 3:
                r, g, b = int(color_tuple[0] * 255), int(color_tuple[1] * 255), int(color_tuple[2] * 255)
                return f'rgba({r},{g},{b},{alpha})'
            return f'rgba(128,128,128,{alpha})'
        
        # Get colors from color dictionary
        feedin_color = self.color_dict.get('waste_heat_grid.heat_feedin', (0.2, 0.6, 1.0, 1.0))
        supply_color = self.color_dict.get('waste_heat_grid.heat_supply', (0.0, 0.8, 0.0, 1.0))
        dissipation_color = self.color_dict.get('waste_heat_grid.heat_dissipation', (1.0, 0.3, 0.3, 1.0))
        
        # Calculate efficiency
        efficiency = (total_supply / total_feedin * 100) if total_feedin > 0 else 0
        
        # Node definitions with values directly in labels
        node_labels = [
            f"Waste Heat Available<br><b>{total_feedin:.0f} MWh</b>",
            f"Heat Utilized<br><b>{total_supply:.0f} MWh</b><br>({total_supply/total_feedin*100:.1f}%)",
            f"Heat Dissipated<br><b>{total_dissipation:.0f} MWh</b><br>({total_dissipation/total_feedin*100:.1f}%)"
        ]
        
        node_colors = [
            color_to_rgb(feedin_color, 0.8),
            color_to_rgb(supply_color, 0.8),
            color_to_rgb(dissipation_color, 0.8)
        ]
        
        # Link definitions: source -> target with value
        link_source = [0, 0]        # From "Waste Heat Available" to both outputs
        link_target = [1, 2]        # To "Heat Utilized" and "Heat Dissipated"
        link_value = [total_supply, total_dissipation]
        
        # Link colors (slightly transparent)
        link_colors = [
            color_to_rgb(supply_color, 0.6),
            color_to_rgb(dissipation_color, 0.6)
        ]
        
        # Create Sankey diagram with improved node positioning
        fig = go.Figure(data=[go.Sankey(
            arrangement="snap",
            node=dict(
                pad=25,
                thickness=30,
                line=dict(color="black", width=2),
                label=node_labels,
                color=node_colors,
                x=[0.1, 0.9, 0.9],   # Position nodes: left, right-top, right-bottom
                y=[0.5, 0.75, 0.25], # Better vertical spacing
            ),
            link=dict(
                source=link_source,
                target=link_target,
                value=link_value,
                color=link_colors,
                line=dict(color="rgba(255,255,255,0.2)", width=1)
            )
        )])
        
        # Update layout with higher resolution and better sizing
        fig.update_layout(
            title={
                'text': f"Waste Heat Flow Analysis - {scenario_name}<br><sub>Utilization Efficiency: {efficiency:.1f}%</sub>",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 20, 'color': 'black'}
            },
            font=dict(size=16, color='black'),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            width=1200,  # Increased width for better text spacing
            height=700,  # Increased height
            margin=dict(l=100, r=100, t=120, b=100)  # Larger margins for better spacing
        )
        
        # Show the plot with high DPI
        fig.show(config={
            'toImageButtonOptions': {
                'format': 'png',
                'filename': f'waste_heat_sankey_{scenario_name}',
                'height': 700,
                'width': 1200,
                'scale': 5  # This gives approximately 600 DPI (120 * 5)
            },
            'displayModeBar': True,
            'modeBarButtonsToAdd': ['downloadImage']
        })
        
        # Print summary statistics
        print(f"\n--- Waste Heat Flow Summary for {scenario_name} ---")
        print(f"Total Heat Available:  {total_feedin:>8.0f} MWh")
        print(f"Heat Utilized:         {total_supply:>8.0f} MWh ({total_supply/total_feedin*100:>5.1f}%)")
        print(f"Heat Dissipated:       {total_dissipation:>8.0f} MWh ({total_dissipation/total_feedin*100:>5.1f}%)")
        print(f"Utilization Efficiency: {efficiency:>6.1f}%")
        print("-" * 55)

class GeothermalAnalyzer:
    """Geothermal and local heat producer analysis."""
    
    def calculate_geothermal_metrics(self, output_data, scenario_name, start_date=None, end_date=None):
        """Calculates geothermal metrics."""
        if start_date and end_date:
            df_filtered = output_data[start_date:end_date]
        else:
            df_filtered = output_data
        
        metrics = {
            'Geothermal Charged (MWh)': df_filtered['geo_heat_storage.heat_charging'].sum(),
            'Geothermal Discharged (MWh)': df_filtered['geo_heat_storage.heat_discharging'].sum(),
            'Storage Z1 FW (MWh)': df_filtered['stratified_storage.Q_dot_Z1_FW'].sum(),
            'Storage Z1 NW (MWh)': df_filtered['stratified_storage.Q_dot_Z1_NW'].sum(),
            'Storage Z2 NW (MWh)': df_filtered['stratified_storage.Q_dot_Z2_NW'].sum(),
            'Heat Pump Input (MWh)': df_filtered['stratified_storage.Q_dot_WP'].sum()
        }
        
        # Calculated metrics
        metrics['Net Geothermal Change (MWh)'] = (metrics['Geothermal Discharged (MWh)'] - 
                                                 metrics['Geothermal Charged (MWh)'])
        metrics['Total Storage Output (MWh)'] = (metrics['Storage Z1 FW (MWh)'] + 
                                               metrics['Storage Z1 NW (MWh)'] + 
                                               metrics['Storage Z2 NW (MWh)'])
        
        return pd.Series(metrics, name=scenario_name)

class CHPAnalyzer:
    """CHP performance analysis."""
    
    def calculate_chp_metrics(self, output_data, scenario_name):
        """Calculates CHP metrics."""
        metrics = {
            'CHP1 Heat (MWh)': output_data['chp_1.heat'].sum(),
            'CHP2 Heat (MWh)': output_data['chp_2.heat'].sum(),
            'CHP1 Operating Hours (h)': output_data['chp_1.bin'].sum(),
            'CHP2 Operating Hours (h)': output_data['chp_2.bin'].sum()
        }
        
        # Calculate starts
        chp_1_bin = output_data['chp_1.bin']
        chp_2_bin = output_data['chp_2.bin']
        metrics['CHP1 Starts'] = (chp_1_bin.diff() == 1).sum()
        metrics['CHP2 Starts'] = (chp_2_bin.diff() == 1).sum()
        
        # Total values
        metrics['Total Heat (MWh)'] = metrics['CHP1 Heat (MWh)'] + metrics['CHP2 Heat (MWh)']
        
        return pd.Series(metrics, name=scenario_name)

class StorageAnalyzer:
    """Storage analysis."""
    
    def __init__(self, color_dict):
        self.color_dict = color_dict
    
    def plot_storage_analysis(self, output_data, start_date, end_date, title_suffix=""):
        """Creates storage analysis plot."""
        df = output_data[[
            'heat_storage.heat_balance', 'heat_storage.heat_charging', 
            'heat_storage.heat_discharging', 'heat_storage.heat_content',
            'heat_storage.bin_charge', 'heat_storage.bin_discharge', 'power_price'
        ]].copy()
        
        df_period = df.loc[start_date:end_date].copy()
        df_period['heat_storage.heat_discharging_neg'] = -df_period['heat_storage.heat_discharging']
        
        fig, axes = plt.subplots(nrows=3, ncols=1, dpi=120, figsize=(17, 7.5), sharex=True)
        
        # 1. Storage content
        color_content = self.color_dict.get('heat_storage.heat_content', (0.0, 0.0, 1.0, 1.0))
        axes[0].plot(df_period.index, df_period['heat_storage.heat_content'], 
                    color=color_content, label='Storage Content')
        axes[0].set_ylabel('Storage Content (MWh)')
        axes[0].set_title(f'Heat Storage Analysis{title_suffix}')
        axes[0].legend(loc='upper right')
        axes[0].grid(True, linestyle='--', alpha=0.5)
        
        # 2. Charging/Discharging with power price
        ax2 = axes[1].twinx()
        color_charging = self.color_dict.get('heat_storage.heat_charging', (0.0, 1.0, 0.0, 1.0))
        color_discharging = self.color_dict.get('heat_storage.heat_discharging', (1.0, 0.0, 0.0, 1.0))
        
        axes[1].plot(df_period.index, df_period['heat_storage.heat_charging'], 
                    color=color_charging, label='Charging (+)')
        axes[1].plot(df_period.index, df_period['heat_storage.heat_discharging_neg'], 
                    color=color_discharging, label='Discharging (-)')
        axes[1].set_ylabel('Power (MW)')
        axes[1].legend(loc='upper left')
        axes[1].grid(True, linestyle='--', alpha=0.5)
        
        color_power_price = self.color_dict.get('power_price', (1.0, 0.5, 0.0, 1.0))
        ax2.plot(df_period.index, df_period['power_price'], 
                color=color_power_price, label='Power Price', 
                linewidth=1.5, linestyle='--')
        ax2.set_ylabel('Power Price (€/MWh)', color='black', fontsize=14)
        ax2.tick_params(axis='y', labelcolor='black', labelsize=14)
        
        # Combined legend
        lines1, labels1 = axes[1].get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        axes[1].legend(lines1 + lines2, labels1 + labels2, loc='upper right')
        
        # 3. Hide third subplot
        axes[2].set_visible(False)
        
        plt.tight_layout()
        plt.show()

class LocalNetworkAnalyzer:
    """Local network balance analysis (formerly DistrictNetworkAnalyzer)."""
    
    def __init__(self, color_dict):
        self.color_dict = color_dict
    
    def plot_local_network_balance(self, output_data, start_date, end_date):
        """Creates local network balance plot."""
        df_period = output_data.loc[start_date:end_date].copy()
        
        # Input/Output calculations for local network
        df_period['Q_dot_ST_in'] = df_period['stratified_storage.Q_dot_ST'].clip(lower=0)
        df_period['Q_dot_WP_in'] = df_period['stratified_storage.Q_dot_WP'].clip(lower=0)
        df_period['Q_dot_Z1_FW_out'] = -df_period['stratified_storage.Q_dot_Z1_FW'].clip(lower=0)
        df_period['Q_dot_Z1_NW_out'] = -df_period['stratified_storage.Q_dot_Z1_NW'].clip(lower=0)
        df_period['Q_dot_Z2_NW_out'] = -df_period['stratified_storage.Q_dot_Z2_NW'].clip(lower=0)
        
        if 'heat_grid.FW_to_NW' in df_period.columns:
            df_period['FW_to_NW_out'] = -df_period['heat_grid.FW_to_NW'].clip(lower=0)
        else:
            df_period['FW_to_NW_out'] = 0
        
        # Color configuration for local network
        input_colors = [
            self.color_dict.get('solar_thermal', (1.0, 0.84, 0.0, 1.0)),
            self.color_dict.get('heatpump_s1', (0.0, 0.75, 1.0, 1.0))
        ]
        output_colors = [
            self.color_dict.get('stratified_storage.Q_dot_Z1_FW', (0.8, 0.2, 0.2, 1.0)),
            self.color_dict.get('stratified_storage.Q_dot_Z1_NW', (1.0, 0.5, 0.0, 1.0)),
            self.color_dict.get('stratified_storage.Q_dot_Z2_NW', (0.5, 0.0, 0.5, 1.0)),
            self.color_dict.get('heat_grid.FW_to_NW', (0.0, 0.5, 1.0, 1.0))
        ]
        
        input_cols = ['Q_dot_ST_in', 'Q_dot_WP_in']
        input_labels = ['Solar Thermal (input)', 'Heat Pump (input)']
        output_cols = ['Q_dot_Z1_FW_out', 'Q_dot_Z1_NW_out', 'Q_dot_Z2_NW_out', 'FW_to_NW_out']
        output_labels = ['Z1 FW (output)', 'Z1 Local (output)', 'Z2 Local (output)', 'FW → Local']
        
        x = df_period.index
        if len(x) > 1:
            bar_width = (x[1] - x[0]).total_seconds() / (60*60*24)
        else:
            bar_width = 1
        
        fig, axes = plt.subplots(nrows=2, ncols=1, dpi=120, figsize=(17, 9), 
                                sharex=True, gridspec_kw={'height_ratios': [2, 1]})
        
        # Main plot
        ax = axes[0]
        
        # Inputs (positive, stacked)
        bottom = np.zeros(len(df_period))
        for i, col in enumerate(input_cols):
            y = df_period[col].values
            ax.bar(x, y, width=bar_width, bottom=bottom, color=input_colors[i], 
                  label=input_labels[i], align='edge', edgecolor='none')
            bottom += y
        
        # Outputs (negative, stacked)
        bottom = np.zeros(len(df_period))
        for i, col in enumerate(output_cols):
            y = df_period[col].values
            ax.bar(x, y, width=bar_width, bottom=bottom, color=output_colors[i], 
                  label=output_labels[i], align='edge', edgecolor='none')
            bottom += y
        
        ax.axhline(0, color='black', linewidth=1)
        ax.set_ylabel('Power (MW)', fontsize=14)
        # ax.set_title('Local Network Energy Balance', fontsize=16)
        
        # Power price on second y-axis
        ax1b = ax.twinx()
        if len(x) > 1:
            x_last = x[-1] + (x[-1] - x[-2])
        else:
            x_last = x[-1] + pd.Timedelta(hours=1)
        
        x_step = np.append(np.array(x, dtype='datetime64[ns]'), 
                          np.array([x_last], dtype='datetime64[ns]'))
        y_step = np.append(df_period['power_price'].values, 
                          df_period['power_price'].values[-1])
        
        color_power_price = self.color_dict.get('power_price', (1.0, 0.0, 0.0, 1.0))
        line_power_price, = ax1b.step(x_step, y_step, where='pre', 
                                     color=color_power_price, linestyle='--', 
                                     linewidth=2, label='Power Price')
        ax1b.set_ylabel('Power Price (€/MWh)', fontsize=14)
        
        # Legends
        ax.legend(loc='lower center', bbox_to_anchor=(0.5, 1.02, 0, 0), 
                 ncol=6, frameon=True, fontsize=14)
        ax1b.legend([line_power_price], ['Power Price'], loc='upper left', 
                   fontsize=10, frameon=True)
        
        ax.grid(True, linestyle='--', alpha=0.5)
        
        # Waste heat dissipation subplot
        if 'waste_heat_grid.heat_dissipation' in df_period.columns:
            if len(x) > 1:
                x_last = x[-1] + (x[-1] - x[-2])
            else:
                x_last = x[-1] + pd.Timedelta(hours=1)
            x_step2 = np.append(np.array(x, dtype='datetime64[ns]'), 
                               np.array([x_last], dtype='datetime64[ns]'))
            y_step2 = np.append(df_period['waste_heat_grid.heat_dissipation'].values, 
                               df_period['waste_heat_grid.heat_dissipation'].values[-1])
            
            color_dissipation = self.color_dict.get('waste_heat_grid.heat_dissipation', (1.0, 0.0, 1.0, 1.0))
            axes[1].step(x_step2, y_step2, where='pre', color=color_dissipation, 
                        label='Waste Heat Dissipation')
            axes[1].set_ylabel('Waste Heat Dissipation (MW)', fontsize=14)
            axes[1].set_xlabel('Time', fontsize=14)
            axes[1].legend(loc='upper left', fontsize=12)
            axes[1].grid(True, linestyle='--', alpha=0.5)
        else:
            axes[1].text(0.5, 0.5, 'Waste heat dissipation data not available', 
                        ha='center', va='center', fontsize=12)
            axes[1].axis('off')
        
        plt.tight_layout()
        plt.show()

def create_comparison_plot(comparison_df, title, ylabel, figsize=(16, 9)):
    """Creates standardized comparison plots."""
    fig, ax = plt.subplots(figsize=figsize)
    comparison_df.plot(kind='bar', ax=ax)
    ax.set_title(title, fontsize=16)
    ax.set_ylabel(ylabel, fontsize=14)
    ax.set_xlabel('Scenario', fontsize=14)
    ax.tick_params(axis='x', rotation=0, labelsize=12)
    ax.tick_params(axis='y', labelsize=12)
    ax.legend(title='Metric', fontsize=10)
    plt.grid(True, linestyle='--', alpha=0.7, axis='y')
    plt.tight_layout()
    plt.show()
    return fig, ax

def create_comparison_metrics(scenarios_data, metric_extractors):
    """Creates comparison metrics for multiple scenarios."""
    results = {}
    for scenario_name, data in scenarios_data.items():
        metrics = {}
        for metric_name, extractor_func in metric_extractors.items():
            metrics[metric_name] = extractor_func(data)
        results[scenario_name] = metrics
    
    return pd.DataFrame(results).T


class GeneralMetricsAnalyzer:
    """Analyzer for general metrics extraction from output data."""
    
    def __init__(self):
        # Define metrics to analyze - easy to extend with any operation
        self.metrics_config = {
            # Gas consumption metrics
            'CHP1 Gas Consumption (MWh)': lambda df: df['chp_1.gas'].sum() if 'chp_1.gas' in df.columns else 0.0,
            'CHP2 Gas Consumption (MWh)': lambda df: df['chp_2.gas'].sum() if 'chp_2.gas' in df.columns else 0.0,
            'Total Gas Consumption (MWh)': lambda df: (df['chp_1.gas'].sum() + df['chp_2.gas'].sum()) if all(col in df.columns for col in ['chp_1.gas', 'chp_2.gas']) else 0.0,
            'Average Gas Consumption (MW)': lambda df: (df['chp_1.gas'] + df['chp_2.gas']).mean() if all(col in df.columns for col in ['chp_1.gas', 'chp_2.gas']) else 0.0,
            'Max Gas Consumption (MW)': lambda df: (df['chp_1.gas'] + df['chp_2.gas']).max() if all(col in df.columns for col in ['chp_1.gas', 'chp_2.gas']) else 0.0,
            
            # Power metrics
            'CHP1 Power Production (MWh)': lambda df: df['chp_1.power'].sum() if 'chp_1.power' in df.columns else 0.0,
            'CHP2 Power Production (MWh)': lambda df: df['chp_2.power'].sum() if 'chp_2.power' in df.columns else 0.0,
            'Total Power Production (MWh)': lambda df: (df['chp_1.power'].sum() + df['chp_2.power'].sum()) if all(col in df.columns for col in ['chp_1.power', 'chp_2.power']) else 0.0,
            'Average Power Production (MW)': lambda df: (df['chp_1.power'] + df['chp_2.power']).mean() if all(col in df.columns for col in ['chp_1.power', 'chp_2.power']) else 0.0,
            'Max Power Production (MW)': lambda df: (df['chp_1.power'] + df['chp_2.power']).max() if all(col in df.columns for col in ['chp_1.power', 'chp_2.power']) else 0.0,
            
            # Heat metrics
            'CHP1 Heat Production (MWh)': lambda df: df['chp_1.heat'].sum() if 'chp_1.heat' in df.columns else 0.0,
            'CHP2 Heat Production (MWh)': lambda df: df['chp_2.heat'].sum() if 'chp_2.heat' in df.columns else 0.0,
            'Total CHP Heat Production (MWh)': lambda df: (df['chp_1.heat'].sum() + df['chp_2.heat'].sum()) if all(col in df.columns for col in ['chp_1.heat', 'chp_2.heat']) else 0.0,
            'Average CHP Heat Production (MW)': lambda df: (df['chp_1.heat'] + df['chp_2.heat']).mean() if all(col in df.columns for col in ['chp_1.heat', 'chp_2.heat']) else 0.0,
            
            # Waste heat metrics
            'CHP1 Waste Heat (MWh)': lambda df: df['chp_1.waste_heat'].sum() if 'chp_1.waste_heat' in df.columns else 0.0,
            'CHP2 Waste Heat (MWh)': lambda df: df['chp_2.waste_heat'].sum() if 'chp_2.waste_heat' in df.columns else 0.0,
            'Total Waste Heat (MWh)': lambda df: (df['chp_1.waste_heat'].sum() + df['chp_2.waste_heat'].sum()) if all(col in df.columns for col in ['chp_1.waste_heat', 'chp_2.waste_heat']) else 0.0,
            'Average Waste Heat (MW)': lambda df: (df['chp_1.waste_heat'] + df['chp_2.waste_heat']).mean() if all(col in df.columns for col in ['chp_1.waste_heat', 'chp_2.waste_heat']) else 0.0,
            
            # Storage metrics
            'Heat Storage Charging (MWh)': lambda df: df['heat_storage.heat_charging'].sum() if 'heat_storage.heat_charging' in df.columns else 0.0,
            'Heat Storage Discharging (MWh)': lambda df: df['heat_storage.heat_discharging'].sum() if 'heat_storage.heat_discharging' in df.columns else 0.0,
            'Max Heat Storage Charging (MW)': lambda df: df['heat_storage.heat_charging'].max() if 'heat_storage.heat_charging' in df.columns else 0.0,
            'Max Heat Storage Discharging (MW)': lambda df: df['heat_storage.heat_discharging'].max() if 'heat_storage.heat_discharging' in df.columns else 0.0,
            'Geothermal Charging (MWh)': lambda df: df['geo_heat_storage.heat_charging'].sum() if 'geo_heat_storage.heat_charging' in df.columns else 0.0,
            'Geothermal Discharging (MWh)': lambda df: df['geo_heat_storage.heat_discharging'].sum() if 'geo_heat_storage.heat_discharging' in df.columns else 0.0,
            
            # Renewable energy metrics
            'Solar Thermal Production (MWh)': lambda df: df['solar_thermal.heat'].sum() if 'solar_thermal.heat' in df.columns else 0.0,
            'Heat Pump S1 Production (MWh)': lambda df: df['heatpump_s1.heat'].sum() if 'heatpump_s1.heat' in df.columns else 0.0,
            'Heat Pump S2 Production (MWh)': lambda df: df['heatpump_s2.heat'].sum() if 'heatpump_s2.heat' in df.columns else 0.0,
            'Total Heat Pump Production (MWh)': lambda df: (df['heatpump_s1.heat'].sum() + df['heatpump_s2.heat'].sum()) if all(col in df.columns for col in ['heatpump_s1.heat', 'heatpump_s2.heat']) else 0.0,
            'Average Solar Thermal (MW)': lambda df: df['solar_thermal.heat'].mean() if 'solar_thermal.heat' in df.columns else 0.0,
            'Max Solar Thermal (MW)': lambda df: df['solar_thermal.heat'].max() if 'solar_thermal.heat' in df.columns else 0.0,
            
            # Grid metrics
            'Waste Heat Grid Feedin (MWh)': lambda df: df['waste_heat_grid.heat_feedin'].sum() if 'waste_heat_grid.heat_feedin' in df.columns else 0.0,
            'Waste Heat Grid Supply (MWh)': lambda df: df['waste_heat_grid.heat_supply'].sum() if 'waste_heat_grid.heat_supply' in df.columns else 0.0,
            'Waste Heat Grid Dissipation (MWh)': lambda df: df['waste_heat_grid.heat_dissipation'].sum() if 'waste_heat_grid.heat_dissipation' in df.columns else 0.0,
            'Average Grid Dissipation (MW)': lambda df: df['waste_heat_grid.heat_dissipation'].mean() if 'waste_heat_grid.heat_dissipation' in df.columns else 0.0,
            'Max Grid Dissipation (MW)': lambda df: df['waste_heat_grid.heat_dissipation'].max() if 'waste_heat_grid.heat_dissipation' in df.columns else 0.0,
            
            # Efficiency and ratio metrics
            'Waste Heat Utilization Rate (%)': lambda df: (df['waste_heat_grid.heat_supply'].sum() / df['waste_heat_grid.heat_feedin'].sum() * 100) if all(col in df.columns for col in ['waste_heat_grid.heat_supply', 'waste_heat_grid.heat_feedin']) and df['waste_heat_grid.heat_feedin'].sum() > 0 else 0.0,
            'CHP Electrical Efficiency (%)': lambda df: (df['chp_1.power'].sum() + df['chp_2.power'].sum()) / (df['chp_1.gas'].sum() + df['chp_2.gas'].sum()) * 100 if all(col in df.columns for col in ['chp_1.power', 'chp_2.power', 'chp_1.gas', 'chp_2.gas']) and (df['chp_1.gas'].sum() + df['chp_2.gas'].sum()) > 0 else 0.0,
            'CHP Total Efficiency (%)': lambda df: ((df['chp_1.power'].sum() + df['chp_2.power'].sum()) + (df['chp_1.heat'].sum() + df['chp_2.heat'].sum())) / (df['chp_1.gas'].sum() + df['chp_2.gas'].sum()) * 100 if all(col in df.columns for col in ['chp_1.power', 'chp_2.power', 'chp_1.heat', 'chp_2.heat', 'chp_1.gas', 'chp_2.gas']) and (df['chp_1.gas'].sum() + df['chp_2.gas'].sum()) > 0 else 0.0,
            
            # Operating statistics
            'CHP1 Operating Hours (h)': lambda df: (df['chp_1.power'] > 0).sum() if 'chp_1.power' in df.columns else 0,
            'CHP2 Operating Hours (h)': lambda df: (df['chp_2.power'] > 0).sum() if 'chp_2.power' in df.columns else 0,
            'Total CHP Operating Hours (h)': lambda df: ((df['chp_1.power'] > 0) | (df['chp_2.power'] > 0)).sum() if all(col in df.columns for col in ['chp_1.power', 'chp_2.power']) else 0,
            'Storage Utilization Hours (h)': lambda df: ((df['heat_storage.heat_charging'] > 0) | (df['heat_storage.heat_discharging'] > 0)).sum() if all(col in df.columns for col in ['heat_storage.heat_charging', 'heat_storage.heat_discharging']) else 0,
            
            # Price statistics (if available)
            'Average Power Price (€/MWh)': lambda df: df['power_price'].mean() if 'power_price' in df.columns else 0.0,
            'Max Power Price (€/MWh)': lambda df: df['power_price'].max() if 'power_price' in df.columns else 0.0,
            'Min Power Price (€/MWh)': lambda df: df['power_price'].min() if 'power_price' in df.columns else 0.0,
            'Power Price Std Dev (€/MWh)': lambda df: df['power_price'].std() if 'power_price' in df.columns else 0.0,

            # Demand metrics
            'Total Heat Demand (MWh)': lambda df: df['heat_demand'].sum() if 'heat_demand' in df.columns else 0.0,
            'Average Heat Demand (MW)': lambda df: df['heat_demand'].mean() if 'heat_demand' in df.columns else 0.0,
            'Max Heat Demand (MW)': lambda df: df['heat_demand'].max() if 'heat_demand' in df.columns else 0.0,
            'Min Heat Demand (MW)': lambda df: df['heat_demand'].min() if 'heat_demand' in df.columns else 0.0,

            # Local Demand metrics
            'Local Heat Demand (MWh)': lambda df: df['local_heat_demand'].sum() if 'local_heat_demand' in df.columns else 0.0,
            'Average Local Heat Demand (MW)': lambda df: df['local_heat_demand'].mean() if 'local_heat_demand' in df.columns else 0.0,      
            'Max Local Heat Demand (MW)': lambda df: df['local_heat_demand'].max() if 'local_heat_demand' in df.columns else 0.0,
            'Min Local Heat Demand (MW)': lambda df: df['local_heat_demand'].min() if 'local_heat_demand' in df.columns else 0.0,
        }
    
    def calculate_metrics(self, output_data, scenario_name):
        """Calculate all configured metrics for a scenario."""
        results = {}
        
        for metric_name, metric_function in self.metrics_config.items():
            try:
                results[metric_name] = metric_function(output_data)
            except Exception as e:
                print(f"Error calculating {metric_name}: {str(e)}")
                results[metric_name] = 0.0
        
        return pd.Series(results, name=scenario_name)