import streamlit as st
import json
import networkx as nx
import requests
import folium
from streamlit_folium import st_folium

# --- TomTom API Ayarı ---
TOMTOM_API_KEY = "GReUWZDvni00hRkWoGCKgSl2tR1GqN4R"

# --- Otobüs Hatları Verisi (Direkt Kod İçine Gömüldü) ---
bus_lines = {
    "DT1": {
        "district": "Şişli",
        "stops": [
            "BEŞİKTAŞ - VADİ",
            "BEŞİKTAŞ - ULUS MAHALLESİ",
            "BEŞİKTAŞ - NİSPETİYE METRO",
            "BEŞİKTAŞ - GAYRETTEPE METRO",
            "ŞİŞLİ - ŞİŞLİ CAMİ",
            "BEŞİKTAŞ - ÇIRAĞAN",
            "VİYADÜK ALTI - BEŞİKTAŞ",
            "TAKSİM - BEYOĞLU"
        ]
    },
    "30A": {
        "district": "Şişli",
        "stops": [
            "BEŞİKTAŞ - BEŞİKTAŞ PERONLAR",
            "ŞİŞLİ - ALİ SAMİ YEN",
            "ŞİŞLİ - ŞİŞLİ CAMİİ",
            "ŞİŞLİ - NİŞANTASI",
            "ŞİŞLİ - DOLMABAHÇE GAZHANE CADDESİ",
            "BEŞİKTAŞ - DENİZ MÜZESİ"
        ]
    },
    "122C": {
        "district": "Şişli",
        "stops": [
            "ÜMRANİYE - TEPEÜSTÜ",
            "BEYKOZ - KAVACIK",
            "ŞİŞLİ - LEVENT",
            "ŞİŞLİ - ZİNCİRLİKUYU",
            "ŞİŞLİ - ALİ SAMİ YEN",
            "ŞİŞLİ - MECİDİYEKÖY VİYADÜK"
        ]
    },
    "12": {
        "district": "Şişli",
        "stops": [
            "KADIKÖY - KADIKÖY",
            "KADIKÖY - AYRILIKÇEŞMESİ MARMARAY",
            "ÜSKÜDAR - KARACAHMET",
            "ÜSKÜDAR - DOĞANCILAR",
            "ÜSKÜDAR - AHMEDİYE",
            "ÜSKÜDAR - ÜSKÜDAR MARMARAY"
        ]
    }
}

# --- Durak Koordinatları JSON Dosyasını Yükle ---
with open("data/stop_locations.json", "r", encoding="utf-8") as f:
    stop_locations = json.load(f)

# --- Sayfa Yapılandırması ---
st.set_page_config(page_title="İstanbul Otobüs Rota Bulucu", layout="centered")
st.title("🚌 İstanbul Otobüs Rota Bulucu")

# --- Kullanıcıdan Girdi Al ---
selected_line = st.selectbox("Otobüs Hattı Seçin", list(bus_lines.keys()))
available_stops = bus_lines[selected_line]["stops"]

start_stop = st.selectbox("Başlangıç Durağı", available_stops)
end_stop = st.selectbox("Varış Durağı", available_stops)

if st.button("Rota Bul"):
    st.session_state["goster"] = True
    st.session_state["start_stop"] = start_stop
    st.session_state["end_stop"] = end_stop
    st.session_state["selected_line"] = selected_line

if "goster" not in st.session_state or not st.session_state["goster"]:
    st.stop()

start = st.session_state["start_stop"]
end = st.session_state["end_stop"]
selected_line = st.session_state["selected_line"]

# --- Yolculuk Süresi Fonksiyonu ---
def get_travel_time(origin, destination):
    lat1, lon1 = origin
    lat2, lon2 = destination
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{lat1},{lon1}:{lat2},{lon2}/json?key={TOMTOM_API_KEY}&traffic=true"
    try:
        r = requests.get(url)
        r.raise_for_status()
        return r.json()['routes'][0]['summary']['travelTimeInSeconds'] / 60
    except Exception as e:
        print(f"TomTom API hatası: {e}")
        return 5.0  # fallback

# --- Seçilen Hat Üzerinden Grafik Kur ---
def build_single_line_graph(line_code, bus_lines, stop_locations, get_time_fn):
    G = nx.Graph()
    stops = bus_lines[line_code]["stops"]
    for i in range(len(stops)-1):
        s1, s2 = stops[i], stops[i+1]
        if s1 in stop_locations and s2 in stop_locations:
            duration = get_time_fn(stop_locations[s1], stop_locations[s2])
            G.add_edge(s1, s2, weight=duration, line=line_code)
    return G

# --- Rota Bul ---
def find_shortest_route(graph, start, end):
    try:
        return nx.dijkstra_path(graph, start, end, weight="weight")
    except Exception as e:
        print(f"Rota bulunamadı: {e}")
        return []

G = build_single_line_graph(selected_line, bus_lines, stop_locations, get_travel_time)
route = find_shortest_route(G, start, end)

# --- Sonuçları Göster ---
if route:
    st.success(f"{start} → {end} rotası bulundu: {len(route)-1} durak")
    st.markdown("### 📍 Rota Üzerindeki Duraklar:")
    for i, stop in enumerate(route):
        st.write(f"{i+1}. {stop}")

    toplam_sure = sum(G[route[i]][route[i+1]]["weight"] for i in range(len(route)-1))
    st.info(f"🕒 Tahmini Süre: {toplam_sure:.1f} dakika")

    # Harita
    m = folium.Map(location=stop_locations[start], zoom_start=13, tiles="CartoDB positron")
    for i in range(len(route)-1):
        s1, s2 = route[i], route[i+1]
        folium.PolyLine(
            [stop_locations[s1], stop_locations[s2]],
            color="green", weight=5,
            tooltip=f"{s1} → {s2} ({selected_line})"
        ).add_to(m)
    for stop in route:
        folium.CircleMarker(
            location=stop_locations[stop],
            radius=6,
            color="black",
            fill_color="lightgreen",
            fill=True,
            popup=stop
        ).add_to(m)

    st_folium(m, width=700, height=500)
else:
    st.error(f"{selected_line} hattı üzerinde {start} ile {end} arasında bir bağlantı bulunamadı.")
