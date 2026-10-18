## 7. FDM filament mechanical data (manufacturer TDS)

How to read the tables: the **Src** column names the source document. Every number in that row comes from it unless the cell has its own tag. The tags resolve to URLs in the source list at the end of this section. Values are printed-specimen values as the manufacturer gives them, with the manufacturer's ± scatter. "XY" means in-layer and "Z" means across layers. Local copies of every TDS used are in `research/tds/` (file names are given in the source list).

The model's current PETG assumption, for comparison, is density 1.27 g/cm³, E = 1800 MPa, "yield" 30 MPa (model/petgasus.py, `PETG` dict).

### Test methods, by manufacturer

| Maker | Tensile / flexural / impact standard | Specimen orientation and preparation |
|---|---|---|
| Bambu Lab | ISO 527 + GB/T 1040 (tensile); ISO 178 + GB/T 9341 (bending); ISO 179 + GB/T 1043 (Charpy) [B1..B8] | Separate **X-Y** and **Z** specimens. 100 % infill. Most sheets say the specimens were "annealed and dried" before the test (PETG HF 75 °C/8 h, PETG-CF 65 °C/8 h, PLA 55 °C/8 h, ASA, PA6-CF and PAHT-CF 80 °C/12 h, TPU HF 70 °C/12 h). PETG Basic V3.0 gives no annealing or drying statement. The X-Y impact cell lists two numbers; only the second is labelled "(notched)". |
| Polymaker | ISO 527 + GB/T 1040; ISO 178 + GB/T 9341; ISO 179 + GB/T 1043; TPU uses ISO 37 + GB/T 528 [P1..P9] | Separate **X-Y** and **Z** specimens. Shell 2, top/bottom 3, infill 100 %, fan off, ambient chamber (the specimen diagrams show the Z axis). PA sheets give a **Dry** set and a **Wet** set. CoPA "wet" means conditioned 15 days at 70 % RH and ambient temperature [P4b]. Fiberon PA "wet" means immersed in 60 °C water for 48 h, which leaves 5.30 % (PA6-CF20) or 2.92 % (PA12-CF10) moisture. Fiberon specimens were annealed at 100 °C for 16 h [P5, P6]. |
| Prusament | ISO 527-1 (printed specimens), ISO 178, ISO 179-1 Charpy edgewise; TPU uses ISO 37 [R1..R7] | Columns are **"Horizontal"** and **"Vertical xz"**. The TDS does not define them, and neither is labelled Z. Both are in-layer orientations: flat, and on edge. Prusa Original MK3/MK3S/MK4S or CORE One+, 0.20 mm layers, 2 perimeters, 0 top/bottom, 100 % rectilinear. The across-layer figure is given separately as "Interlayer Adhesion [MPa]" (Prusa Polymers in-house method; ISO 527 for TPU). The PA11 TDS defines a "tensile strength anisotropy coefficient = Z / XY" of 0.84 [R3]. Its interlayer adhesion of 32 MPa ÷ XY yield of 38.3 MPa = 0.84, so Prusa's interlayer-adhesion figure is its Z tensile strength. Prusament gives **elongation at yield**, not at break. |

### 7a. PETG

| Product (TDS version) | Src | Density g/cm³ | E XY MPa | E Z MPa | UTS XY MPa | UTS Z MPa | Elong. break XY / Z % | Impact kJ/m² (Charpy) | Drying | Enclosure / chamber |
|---|---|---|---|---|---|---|---|---|---|---|
| Bambu PETG HF (V1.0) | B1 | 1.28 | 1810 ± 190 | 1540 ± 130 | 34 ± 4 | **23 ± 4** | 8.6 ± 1.2 / 5.1 ± 0.8 | XY 31.5 ± 2.2; XY notched 6.2 ± 1.8; Z 10.6 ± 1.2 | 65 °C 8 h (blast oven); store < 20 % RH; sat. water 0.40 % (25 °C, 55 % RH) | Chamber 35–50 °C; guide: enclosure ✗, desiccant ✗, drying "Optional" [BG] |
| Bambu PETG Basic (V3.0, current) | B2 | 1.25 | 2780 ± 65 | 2550 ± 100 | 51 ± 1 | 35 ± 6 | 9.5 ± 0.7 / 5.2 ± 1.4 | XY 34.2 ± 4.1; Z 10.5 ± 1.8 (notch not stated) | 65 °C 8 h; sat. water 0.45 % | Chamber 35–50 °C; guide ✗ [BG] |
| Bambu PETG Basic (V2.0, superseded) | B2old | 1.25 | 1460 ± 190 | 1120 ± 130 | 48 ± 5 | 39 ± 3 | 11.2 ± 0.8 / 5.7 ± 0.6 | XY 52.7 ± 2.4; XY notched 21.6 ± 1.8; Z 13.6 ± 0.8 | 65 °C 8 h; sat. water 0.32 % | Chamber 35–50 °C |
| Polymaker PolyLite PETG (V5.4) | P1 | 1.25 | 2116.8 ± 68.1 | 1898.7 ± 98.5 | 50.8 ± 0.9 | 42.8 ± 2.8 | 8.4 ± 1.7 / 3.3 ± 0.2 | Notched XY 2.6 ± 0.2; Z N/A | 65 °C 6 h; equil. water 0.54 % | "Closure Chamber: No Needed" |
| Polymaker PETG ("Polymaker™ PETG [NEW]", V3.0) | P2 | 1.30 | 2311.11 ± 92.41 | 2202.91 ± 52.34 | 47.96 ± 4.88 | 45.71 ± 1.76 | 9.33 ± 6.57 / 3.54 ± 2.35 | XY notched 4.95 ± 0.55; XY 20.24 ± 3.95; Z 15.74 ± 3.91 | 60 °C 6 h; max water 0.51 % | "Closure chamber: Not Needed" |
| Prusament PETG (v1.1, 16-02-2022) | R1 | 1.27 | 1500 ± 100 (Horizontal); 1600 ± 100 (Vertical xz) | not published | Yield 47 ± 2 (H); 50 ± 1 (V xz) | Interlayer adhesion **18 ± 4** | Elong. **at yield** 5.1 ± 0.1 (H and V) | Unnotched: no break (H, V); notched 6 ± 1 (H), 3 ± 1 (V xz) | 55 °C 6 h [RD]; water 0.07 % / 24 h, 0.10 % / 7 d | "Enclosure not required" [R1p] |

### 7b. PETG-CF

| Product (TDS version) | Src | Density | E XY | E Z | UTS XY | UTS Z | Elong. XY / Z % | Impact kJ/m² | Drying | Enclosure / nozzle |
|---|---|---|---|---|---|---|---|---|---|---|
| Bambu PETG-CF (V3.0, current) | B3 | 1.25 | 2460 ± 230 | 1340 ± 150 | **35 ± 5** | **29 ± 4** | 10.4 ± 0.6 / 4.7 ± 0.4 | XY 41.2 ± 2.6; XY notched 15.7 ± 1.6; Z 10.7 ± 1.6 | 65 °C 8 h; sat. water 0.30 % | Chamber 35–50 °C; guide: enclosure ✗; hardened steel nozzle, 0.4/0.6/0.8 [BG] |
| Bambu PETG-CF (V2.0, superseded) | B3old | 1.25 | 2460 ± 230 | 1340 ± 150 | **59 ± 4** | **38 ± 3** | 10.4 ± 0.6 / 4.7 ± 0.4 | same as V3.0 | 65 °C 8 h | Chamber 25–45 °C |
| Polymaker Fiberon PETG-rCF08 (V1.0) | P3 | 1.30 | 3710.1 ± 151.1 | 2651.9 ± 51.0 | 59.8 ± 0.3 | 41.1 ± 4.1 | 5.7 ± 1.0 / 1.9 ± 0.3 | XY notched 4.0 ± 0.9; XY unnotched 18.0 ± 1.1; Z unnotched: row present, value blank | 65 °C 3 h; equil. water 0.55 %; "sensitive to moisture", store < 20 % RH | Chamber "Room temp."; brass nozzle life "approximately 9h", hardened/ruby "highly recommended" |
| Prusament PETG Carbon Fiber Black (v1.0, 20-12-2022) | R2 | 1.27 | 1700 ± 100 (H); 1800 ± 100 (V xz) | not published | Yield 47 ± 2 (H); 52 ± 2 (V xz) | Interlayer adhesion 18 ± 3 | Elong. at yield 4.3 ± 0.1 / 4.5 ± 0.2 (H / V) | Unnotched 29 ± 6 (H), 43 ± 8 (V xz); notched not given | 55 °C 6 h ("PETG all versions incl. CF") [RD]; water 0.07 % / 24 h | Page: "Requires a hardened nozzle" [R2p]; no enclosure statement found |

### 7c. PA (nylon), not fibre-filled

| Product (TDS version) | Src | Density | E XY | E Z | UTS XY | UTS Z | Elong. XY / Z % | Impact kJ/m² | Drying | Enclosure / nozzle |
|---|---|---|---|---|---|---|---|---|---|---|
| Polymaker PolyMide CoPA (PA6/66 copolymer), **dry** (V5.5, 2026-01-06) | P4 | 1.12 | 2703 ± 259 | 2209 ± 59 | 78.0 ± 0.7 | 45.8 ± 1.5 | 12.7 ± 2.1 / 1.3 ± 0.1 | Notched XY 6.9 ± 1.4; Z N/A | 100 °C 8 h; equil. water 2.82 % (70 % RH, 23 °C); "sensitive to moisture", store < 20 % RH | "Closure chamber: Needed (ambient temp.)"; brass nozzle abrasion "quite often", hardened steel/ruby "highly recommended" |
| same, **wet** (conditioned) | P4 | — | 724 ± 61 | 660 ± 29 | 34.3 ± 2.5 | 13.7 ± 1.2 | 13.2 ± 2.3 / 1.7 ± 0.2 | Notched XY 27.7 ± 1.2 | — | — |
| Prusament PA11 (natural; v1.0, 22-07-2026) | R3 | 1.02 | 1200 ± 0 (H xy); 1200 ± 0 (V xz) | not published | Yield 38.3 ± 0.8 (H); 39.5 ± 0.5 (V xz) | Interlayer adhesion 32 ± 1; Z/XY anisotropy 0.84 | Elong. at yield 5.6 ± 0.1 (both) | Unnotched N/A; notched 12.9 ± 2.1 (H), 11.7 ± 1.2 (V xz) | 90 °C 6–8 h [R3p]; water 0.26 % / 24 h, 0.46 % / 7 d (25 °C, 30 % RH); "Hygroscopic" | "Enclosure Required, temperature 55 ± 5 °C"; "Standard 0.4 mm brass nozzle" [R3p]; chamber 55 ± 5 °C in TDS |
| Bambu Lab, unfilled PA | — | no unfilled PA product found. Bambu PA products found: PA6-CF, PAHT-CF, PA6-GF, PPA-CF | | | | | | | | |

### 7d. PA-CF

| Product (TDS version) | Src | Density | E XY | E Z | UTS XY | UTS Z | Elong. XY / Z % | Impact kJ/m² | Drying | Enclosure / nozzle |
|---|---|---|---|---|---|---|---|---|---|---|
| Bambu PA6-CF (V3.0) | B4 | 1.09 | 4430 ± 310 | 2170 ± 230 | 102 ± 7 | 48 ± 6 | 5.8 ± 1.6 / 3.7 ± 0.8 | XY 40.3 ± 2.5; XY notched 13.4 ± 1.7; Z 15.5 ± 1.7 | 80 °C 8–12 h; sat. water 2.35 %; store < 20 % RH; guide: drying "Required" [BG] | Chamber 45–60 °C; guide: enclosure ✓; hardened steel, 0.6 recommended [BG] |
| Bambu PAHT-CF (PA12 + other long-chain PA + CF; V3.0), "Mechanical Properties (Dry state)" | B5 | 1.06 | 3860 ± 230 | 2180 ± 130 | 92 ± 7 | 47 ± 5 | 8.4 ± 1.8 / 4.1 ± 1.2 | XY 57.5 ± 3.4; XY notched 22.8 ± 1.8; Z 13.3 ± 0.8 | 80 °C 8–12 h; sat. water 0.88 %; guide: "Required" [BG] | Chamber 45–60 °C; guide ✓; hardened steel, 0.6 recommended [BG] |
| Polymaker Fiberon PA6-CF20, **dry** (V1.1) | P5 | 1.17 | 8636.5 ± 211.4 | 3759.5 ± 118.5 | 109.3 ± 2.4 | 54.0 ± 5.2 | 2.1 ± 0.2 / 1.9 ± 0.4 | XY notched 11.0 ± 0.3; XY unnotched 24.0 ± 1.0; Z unnotched 7.5 ± 2.7 | 100 °C 10 h; equil. water 3.3 %; store < 20 % RH | Chamber "Room Temp."; hardened steel/ruby "highly recommended" (brass ≈ 9 h life) |
| same, **wet** (5.30 % moisture) | P5 | — | 2508.1 ± 82.6 | 1056.1 ± 127.9 | 54.7 ± 1.1 | 25.5 ± 1.2 | 7.0 ± 0.9 / 6.7 ± 1.7 | XY notched 35.6; XY unnotched 73.0; Z unnotched 25.2 | — | — |
| Polymaker Fiberon PA12-CF10, **dry** (V1.1) | P6 | 1.06 | 3311.2 ± 134.9 | 1806.6 ± 145.7 | 77.4 ± 1.1 | 52.2 ± 0.8 | 4.2 ± 0.4 / 5.0 ± 1.0 | XY notched 9.9 ± 0.7; XY unnotched 33.7 ± 1.4; Z unnotched 27.6 ± 3.7 | 100 °C 10 h; equil. water 1.5 % | Chamber "Room Temp."; hardened steel/ruby "highly recommended" |
| same, **wet** (2.92 % moisture) | P6 | — | 3131.7 ± 124.2 | 1622.0 ± 71.7 | 71.7 ± 0.7 | 42.1 ± 1.8 | 5.3 ± 0.3 / 5.3 ± 1.2 | XY notched 10.2; XY unnotched 41.2; Z unnotched 20.6 | — | — |
| Prusament PA11 Carbon Fiber (v1.0, 29-06-2022) | R4 | 1.11 | 2500 ± 100 (H); 3300 ± 100 (V xz) | not published | Yield 42 ± 1 (H); 49 ± 2 (V xz) | Interlayer adhesion 20 ± 5 | Elong. at yield 3.3 ± 0.2 / 2.6 ± 0.3 (H / V) | Unnotched 30 ± 4 (H), 51 ± 4 (V); notched 12 ± 2 (H), 17 ± 1 (V) | 90 °C 6 h [RD]; water 0.20 % / 24 h, 0.50 % / 7 d | TDS: "A hardened nozzle is necessary"; page: "Enclosure recommended" [R4p] |

### 7e. PLA

| Product (TDS version) | Src | Density | E XY | E Z | UTS XY | UTS Z | Elong. XY / Z % | Impact kJ/m² | Drying | Enclosure |
|---|---|---|---|---|---|---|---|---|---|---|
| Bambu PLA Basic (V3.0) | B6 | 1.24 | 2580 ± 220 | 2060 ± 170 | 35 ± 4 | 31 ± 3 | 12.2 ± 1.8 / 7.5 ± 1.3 | XY 26.6 ± 2.8; XY notched 7.9 ± 1.2; Z 13.8 ± 0.9 | 50 °C 8 h (V3.0; the guide says 55 °C 8 h [BG]); sat. water 0.43 % | Chamber 25–45 °C; guide ✗ [BG] |
| Polymaker PolyLite PLA (V5.4) | P7 | 1.17 | 3426.9 ± 64.8 | 3064.9 ± 83.4 | 52.3 ± 0.3 | 40.5 ± 0.5 | 6.3 ± 0.6 / 1.8 ± 0.1 | Notched XY 3.3 ± 0.2; Z N/A | 55 °C 6 h; equil. water 0.51 % | "No Needed" |
| Prusament PLA (v1.1, 27-07-2022) | R5 | 1.24 | 2300 ± 100 (H); 2400 ± 100 (V xz) | not published | Yield 51 ± 3 (H); 59 ± 2 (V xz) | Interlayer adhesion 17 ± 3 | Elong. at yield 2.9 ± 0.3 / 3.2 ± 1.0 | Unnotched 13 ± 1 (H), 14 ± 1 (V); notched "not applicable" | 45 °C 6 h [RD]; water 0.13 % / 24 h, 0.19 % / 7 d | "Enclosure not required" [R5p] |

### 7f. ASA

| Product (TDS version) | Src | Density | E XY | E Z | UTS XY | UTS Z | Elong. XY / Z % | Impact kJ/m² | Drying | Enclosure |
|---|---|---|---|---|---|---|---|---|---|---|
| Bambu ASA (V3.0) | B7 | 1.05 | 2450 ± 270 | 2120 ± 260 | 37 ± 3 | 31 ± 4 | 9.2 ± 1.4 / 4.6 ± 0.8 | XY 41.0 ± 2.3; XY notched 19.6 ± 1.8; Z 4.9 ± 0.6 | 80 °C 8 h; sat. water 0.45 % | Chamber 45–60 °C; guide: enclosure ✓ [BG] |
| Polymaker ASA (sheet says "V6.0"; file name PolyLite_ASA_TDS_EN_V5.4.pdf) | P8 | 1.13 | 2379 ± 157 | 1965 ± 136 | 43.8 ± 0.8 | 32 ± 1.8 | 6.7 ± 0.6 / 1.65 ± 0.2 | Notched XY 10.3 ± 0.4; notched Z 6.7 ± 1.4 | 70 °C 7 h; equil. water 0.40 % | "Closure chamber: Needed" |
| Prusament ASA (v1.1, 20-05-2024) | R6 | 1.07 | 1600 ± 100 (H); 1700 ± 100 (V xz) | not published | Yield 42 ± 1 (H); 45 ± 2 (V xz) | Interlayer adhesion 11 ± 1 | Elong. at yield 3.4 ± 0.2 / 3.8 ± 0.2 | Unnotched 25 ± 3 (H), 38 ± 11 (V); notched 12 ± 1 (H), 15 ± 3 (V) | 80 °C 4 h [RD]; water 0.16 % / 24 h, 0.17 % / 7 d | "Skirt or Enclosure Recommended" [R6p] |

### 7g. TPU 95A

| Product (TDS version) | Src | Density | E XY | E Z | UTS XY | UTS Z | Elong. XY / Z % | Impact / hardness | Drying | Enclosure / nozzle |
|---|---|---|---|---|---|---|---|---|---|---|
| Bambu TPU 95A HF (V1.0) | B8 | 1.22 | 9.8 ± 0.7 | 7.4 ± 0.6 | 27.3 ± 0.8 | 22.3 ± 0.6 | > 650 / > 480 | Impact XY 123.2, Z 86.3 (ISO 179); Shore not stated in TDS | 70 °C 8 h; sat. water 1.08 % (the guide gives TPU95A 1.16 %); guide: drying "Required", seal with desiccant ✓ [BG] | Chamber 25–45 °C; guide: enclosure ✗; nozzle hardened or stainless steel 0.4/0.6/0.8, AMS ✗ [BG] |
| Polymaker PolyFlex TPU95 (V5.4) | P9 | 1.20–1.24 | 33.6 ± 0.9 (ISO 37) | N/A | Not given; stress at 100/200/300/400 % strain = 11.1 / 15.0 / 21.0 / 25.8 | N/A | 551.2 ± 23.5 / N/A | Shore 95A (ISO 7619-1) | 70 °C 8 h; equil. water 0.82 % | "No Needed" |
| Prusament TPU 95A (v1.0, 29-05-2025) | R7 | 1.25 | Not given; "modulus at 100/200/300 % elongation" 8.9 / 14.7 / 21.3 (Horizontal, ISO 37) | not published | 41.4 ± 1.3 (Horizontal, ISO 37) | Interlayer adhesion 9.5 ± 0.2 (ISO 527) | Max elongation 563.3 ± 13.1 (H) | Shore A 92 ± 0.4; Shore D 39 ± 0.7; abrasion 0.21 % (ISO 4649) | 60 °C ≥ 4 h, "usually not necessary" [R7p]; [RD] gives 4–6 h; water 0.02 % / 24 h, 0.04 % / 7 d | "Enclosure not required" [R7p] |

### Enclosure and drying matrix from the Bambu Filament Guide [BG]

These icons were read from the rendered PDF. The crop is saved as `research/tds/bambu_filament_guide_enclosure_row_crop.png`. ✓ = yes, ✗ = no.

| Guide column | PLA | PETG | ABS | ASA | PC | TPU95A | PLA-CF | PETG-CF | PET-CF | PAHT-CF | PA6-CF |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Print with enclosure | ✗ | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ |
| Seal with desiccant | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Dry out before use | Opt. | Opt. | Opt. | Opt. | Req. | Req. | Opt. | Opt. | Req. | Req. | Req. |
| Nozzle | any | any | any | any | any | HS/SS | HS | HS | HS (0.6 rec.) | HS (0.6 rec.) | HS (0.6 rec.) |
| Z impact kJ/m² | 13.8 | 13.6 | 7.4 | 4.9 | 9.0 | 88.7 | 7.8 | 10.7 | 4.5 | 13.3 | 15.5 |

(HS = hardened steel, SS = stainless steel.)

### Not found / conflicting

- **Bambu PETG-CF V2.0 vs V3.0 conflict.** Tensile strength fell from XY 59 / Z 38 MPa to **XY 35 / Z 29 MPa** with no stated reason. Modulus, elongation and impact are identical in both versions [B3old vs B3].
- **Bambu PETG Basic was reformulated.** V2.0 gives E XY 1460, UTS 48 MPa. V3.0 gives E XY 2780, UTS 51 MPa, and the text says it was "upgraded to deliver PLA-level strength". In V3.0 the tensile modulus (2780) is higher than the bending modulus (1950 MPa), the opposite of every other Bambu sheet [B2]. The Filament Guide's "PETG" column (impact 52.7, bending 1670 MPa) still matches the old V2.0 [BG].
- **PETG Z strength spans 23 to 46 MPa across makers:**
  - Bambu PETG HF Z UTS 23 ± 4 MPa [B1]
  - Prusament PETG interlayer adhesion 18 ± 4 MPa [R1]
  - Bambu PETG Basic V3 Z 35 ± 6 MPa [B2]
  - PolyLite PETG Z 42.8 MPa [P1]
  - Polymaker PETG (new) Z 45.7 MPa [P2]
- **PETG XY modulus spans 1460 to 2780 MPa:**
  - Bambu V2 1460 [B2old], Prusament 1500–1600 [R1], Bambu HF 1810 [B1], PolyLite 2117 [P1], Polymaker new 2311 [P2], Bambu Basic V3 2780 [B2].
  - PETG notched Charpy XY: 2.6 [P1], 4.95 [P2], 6.2 [B1], 6 (H) / 3 (V xz) [R1].
- **Prusament publishes no Z modulus** for any material, only an interlayer-adhesion strength. Its "Horizontal" and "Vertical xz" columns are both in-plane orientations; the TDS does not define either. Its elongation is at yield, not at break.
- **Bambu PA densities** are 1.09 g/cm³ (PA6-CF) [B4] and 1.06 (PAHT-CF) [B5]. Polymaker's PA6-CF20 is 1.17 [P5]. All are as published, none were checked.
- **Prusament TPU 95A** lists "Maximum Elongation for Filament 7264 ± 76 %" [R7]. This is printed as given; it is probably a decimal error (the printed-specimen value is 563 %).
- **No Z data** for Polymaker PolyFlex TPU95, and it has no tensile-strength-at-break figure [P9]. Polymaker's Z bending and Z notched impact are "N/A" on most sheets. Fiberon PETG-rCF08's Z unnotched impact row is blank [P3].
- **Bambu Lab unfilled PA:** none found. Bambu's non-CF TPU 95A (V2.0) sheet was not obtained (the polyalkemi.no mirror returns 404). A search snippet quotes 29.6 / 23.2 MPa XY / Z; this is not verified and not used.
- **Polymaker PolyMide PA6-CF TDS V5.4** (polymaker.com/lana-downloads) returns 404. Polymaker's current PA6-CF product is Fiberon PA6-CF20 [P5].
- **Bambu enclosure advice** exists only as icons in the Filament Guide [BG]. The TDSs give only a chamber-temperature range.
- **Prusament drying** values for PLA, PETG, PETG-CF, ASA and PA11-CF are not in the TDSs. They come from Prusa's help article [RD].
- **Polymaker ASA** is served under the file name `PolyLite_ASA_TDS_EN_V5.4.pdf`, but the document inside is "Polymaker™ ASA, V6.0" [P8].

### Source list

Local file names are in `research/tds/`.

- **[B1]** Bambu PETG HF TDS V1.0. https://store.bblcdn.com/3a230e260a3a47c2b0db0156e07eef91.pdf, linked from https://us.store.bambulab.com/products/petg-hf. Byte-identical mirror at https://botland.com.pl/img/art/inne/25540_karta_produktu.pdf. Copy kept outside the repo: `bambu_PETG_HF_TDS_v1.0.pdf`.
- **[B2]** Bambu PETG Basic TDS V3.0. https://store.bblcdn.com/s1/default/cb94589bf7994fdcbfa833badefae9cd/Bambu_PETG_Basic_Technical_Data_Sheet.pdf, from https://us.store.bambulab.com/products/petg-basic. Copy kept outside the repo: `bambu_PETG_Basic_TDS_v3.0.pdf`.
- **[B2old]** Bambu PETG Basic TDS V2.0, reseller mirror. https://www.additive-x.com/shop/mpattachments/file/viewonline/id/580/product_id/2330. Not kept in tds/.
- **[B3]** Bambu PETG-CF TDS V3.0. https://store.bblcdn.com/626e4f424bf345ae965ad0ddfcaf2459.pdf, from https://us.store.bambulab.com/products/petg-cf. Copy kept outside the repo: `bambu_PETG-CF_TDS_v3.0.pdf`.
- **[B3old]** Bambu PETG-CF TDS V2.0, reseller mirror. https://www.additive-x.com/shop/mpattachments/file/viewonline/id/596/product_id/2346.
- **[B4]** Bambu PA6-CF TDS V3.0. https://store.bblcdn.com/b2abc59ac250492b979a52f1ce3e61b3.pdf, from https://us.store.bambulab.com/products/pa6-cf. Copy kept outside the repo: `bambu_PA6-CF_TDS_v3.0.pdf`.
- **[B5]** Bambu PAHT-CF TDS V3.0. https://store.bblcdn.com/7166b20bc68f4c87b32c972b856eeb4b.pdf, from https://us.store.bambulab.com/products/paht-cf. Copy kept outside the repo: `bambu_PAHT-CF_TDS_v3.0.pdf`.
- **[B6]** Bambu PLA Basic TDS V3.0. https://store.bblcdn.com/s1/default/58b85d0f3db94878854a28fdb8a0006e/Bambu_PLA_Basic_Technical_Data_Sheet.pdf, from https://us.store.bambulab.com/products/pla-basic-filament. Copy kept outside the repo: `bambu_PLA_Basic_TDS_v3.0.pdf`.
- **[B7]** Bambu ASA TDS V3.0. https://store.bblcdn.com/ad7b08230c164e72856cffbe06bb7dc9.pdf, from https://us.store.bambulab.com/products/asa-filament. Copy kept outside the repo: `bambu_ASA_TDS_v3.0.pdf`.
- **[B8]** Bambu TPU 95A HF TDS V1.0. https://store.bblcdn.com/58df32731eab4c90a7dac9b12e13ba88.pdf, from https://us.store.bambulab.com/products/tpu-95a-hf. Copy kept outside the repo: `bambu_TPU_95A_HF_TDS_v1.0.pdf`.
- **[BG]** Bambu Filament Guide (en, rev 4). https://cdn1.bambulab.com/filament/a5e185aed14e6/filament-guide-en-4.pdf. Copy kept outside the repo: `bambu_filament_guide_en4.pdf` and `bambu_filament_guide_enclosure_row_crop.png`.
- **[P1]** Polymaker PolyLite PETG TDS V5.4. https://cdn.shopify.com/s/files/1/0548/7299/7945/files/PolyLite_PETG_TDS_EN_V5.4.pdf, linked from https://wiki.polymaker.com/polymaker-products/more-about-our-products/documents/technical-data-sheets/petg-pet/polylite-tm-petg. Copy kept outside the repo: `polymaker_PolyLite_PETG_TDS_EN_V5.4.pdf`.
- **[P2]** Polymaker PETG [NEW] TDS V3.0. https://cdn.shopify.com/s/files/1/0548/7299/7945/files/PETG_TDS_Polymaker_297e875c-5d38-4d2b-ba68-eef8916de183.pdf?v=1772830046, linked from https://wiki.polymaker.com/polymaker-products/more-about-our-products/documents/technical-data-sheets/petg-pet/polymaker-tm-petg-new. Copy kept outside the repo: `polymaker_PETG_NEW_TDS.pdf`.
- **[P3]** Polymaker Fiberon PETG-rCF08 TDS V1.0. https://fiberon.polymaker.com/wp-content/uploads/TDS_FIBERON-PETG-rCF08_V1.0_EN.pdf. Copy kept outside the repo: `polymaker_Fiberon_PETG-rCF08_TDS_V1.0.pdf`.
- **[P4]** Polymaker PolyMide CoPA TDS V5.5 (2026-01-06). https://polymaker.com/wp-content/uploads/lana-downloads/TDS_Polymaker_PolyMide-CoPA_V5.5_2026-01-06_EN.pdf. Copy kept outside the repo: `polymaker_PolyMide_CoPA_TDS_V5.5_2026-01-06.pdf`.
- **[P4b]** PolyMide CoPA TDS V5.1, used only for the conditioning description. https://core-electronics.com.au/attachments/uploads/PolyMide_CoPA_TDS_V5_1.pdf. Copy kept outside the repo: `polymaker_PolyMide_CoPA_TDS_V5.1_coreelectronics.pdf`.
- **[P5]** Polymaker Fiberon PA6-CF20 TDS V1.1. https://cdn.shopify.com/s/files/1/0548/7299/7945/files/TDS_FIBERON_PA6-CF20_V1.1_EN.pdf?v=1733846088. Copy kept outside the repo: `polymaker_Fiberon_PA6-CF20_TDS_V1.1.pdf`.
- **[P6]** Polymaker Fiberon PA12-CF10 TDS V1.1. https://cdn.shopify.com/s/files/1/0548/7299/7945/files/TDS_FIBERON_PA12-CF10_V1.1_EN.pdf?v=1740427088. Copy kept outside the repo: `polymaker_Fiberon_PA12-CF10_TDS_V1.1.pdf`.
- **[P7]** Polymaker PolyLite PLA TDS V5.4. https://cdn.shopify.com/s/files/1/0548/7299/7945/files/PolyLite_PLA_TDS_EN_V5.4.pdf. Copy kept outside the repo: `polymaker_PolyLite_PLA_TDS_EN_V5.4.pdf`.
- **[P8]** Polymaker ASA TDS V6.0. https://cdn.shopify.com/s/files/1/0548/7299/7945/files/PolyLite_ASA_TDS_EN_V5.4.pdf, linked from https://wiki.polymaker.com/polymaker-products/more-about-our-products/documents/technical-data-sheets/abs-asa/polymaker-tm-asa. Copy kept outside the repo: `polymaker_ASA_TDS_V6.0_file-PolyLite_ASA_TDS_EN_V5.4.pdf`.
- **[P9]** Polymaker PolyFlex TPU95 TDS V5.4. https://cdn.shopify.com/s/files/1/0548/7299/7945/files/PolyFlex_TPU95_TDS_EN_V5.4.pdf. Copy kept outside the repo: `polymaker_PolyFlex_TPU95_TDS_EN_V5.4.pdf`.
- **[R1]** Prusament PETG TDS v1.1. https://storage.googleapis.com/prusa3d-content-prod-14e8-wordpress-prusament-prod/2023/10/9f8d2165-tds_prusament-petg_n_en.pdf. Copy kept outside the repo: `prusament_PETG_TDS.pdf`.
  - **[R1p]** Product page: https://prusament.com/materials/prusament-petg/
- **[R2]** Prusament PETG Carbon Fiber Black TDS v1.0, taken from the zip https://prusament.com/wp-content/uploads/2023/02/TDS_Prusament-PETG-CF-Black.zip. Copy kept outside the repo: `prusament_PETG-CF_Black_TDS_EN.pdf`.
  - **[R2p]** Product page: https://prusament.com/materials/prusament-petg-carbon-fiber/
- **[R3]** Prusament PA11 TDS v1.0. https://storage.googleapis.com/prusa3d-content-prod-14e8-wordpress-prusament-prod/2026/08/2d2145fc-pa11_tds_eng.pdf. Copy kept outside the repo: `prusament_PA11_TDS.pdf`.
  - **[R3p]** Product page: https://prusament.com/materials/prusament-pa11/
- **[R4]** Prusament PA11 Carbon Fiber TDS v1.0. https://prusament.com/wp-content/uploads/2022/08/TDS_PA11CFB.pdf. Copy kept outside the repo: `prusament_PA11_Carbon_Fiber_TDS.pdf`.
  - **[R4p]** Product page: https://prusament.com/materials/prusament-pa11-nylon-carbon-fiber/
- **[R5]** Prusament PLA TDS v1.1 (2022), taken from the zip https://storage.googleapis.com/prusa3d-content-prod-14e8-wordpress-prusament-prod/2024/05/7ca620c4-prusament-pla-plablend.zip. Copy kept outside the repo: `prusament_PLA_TDS_2022_EN.pdf`.
  - **[R5p]** Product page: https://prusament.com/materials/pla/
- **[R6]** Prusament ASA TDS v1.1 (2024). https://storage.googleapis.com/prusa3d-content-prod-14e8-wordpress-prusament-prod/2024/05/bc8551ef-tds_prusament-asa_2024_en.pdf. Copy kept outside the repo: `prusament_ASA_TDS_2024.pdf`.
  - **[R6p]** Product page: https://prusament.com/materials/prusament-asa/
- **[R7]** Prusament TPU 95A TDS v1.0. https://storage.googleapis.com/prusa3d-content-prod-14e8-wordpress-prusament-prod/2025/05/80316f6d-tds-prusament_tpu_95a_en-1.pdf. Copy kept outside the repo: `prusament_TPU_95A_TDS.pdf`.
  - **[R7p]** Product page: https://prusament.com/materials/prusament-tpu-95a/
- **[RD]** Prusa Knowledge Base, "Drying filament": https://help.prusa3d.com/article/drying-filament_332086. Values: PLA 45 °C 6 h; PETG (all versions incl. CF) 55 °C 6 h; TPU 60 °C 4–6 h; ASA 80 °C 4 h; PA11 CF 90 °C 6 h.
