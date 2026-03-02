# Road Network Disruption Impact Analysis (Open Data)

## Overview

This project evaluates the criticality of road segments in the state highway network in South Island by simulating road closures and measuring their impact on network performance.

Using publicly available OpenStreetMap data, the project demonstrates how graph-based modelling can support infrastructure resilience and evidence-based decision-making.

---

## Study Area

- Location: South Island, New Zealand  
- Network type: State Highway network  
- Data source: OpenStreetMap (via OSMnx)

---

## Objective

To identify road segments whose failure leads to disproportionate increases in travel distance or network disconnection.

The project simulates individual edge removals and measures resulting impacts on randomly sampled origin–destination (OD) pairs.

---

## Methodology

1. Download South Island road network using OSMnx.
2. Construct a directed graph with edge lengths.
3. Randomly sample OD node pairs.
4. Compute baseline shortest path distances.
5. Remove one road segment at a time.
6. Recalculate shortest paths by distance.
7. Rank road segments by impact severity.

---

## Key Metrics

### Mean Distance Increase (m)

Average additional travel distance caused by a road closure.

### Fraction Unreachable

Proportion of OD pairs that become disconnected after road segment removal.

These metrics approximate network efficiency loss and accessibility degradation.

---

## Results

### Simulated Traffic Flow in CHCH

<img width="1221" height="1003" alt="Flow_lcv_chch" src="https://github.com/user-attachments/assets/cf2b16ce-7d61-4c6b-a2ef-6a19e852903d" />


---

### Spatial Distribution of Critical Segments

<img width="409" height="349" alt="image" src="https://github.com/user-attachments/assets/f8b4bded-3164-4115-bfd0-8a0135661de6" />

---

## Interpretation

Road segments with high disruption impact may warrant:

- Resilience investment prioritisation  
- Redundancy planning  
- Risk-informed asset management  
- Criticality assessment within infrastructure frameworks  

This simplified open-data implementation mirrors the conceptual approach used in transport criticality assessment methodologies.

---

## Technical Stack

- Python  
- OSMnx  
- NetworkX  
- GeoPandas  
- Pandas  
- Matplotlib  

---

## Limitations

- Random OD sampling (not demand-weighted)  
- Distance-based metric (travel time not included since lack real travel speed)  
- Single-edge disruption only  
- No traffic flow or capacity modelling  

---

## Future Extensions

- Incorporate travel time and congestion  
- Demand-weighted OD modelling  
- Multi-edge disruption scenarios  
- Flood-zone simulation  
- Comparison with network centrality measures  

