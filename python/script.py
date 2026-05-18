import os
import json
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
import folium
from folium.plugins import HeatMap
from pyinaturalist import get_observations

# Create output directories
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out_dir = os.path.join(base_dir, 'docs')
assets_dir = os.path.join(out_dir, 'assets')
os.makedirs(assets_dir, exist_ok=True)

print("Fetching data from iNaturalist...")
# 1. Fetch data
try:
    response = get_observations(project_id="living-lab-campus-agripolis-unipd", page='all')
    
    records = []
    gallery_photos = []
    for obs in response.get('results', []):
        photo_url = ''
        if obs.get('photos') and len(obs['photos']) > 0:
            photo_url = obs['photos'][0].get('url', '')
            if photo_url:
                # Replace 'square' with 'large' for gallery, 'medium' for map
                gallery_url = photo_url.replace('square', 'large')
                photo_url = photo_url.replace('square', 'medium')
                
                # Add to gallery list
                gallery_photos.append({
                    'url': gallery_url,
                    'author': obs.get('user', {}).get('login', 'Unknown'),
                    'taxon': obs.get('taxon', {}).get('name', 'Unknown Species')
                })
                
        record = {
            'id': obs.get('id'),
            'quality_grade': obs.get('quality_grade'),
            'taxon_name': obs.get('taxon', {}).get('name', '') if obs.get('taxon') else '',
            'iconic_taxon_name': obs.get('taxon', {}).get('iconic_taxon_name', 'Other') if obs.get('taxon') else 'Other',
            'latitude': obs.get('geojson', {}).get('coordinates', [None, None])[1] if obs.get('geojson') else None,
            'longitude': obs.get('geojson', {}).get('coordinates', [None, None])[0] if obs.get('geojson') else None,
            'time_observed_at': obs.get('time_observed_at'),
            'photo_url': photo_url,
            'user': obs.get('user', {}).get('login', 'Unknown')
        }
        records.append(record)

    df = pd.DataFrame(records)
    print(f"Total observations fetched: {len(df)}")
    
    # Save gallery JS (take top 12 unique photos to avoid duplicates/clutter)
    if gallery_photos:
        # Simple uniqueness filter based on URL
        seen = set()
        unique_gallery = []
        for p in gallery_photos:
            if p['url'] not in seen:
                seen.add(p['url'])
                unique_gallery.append(p)
        # Save up to 12 images
        unique_gallery = unique_gallery[:12]
        with open(os.path.join(assets_dir, 'gallery.js'), 'w', encoding='utf-8') as f:
            f.write(f"const inatPhotos = {json.dumps(unique_gallery, indent=2)};")
            
except Exception as e:
    print(f"Failed to fetch data: {e}")
    df = pd.DataFrame()

if not df.empty:
    # 2. Clean data
    df_clean = df[
        (df['quality_grade'] != 'casual') &
        (df['taxon_name'].astype(str).str.split().str.len() > 1) &
        (df['latitude'].notnull()) & 
        (df['longitude'].notnull())
    ].copy()

    print(f"Observations after cleaning: {len(df_clean)}")

    if not df_clean.empty:
        # Convert time to datetime
        df_clean['time_observed_at'] = pd.to_datetime(df_clean['time_observed_at'], utc=True)
        # Extract YEAR instead of month
        df_clean['year'] = df_clean['time_observed_at'].dt.year

        # Style settings for plots
        sns.set_theme(style="whitegrid")
        plt.rcParams.update({'font.family': 'sans-serif', 'font.sans-serif': ['Arial']})

        # --- A. Pie Chart ---
        taxon_counts = df_clean.groupby('iconic_taxon_name').size().reset_index(name='count')
        taxon_counts = taxon_counts[taxon_counts['iconic_taxon_name'] != ''].sort_values(by='count', ascending=False)
        taxon_counts['label'] = taxon_counts['iconic_taxon_name'] + " (" + taxon_counts['count'].astype(str) + ")"

        plt.figure(figsize=(10, 8), facecolor='none')
        colors = sns.color_palette('pastel', len(taxon_counts))
        plt.pie(taxon_counts['count'], labels=taxon_counts['label'], autopct='%1.1f%%', startangle=140, colors=colors, textprops={'fontsize': 12, 'color': '#333'})
        plt.title("Proporzione Gruppi Tassonomici", color='#111', fontsize=16, fontweight='bold', pad=20)
        plt.axis('equal')
        plt.savefig(os.path.join(assets_dir, 'pie_chart_py.png'), bbox_inches='tight', dpi=300, transparent=True)
        plt.close()

        # --- B. Activity Over Time (Yearly Bar Chart) ---
        yearly_counts = df_clean.groupby('year').size().reset_index(name='count')
        
        plt.figure(figsize=(10, 6), facecolor='none')
        # Filter out NaN years just in case
        yearly_counts = yearly_counts.dropna()
        yearly_counts['year'] = yearly_counts['year'].astype(int)
        
        ax = sns.barplot(x='year', y='count', data=yearly_counts, palette='viridis')
        plt.title("Attività di Osservazione per Anno", color='#111', fontsize=16, fontweight='bold', pad=15)
        plt.xlabel("Anno", fontsize=12)
        plt.ylabel("Numero di Osservazioni", fontsize=12)
        plt.savefig(os.path.join(assets_dir, 'activity_chart.png'), bbox_inches='tight', dpi=300, transparent=True)
        plt.close()

        # --- C. Top Observers (Bar Chart) ---
        top_users = df_clean.groupby('user').size().reset_index(name='count').sort_values(by='count', ascending=False).head(10)
        plt.figure(figsize=(10, 6), facecolor='none')
        sns.barplot(y='user', x='count', data=top_users, palette='mako')
        plt.title("Top 10 Osservatori (Citizen Scientists)", color='#111', fontsize=16, fontweight='bold', pad=15)
        plt.xlabel("Numero di Osservazioni", fontsize=12)
        plt.ylabel("Utente", fontsize=12)
        plt.savefig(os.path.join(assets_dir, 'top_observers.png'), bbox_inches='tight', dpi=300, transparent=True)
        plt.close()

        print("Charts generated successfully.")

        # --- D. Interactive Map (Distribution) ---
        center_lat = df_clean['latitude'].mean()
        center_lon = df_clean['longitude'].mean()

        m = folium.Map(location=[center_lat, center_lon], zoom_start=16, 
                       tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                       attr='Esri World Imagery', control_scale=True)

        taxons = taxon_counts['iconic_taxon_name'].tolist()
        marker_colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue', 'darkpurple', 'white', 'pink', 'lightblue', 'lightgreen', 'gray', 'black', 'lightgray']
        color_map = {t: marker_colors[i % len(marker_colors)] for i, t in enumerate(taxons)}

        feature_groups = {}
        for taxon in taxons:
            fg = folium.FeatureGroup(name=taxon)
            feature_groups[taxon] = fg
            m.add_child(fg)

        for idx, row in df_clean.iterrows():
            taxon = row['iconic_taxon_name']
            color = color_map.get(taxon, 'gray')
            
            html_popup = f"""
            <div style="font-family: Arial; font-size: 14px; width: 220px; text-align: center;">
                <h4 style="margin-bottom: 5px; color: {color if color not in ['white', 'beige', 'lightgray'] else '#333'}">{row['taxon_name']}</h4>
                <p style="margin: 0; font-size: 12px; color: #666;">Group: {taxon}<br>Observed by: {row['user']}</p>
            """
            if row['photo_url']:
                html_popup += f'<img src="{row["photo_url"]}" style="width: 100%; border-radius: 8px; margin-top: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">'
            
            html_popup += "</div>"
            
            iframe = folium.IFrame(html=html_popup, width=250, height=250 if row['photo_url'] else 100)
            popup = folium.Popup(iframe, max_width=250)

            marker = folium.CircleMarker(
                location=[row['latitude'], row['longitude']],
                radius=6,
                popup=popup,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.9,
                weight=1
            )
            
            if taxon in feature_groups:
                marker.add_to(feature_groups[taxon])

        folium.LayerControl(position='topright', collapsed=False).add_to(m)
        m.save(os.path.join(out_dir, 'map.html'))
        print("Interactive distribution map saved.")

        # --- E. Individual Heatmaps (Selectable by Taxon via HTML dropdown) ---
        # 1. Global Heatmap
        m_heat_all = folium.Map(location=[center_lat, center_lon], zoom_start=16, 
                            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                            attr='Esri World Imagery')
        heat_data_all = [[row['latitude'], row['longitude']] for index, row in df_clean.iterrows()]
        HeatMap(heat_data_all, radius=15, blur=10).add_to(m_heat_all)
        m_heat_all.save(os.path.join(out_dir, 'heatmap.html'))

        # 2. Per-Taxon Heatmaps
        for taxon in taxons:
            taxon_data = df_clean[df_clean['iconic_taxon_name'] == taxon]
            if len(taxon_data) > 0:
                m_heat_taxon = folium.Map(location=[center_lat, center_lon], zoom_start=16, 
                            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                            attr='Esri World Imagery')
                heat_data_taxon = [[row['latitude'], row['longitude']] for index, row in taxon_data.iterrows()]
                HeatMap(heat_data_taxon, radius=15, blur=10, 
                        gradient={0.4: 'blue', 0.65: 'lime', 1: 'red'}).add_to(m_heat_taxon)
                # Create safe filename
                safe_taxon = "".join([c for c in taxon if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(" ", "_")
                m_heat_taxon.save(os.path.join(out_dir, f'heatmap_{safe_taxon}.html'))

        # Write taxon list for HTML dropdown
        safe_taxons = ["".join([c for c in taxon if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(" ", "_") for taxon in taxons]
        with open(os.path.join(assets_dir, 'taxons.js'), 'w') as f:
            f.write(f"const taxonList = {json.dumps([{'name': t, 'safe_name': s} for t, s in zip(taxons, safe_taxons)])};")

        print("Individual heatmaps saved.")

    else:
        print("No valid observations left after cleaning.")
else:
    print("No data to process.")
