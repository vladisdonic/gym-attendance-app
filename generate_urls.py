#!/usr/bin/env python3
"""
Skript na generovanie unikátnych URL pre NFC tagy a QR kódy
"""

import urllib.parse

# Typy členstva
MEMBERSHIP_TYPES = [
    "Skúšobný tréning",
    "Mesačné členstvo",
    "Jednorázový vstup",
    "Ročné členstvo"
]

# Časy tréningov
TRAINING_TIMES = [
    "9:00",
    "17:00",
    "18:30"
]

BASE_URL = "https://giantgym.streamlit.app/?view=participant"


def create_gym_url(name, membership, time, auto=True):
    """
    Vytvorí unikátne URL pre člena gymu.
    
    Args:
        name: Meno a priezvisko
        membership: Typ členstva (musí byť presne z MEMBERSHIP_TYPES)
        time: Čas tréningu (musí byť presne z TRAINING_TIMES)
        auto: Automatické odoslanie (True/False)
    
    Returns:
        URL string
    """
    params = {
        "name": name,
        "membership": membership,
        "time": time
    }
    if auto:
        params["auto"] = "1"
    
    # URL encoding
    query_string = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
    return f"{BASE_URL}&{query_string}"


def generate_from_csv(csv_file="members.csv"):
    """
    Generuje URL pre všetkých členov z CSV súboru.
    
    Formát CSV:
    Meno,Typ členstva,Čas tréningu
    Ján Novák,Mesačné členstvo,17:00
    """
    import csv
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            results = []
            
            for row in reader:
                name = row.get('Meno', '').strip()
                membership = row.get('Typ členstva', '').strip()
                time = row.get('Čas tréningu', '').strip()
                
                if name and membership and time:
                    url = create_gym_url(name, membership, time, auto=True)
                    results.append({
                        'name': name,
                        'url': url
                    })
                    print(f"✅ {name}: {url}")
                else:
                    print(f"⚠️  Preskočené - chýbajú údaje: {row}")
            
            return results
    except FileNotFoundError:
        print(f"❌ Súbor {csv_file} nebol nájdený!")
        print(f"Vytvor CSV súbor s hlavičkou: Meno,Typ členstva,Čas tréningu")
        return []


if __name__ == "__main__":
    import sys
    
    print("🔗 Generátor unikátnych URL pre Giant Gym\n")
    print("=" * 60)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--csv":
        # Generovanie z CSV
        csv_file = sys.argv[2] if len(sys.argv) > 2 else "members.csv"
        print(f"\n📄 Načítavam z CSV súboru: {csv_file}\n")
        results = generate_from_csv(csv_file)
        
        if results:
            # Uloženie do súboru
            output_file = "generated_urls.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                for item in results:
                    f.write(f"{item['name']}: {item['url']}\n")
            print(f"\n✅ URL uložené do: {output_file}")
    else:
        # Interaktívne generovanie
        print("\n📝 Zadaj údaje pre člena:\n")
        
        name = input("Meno a priezvisko: ").strip()
        
        print("\nTyp členstva:")
        for i, mem_type in enumerate(MEMBERSHIP_TYPES, 1):
            print(f"  {i}. {mem_type}")
        membership_choice = input("Vyber číslo (1-4): ").strip()
        
        try:
            membership = MEMBERSHIP_TYPES[int(membership_choice) - 1]
        except (ValueError, IndexError):
            print("❌ Neplatný výber!")
            sys.exit(1)
        
        print("\nČas tréningu:")
        for i, time in enumerate(TRAINING_TIMES, 1):
            print(f"  {i}. {time}")
        time_choice = input("Vyber číslo (1-3): ").strip()
        
        try:
            time = TRAINING_TIMES[int(time_choice) - 1]
        except (ValueError, IndexError):
            print("❌ Neplatný výber!")
            sys.exit(1)
        
        auto = input("\nAutomatické odoslanie? (a/n, default: a): ").strip().lower()
        auto = auto != 'n'
        
        url = create_gym_url(name, membership, time, auto)
        
        print("\n" + "=" * 60)
        print("✅ Vygenerované URL:")
        print("=" * 60)
        print(url)
        print("=" * 60)
        print("\n📋 Skopíruj tento URL a použij ho pre:")
        print("   - NFC tag")
        print("   - QR kód")
        print("   - Priamy link")

