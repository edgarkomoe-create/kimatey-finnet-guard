"""
Etape 0 : Analyse exploratoire des donnees (EDA)
Projet Master 1 Informatique - Detection Intelligente des Attaques Reseau
"""
import pandas as pd
import numpy as np
import json

DATA_PATH = "data/Enterprise_Network_Traffic_BigData.csv"

def main():
    df = pd.read_csv(DATA_PATH)

    report = {}
    report["shape"] = df.shape
    report["dtypes"] = df.dtypes.astype(str).to_dict()
    report["missing_values"] = df.isna().sum().to_dict()
    report["missing_pct"] = (df.isna().mean() * 100).round(3).to_dict()
    report["duplicates"] = int(df.duplicated().sum())

    # Statut_Menace peut etre lu comme string ("0","1",...) -> normaliser en int
    df["Statut_Menace"] = df["Statut_Menace"].astype(str).str.strip().astype(int)
    report["class_distribution"] = df["Statut_Menace"].value_counts().sort_index().to_dict()
    report["class_distribution_pct"] = (df["Statut_Menace"].value_counts(normalize=True).sort_index() * 100).round(2).to_dict()

    report["describe"] = df.describe().round(3).to_dict()

    print("=" * 70)
    print("RAPPORT EDA")
    print("=" * 70)
    print(f"Dimensions : {report['shape']}")
    print(f"Doublons   : {report['duplicates']}")
    print("\nValeurs manquantes (%):")
    for k, v in report["missing_pct"].items():
        if v > 0:
            print(f"  {k}: {v}%")
    print("\nDistribution de la variable cible Statut_Menace :")
    labels = {0: "Normal", 1: "Scan de Ports", 2: "DDoS", 3: "Infiltration/Brute-Force"}
    for k, v in report["class_distribution"].items():
        pct = report["class_distribution_pct"][k]
        print(f"  {k} ({labels[k]}): {v} ({pct}%)")

    with open("outputs/eda_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    print("\nRapport sauvegarde dans outputs/eda_report.json")

if __name__ == "__main__":
    main()
