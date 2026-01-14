#!/bin/bash

# Skript na pripravenie projektu na deploy na Streamlit Cloud

echo "🚀 Pripravujem projekt na deploy..."

# Kontrola, či už existuje git repozitár
if [ -d ".git" ]; then
    echo "✅ Git repozitár už existuje"
else
    echo "📦 Inicializujem Git repozitár..."
    git init
    echo "✅ Git repozitár inicializovaný"
fi

# Kontrola, či sú všetky potrebné súbory
echo "📋 Kontrolujem súbory..."

if [ ! -f "app.py" ]; then
    echo "❌ Chýba app.py"
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo "❌ Chýba requirements.txt"
    exit 1
fi

if [ ! -f ".gitignore" ]; then
    echo "❌ Chýba .gitignore"
    exit 1
fi

echo "✅ Všetky potrebné súbory sú prítomné"

# Kontrola, či secrets.toml nie je v root (mal by byť len v .streamlit/)
if [ -f "secrets.toml" ] && [ ! -f ".streamlit/secrets.toml" ]; then
    echo "⚠️  Nájdený secrets.toml v root adresári"
    echo "   Tento súbor by mal byť v .streamlit/secrets.toml"
fi

# Kontrola, či .streamlit/secrets.toml existuje
if [ -f ".streamlit/secrets.toml" ]; then
    echo "✅ .streamlit/secrets.toml existuje"
    echo "   ⚠️  UISTI SA, že tento súbor je v .gitignore!"
else
    echo "⚠️  .streamlit/secrets.toml neexistuje"
    echo "   Budeš ho musieť vytvoriť alebo pridať do Streamlit Cloud secrets"
fi

# Kontrola .gitignore
if grep -q ".streamlit/secrets.toml" .gitignore; then
    echo "✅ .streamlit/secrets.toml je v .gitignore"
else
    echo "⚠️  .streamlit/secrets.toml NIE JE v .gitignore!"
    echo "   Pridaj ho do .gitignore pred pushom na GitHub!"
fi

echo ""
echo "📝 Ďalšie kroky:"
echo "1. Vytvor repozitár na GitHub.com"
echo "2. Spusti: git add ."
echo "3. Spusti: git commit -m 'Initial commit'"
echo "4. Spusti: git remote add origin https://github.com/TVOJ_USERNAME/TVOJ_REPO.git"
echo "5. Spusti: git push -u origin main"
echo "6. Choď na share.streamlit.io a vytvor novú aplikáciu"
echo "7. V Advanced settings pridaj secrets (obsah .streamlit/secrets.toml)"
echo ""
echo "📖 Podrobný návod nájdeš v súbore DEPLOY.md"
echo ""
echo "✅ Projekt je pripravený na deploy!"





