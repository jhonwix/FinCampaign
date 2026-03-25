"""
Genera customers_200.csv — 200 clientes para pruebas FinCampaign
================================================================
Distribución por segmento:
  SUPER-PRIME  (760–850): 30 clientes
  PRIME        (700–759): 40 clientes
  NEAR-PRIME   (650–699): 50 clientes
  SUBPRIME     (600–649): 50 clientes
  DEEP-SUBPRIME(500–599): 30 clientes

products_of_interest alineados con las 3 campañas de prueba:
  hipotecario | vehiculo | tarjeta de credito
"""
import csv
import random

random.seed(42)

# ── Nombres colombianos realistas ────────────────────────────────────────────
PRIMEROS = [
    "Andrés","María","Carlos","Laura","Santiago","Valentina","Sebastián","Daniela",
    "Felipe","Isabella","Mateo","Camila","Julián","Sara","Diego","Paula","Jorge",
    "Natalia","Alejandro","Sofía","Ricardo","Lucía","Mauricio","Ana María","David",
    "Verónica","Gabriel","Claudia","Esteban","Marcela","Iván","Patricia","Nicolás",
    "Gloria","Fernando","Adriana","Ramón","Liliana","Gustavo","Esperanza","Hernán",
    "Paola","Roberto","Mónica","Arturo","Luz","Pedro","Ximena","Oscar","Nathalia",
]
APELLIDOS = [
    "García","Martínez","López","Rodríguez","Hernández","González","Pérez","Sánchez",
    "Ramírez","Torres","Flores","Rivera","Gómez","Díaz","Reyes","Morales","Castro",
    "Jiménez","Romero","Vargas","Ramos","Gutiérrez","Mendoza","Ortega","Silva",
    "Aguilar","Medina","Suárez","Núñez","Ríos","Acosta","Bernal","Cardona","Ospina",
    "Pardo","Quintero","Ávila","Castaño","Vega","Ruiz","Rojas","Muñoz","Cruz",
    "Salazar","Cano","Montoya","Barrera","Niño","Moreno","Cifuentes",
]

CHANNELS = ["Email", "WhatsApp", "SMS"]

def nombre():
    return f"{random.choice(PRIMEROS)} {random.choice(APELLIDOS)} {random.choice(APELLIDOS)}"

def cedula(base):
    return str(1000000000 + base)

# ── Configuración por segmento ───────────────────────────────────────────────
# (score_min, score_max, income_min, income_max, debt_ratio_min, debt_ratio_max,
#  late_min, late_max, util_min, util_max, age_min, age_max)
SEGMENTS = {
    "SUPER_PRIME": {
        "count": 30,
        "score": (760, 850),
        "income": (6000, 18000),
        "debt_ratio": (0.05, 0.25),   # DTI muy bajo
        "late": (0, 0),
        "util": (5, 25),
        "age": (28, 65),
        # Productos de interés: hipotecario + vehiculo (candidatos ideales para ambas)
        "poi_options": [
            "hipotecario",
            "vehiculo",
            "hipotecario",
            "hipotecario, vehiculo",
            "vehiculo, tarjeta de credito",
            "hipotecario, tarjeta de credito",
        ],
        "existing": [
            "tarjeta de credito, cdt",
            "hipotecario",
            "vehiculo, tarjeta de credito",
            "cdt",
            "",
            "tarjeta de credito",
        ],
    },
    "PRIME": {
        "count": 40,
        "score": (700, 759),
        "income": (4000, 12000),
        "debt_ratio": (0.10, 0.32),
        "late": (0, 1),
        "util": (10, 40),
        "age": (25, 60),
        "poi_options": [
            "hipotecario",
            "vehiculo",
            "tarjeta de credito",
            "hipotecario, vehiculo",
            "vehiculo, tarjeta de credito",
            "hipotecario",
        ],
        "existing": [
            "tarjeta de credito",
            "vehiculo",
            "credito personal",
            "",
            "tarjeta de credito, credito personal",
            "vehiculo, tarjeta de credito",
        ],
    },
    "NEAR_PRIME": {
        "count": 50,
        "score": (650, 699),
        "income": (2500, 8000),
        "debt_ratio": (0.20, 0.42),
        "late": (0, 2),
        "util": (20, 55),
        "age": (22, 58),
        "poi_options": [
            "vehiculo",
            "tarjeta de credito",
            "vehiculo",
            "hipotecario",
            "tarjeta de credito",
            "vehiculo, tarjeta de credito",
            "hipotecario",
        ],
        "existing": [
            "credito personal",
            "tarjeta de credito",
            "",
            "credito personal, tarjeta de credito",
            "vehiculo",
            "",
        ],
    },
    "SUBPRIME": {
        "count": 50,
        "score": (600, 649),
        "income": (1800, 5500),
        "debt_ratio": (0.30, 0.52),
        "late": (1, 4),
        "util": (35, 75),
        "age": (20, 55),
        "poi_options": [
            "tarjeta de credito",
            "vehiculo",
            "tarjeta de credito",
            "credito personal",
            "tarjeta de credito",
            "vehiculo",
            "tarjeta de credito",
        ],
        "existing": [
            "",
            "credito personal",
            "tarjeta de credito",
            "",
            "credito personal",
            "",
        ],
    },
    "DEEP_SUBPRIME": {
        "count": 30,
        "score": (500, 599),
        "income": (900, 3500),
        "debt_ratio": (0.40, 0.75),
        "late": (3, 10),
        "util": (55, 95),
        "age": (18, 50),
        "poi_options": [
            "credito personal",
            "tarjeta de credito",
            "credito personal",
            "credito personal",
            "tarjeta de credito",
        ],
        "existing": [
            "",
            "credito personal",
            "",
            "",
            "tarjeta de credito",
        ],
    },
}

# ── Generación ───────────────────────────────────────────────────────────────
rows = []
idx = 1

for seg_name, cfg in SEGMENTS.items():
    for _ in range(cfg["count"]):
        score = random.randint(*cfg["score"])
        income = round(random.uniform(*cfg["income"]), 2)
        dti_target = random.uniform(*cfg["debt_ratio"])
        monthly_debt = round(income * dti_target, 2)
        late = random.randint(*cfg["late"])
        util = round(random.uniform(*cfg["util"]), 1)
        age = random.randint(*cfg["age"])
        poi = random.choice(cfg["poi_options"])
        existing = random.choice(cfg["existing"])

        rows.append({
            "id_number":           cedula(idx),
            "name":                nombre(),
            "age":                 age,
            "monthly_income":      income,
            "monthly_debt":        monthly_debt,
            "credit_score":        score,
            "late_payments":       late,
            "credit_utilization":  util,
            "products_of_interest": poi,
            "existing_products":   existing,
        })
        idx += 1

random.shuffle(rows)

# ── Escritura CSV ─────────────────────────────────────────────────────────────
out_path = "customers_200.csv"
fields = [
    "id_number","name","age","monthly_income","monthly_debt","credit_score",
    "late_payments","credit_utilization","products_of_interest","existing_products",
]

with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)

print(f"OK: {out_path} generado -- {len(rows)} clientes")

# Resumen distribución
from collections import Counter
def segment_of(score):
    if score >= 760: return "SUPER-PRIME"
    if score >= 700: return "PRIME"
    if score >= 650: return "NEAR-PRIME"
    if score >= 600: return "SUBPRIME"
    return "DEEP-SUBPRIME"

dist = Counter(segment_of(r["credit_score"]) for r in rows)
for seg in ["SUPER-PRIME","PRIME","NEAR-PRIME","SUBPRIME","DEEP-SUBPRIME"]:
    print(f"  {seg:<15} {dist[seg]:>3} clientes")
