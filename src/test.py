from bs4 import BeautifulSoup

file_path = r"C:\Dev\Hierarchical_search\all_indexes\test_enrichment_html\source_files\Système salarial ‒ Expérience Employé·es et Opérations VPH ‐ EPFL.html"

with open(file_path, 'r', encoding='utf-8') as file:
    html_content = file.read()

soup = BeautifulSoup(html_content, 'html.parser')
elements_with_id = soup.find_all(id=True)
elements_with_id = [el for el in elements_with_id if el.get('id')
                    and 'css' not in el.get('id')
                    and 'icon' not in el.get('id')
                    and 'menu' not in el.get('id').lower()
                    and 'breadcrumb' not in el.get('id').lower()
                    and 'toggle' not in el.get('id').lower()
                    and 'back-to-top' not in el.get('id').lower()
                    ]

elements_with_id_filtered = []
for el in elements_with_id:
    if el.get('class') and any('icon' in cls for cls in el.get('class')):
        continue
    if el.get('class') and any('feather' in cls for cls in el.get('class')):
        continue
    if el.get('class') and any('collapse' in cls for cls in el.get('class')):
        continue

    elements_with_id_filtered.append(el)

print(f"Nombre d'éléments avec un id: {len(elements_with_id)}\n")

for element in elements_with_id_filtered:
    print(f"Balise: <{element.name}>")
    print(f"ID: {element.get('id')}")
    print(f"Classes: {element.get('class', [])}")
    print(f"Autres attributs: {dict(element.attrs)}")
    print(f"Texte: {element.get_text(strip=True)[:100]}...")
    print("=" * 80)