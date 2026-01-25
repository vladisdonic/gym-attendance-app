# 🔗 Generátor unikátnych URL pre NFC tagy a QR kódy

## Ako to funguje

Aplikácia teraz podporuje parametrické URL, ktoré automaticky vyplnia formulár a môžu ho aj automaticky odoslať.

## Formát URL

```
https://giantgym.streamlit.app/?view=participant&name=MENO&membership=TYP&time=ČAS&auto=1
```

## Parametre

| Parameter | Popis | Príklady | Povinné |
|-----------|-------|----------|---------|
| `view` | Typ pohľadu | `participant` | Áno |
| `name` | Meno a priezvisko | `Ján Novák` (URL encoded: `Ján%20Novák`) | Áno pre auto |
| `membership` | Typ členstva | `Mesačné členstvo`, `Skúšobný tréning`, `Jednorázový vstup`, `Ročné členstvo` | Áno pre auto |
| `time` | Čas tréningu | `7:00`, `9:00`, `15:30`, `17:00`, `18:30` | Áno pre auto |
| `auto` | Automatické odoslanie | `1` = automaticky, `0` alebo chýba = manuálne | Nie |

## Typy členstva (presné názvy)

- `Skúšobný tréning`
- `Mesačné členstvo`
- `Jednorázový vstup`
- `Ročné členstvo`

## Časy tréningov

- `7:00`
- `9:00`
- `15:30`
- `17:00`
- `18:30`

## Príklady URL

### 1. Automatické prihlásenie (odporúčané pre NFC)

```
https://giantgym.streamlit.app/?view=participant&name=Ján%20Novák&membership=Mesačné%20členstvo&time=17:00&auto=1
```

### 2. Automatické vyplnenie, manuálne odoslanie

```
https://giantgym.streamlit.app/?view=participant&name=Peter%20Horák&membership=Ročné%20členstvo&time=18:30
```

### 3. Len vyplnenie mena

```
https://giantgym.streamlit.app/?view=participant&name=Ján%20Novák
```

## Ako vytvoriť URL

### Manuálne

1. Začni so základným URL: `https://giantgym.streamlit.app/?view=participant`
2. Pridaj parametre:
   - `&name=` + URL encoded meno (medzery = `%20`)
   - `&membership=` + typ členstva (presne ako v zozname)
   - `&time=` + čas tréningu
   - `&auto=1` pre automatické odoslanie

### Online nástroje

- **URL Encoder:** https://www.urlencoder.org/
- **QR Code Generator:** https://www.qr-code-generator.com/

### Python skript (pre hromadné vytvorenie)

```python
import urllib.parse

def create_gym_url(name, membership, time, auto=True):
    base_url = "https://giantgym.streamlit.app/?view=participant"
    params = {
        "name": name,
        "membership": membership,
        "time": time
    }
    if auto:
        params["auto"] = "1"
    
    # URL encoding
    query_string = "&".join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
    return f"{base_url}&{query_string}"

# Príklad použitia
url = create_gym_url("Ján Novák", "Mesačné členstvo", "17:00", auto=True)
print(url)
```

## Vytvorenie NFC tagov

### 1. Kúp NFC tagy
- NFC NTAG215 (odporúčané - 504 bajtov, stačí na URL)
- Dostupné na: Amazon, Alza, atď.

### 2. Naprogramuj NFC tag

**Android:**
- Aplikácia: "NFC Tools" alebo "TagWriter"
- Vyber "Write a URL"
- Vlož vytvorené URL
- Prilož telefón k NFC tagu

**iPhone:**
- Použi aplikáciu "Shortcuts"
- Vytvor automatizáciu, ktorá otvorí URL pri priložení NFC tagu

### 3. Otestuj
- Prilož telefón k NFC tagu
- Mala by sa otvoriť aplikácia s automaticky vyplneným formulárom
- Ak je `auto=1`, formulár sa automaticky odosiela

## Vytvorenie QR kódov

### Online generátory:
1. https://www.qr-code-generator.com/
2. https://qr-code-generator.com/
3. https://www.qrcode-monkey.com/

### Postup:
1. Vlož vytvorené URL
2. Vygeneruj QR kód
3. Stiahni a vytlač
4. Nalepte na stenu alebo vytvorte kartičky

## Hromadné vytvorenie pre všetkých členov

### Excel/Google Sheets vzorec:

```
="https://giantgym.streamlit.app/?view=participant&name="&ENCODEURL(A2)&"&membership="&ENCODEURL(B2)&"&time="&C2&"&auto=1"
```

Kde:
- A2 = Meno
- B2 = Typ členstva
- C2 = Čas tréningu

### Príklad dát:

| Meno | Typ členstva | Čas | URL |
|------|--------------|-----|-----|
| Ján Novák | Mesačné členstvo | 17:00 | (vzorec) |
| Peter Horák | Ročné členstvo | 18:30 | (vzorec) |

## Bezpečnosť

⚠️ **Dôležité:**
- URL obsahujú osobné údaje (meno)
- Každý člen by mal mať svoj unikátny NFC tag/QR kód
- NFC tagy by mali byť fyzicky chránené (napr. v kartičke)
- Ak sa tag stratí, vytvor nový URL (možno zmeniť parameter)

## Riešenie problémov

### URL sa neotvorí správne
- Skontroluj, či sú všetky parametre URL encoded
- Over, či typ členstva a čas sú presne ako v zozname

### Formulár sa nevyplní
- Skontroluj, či sú parametre správne napísané
- Over, či typ členstva a čas presne zodpovedajú možnostiam

### Automatické odoslanie nefunguje
- Skontroluj, či je parameter `auto=1` prítomný
- Over, či sú všetky povinné parametre vyplnené

## Príklady pre rôzne scenáre

### Ranný tréning (7:00)
```
https://giantgym.streamlit.app/?view=participant&name=Meno%20Priezvisko&membership=Mesačné%20členstvo&time=7:00&auto=1
```

### Ranný tréning (9:00)
```
https://giantgym.streamlit.app/?view=participant&name=Meno%20Priezvisko&membership=Mesačné%20členstvo&time=9:00&auto=1
```

### Popoludňajší tréning (15:30)
```
https://giantgym.streamlit.app/?view=participant&name=Meno%20Priezvisko&membership=Mesačné%20členstvo&time=15:30&auto=1
```

### Popoludňajší tréning (17:00)
```
https://giantgym.streamlit.app/?view=participant&name=Meno%20Priezvisko&membership=Mesačné%20členstvo&time=17:00&auto=1
```

### Večerný tréning (18:30)
```
https://giantgym.streamlit.app/?view=participant&name=Meno%20Priezvisko&membership=Mesačné%20členstvo&time=18:30&auto=1
```

---

**Vytvorené:** Pre aplikáciu Giant Gym Attendance
**URL aplikácie:** https://giantgym.streamlit.app





