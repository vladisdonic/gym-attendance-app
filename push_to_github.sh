#!/bin/bash

# Skript na push kódu na GitHub

echo "📤 Pushujem kód na GitHub..."
echo ""

# Kontrola, či existuje remote
if ! git remote get-url origin &>/dev/null; then
    echo "❌ Remote 'origin' nie je nastavený"
    echo "Nastavujem remote..."
    git remote add origin https://github.com/vladisdonic/gym-attendance-app.git
fi

# Kontrola aktuálneho stavu
echo "📋 Aktuálny stav:"
git status --short
echo ""

# Push na GitHub
echo "🚀 Pushujem na GitHub..."
echo "💡 Ak sa ťa opýta na prihlasovacie údaje:"
echo "   - Username: tvoj GitHub username"
echo "   - Password: použij Personal Access Token (nie heslo!)"
echo "   - Token vytvoríš na: https://github.com/settings/tokens"
echo ""

git push -u origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Úspešne pushnuté na GitHub!"
    echo ""
    echo "📝 Ďalšie kroky:"
    echo "1. Choď na https://share.streamlit.io/"
    echo "2. Prihlás sa pomocou GitHub účtu"
    echo "3. Klikni 'New app'"
    echo "4. Vyber repozitár: vladisdonic/gym-attendance-app"
    echo "5. Nastav Main file path: app.py"
    echo "6. V Advanced settings pridaj secrets (pozri DEPLOY.md)"
    echo "7. Klikni 'Deploy!'"
else
    echo ""
    echo "❌ Push zlyhal"
    echo ""
    echo "Možné riešenia:"
    echo "1. Skontroluj prihlasovacie údaje"
    echo "2. Použi Personal Access Token namiesto hesla"
    echo "3. Alebo nastav SSH kľúč"
fi

