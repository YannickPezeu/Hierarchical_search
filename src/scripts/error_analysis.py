#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from collections import Counter


def analyze_failed_pages(state_file):
    """Analyse les pages échouées depuis le fichier crawler_state.json"""

    if not Path(state_file).exists():
        print(f"❌ Fichier introuvable: {state_file}")
        sys.exit(1)

    with open(state_file, 'r', encoding='utf-8') as f:
        state = json.load(f)

    failed = state.get('failed', [])

    if not failed:
        print("✅ Aucune page échouée!")
        return

    # Convertir de format [[url, metadata], ...] à dict
    failed_dict = dict(failed)

    print('=' * 80)
    print(f'❌ PAGES ÉCHOUÉES: {len(failed_dict)}')
    print('=' * 80)

    # Compter les erreurs par type
    error_types = Counter()
    for url, metadata in failed_dict.items():
        error_msg = metadata.get('error', 'Unknown error')
        error_types[error_msg] += 1

    print('\n📊 Erreurs par type:')
    print('-' * 80)
    for error_type, count in error_types.most_common():
        percentage = (count / len(failed_dict)) * 100
        print(f"  {error_type:<50} {count:>5} ({percentage:.1f}%)")

    # Grouper par type d'erreur
    errors_grouped = {}
    for url, metadata in failed_dict.items():
        error_msg = metadata.get('error', 'Unknown error')
        if error_msg not in errors_grouped:
            errors_grouped[error_msg] = []
        errors_grouped[error_msg].append({
            'url': url,
            'referrer': metadata.get('referrer'),
            'timestamp': metadata.get('timestamp')
        })

    # Afficher les détails par type d'erreur
    print('\n' + '=' * 80)
    print('📋 DÉTAILS PAR TYPE D\'ERREUR')
    print('=' * 80)

    for error_type, pages in sorted(errors_grouped.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n🔴 {error_type} ({len(pages)} pages)")
        print('-' * 80)

        # Afficher les 10 premières de chaque type
        for i, page in enumerate(pages[:10], 1):
            print(f"{i}. {page['url']}")
            if page['referrer']:
                print(f"   ↳ From: {page['referrer']}")

        if len(pages) > 10:
            print(f"   ... et {len(pages) - 10} autres pages")

    # Exporter vers un fichier texte
    output_file = Path(state_file).parent / 'failed_pages.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"PAGES ÉCHOUÉES - Total: {len(failed_dict)}\n")
        f.write("=" * 100 + "\n\n")

        for error_type, pages in sorted(errors_grouped.items(), key=lambda x: len(x[1]), reverse=True):
            f.write(f"\n{error_type} ({len(pages)} pages)\n")
            f.write("-" * 100 + "\n")
            for page in pages:
                f.write(f"{page['url']}\n")
                if page['referrer']:
                    f.write(f"  From: {page['referrer']}\n")
                f.write(f"  Time: {page['timestamp']}\n\n")

    print(f"\n💾 Détails exportés vers: {output_file}")
    print("=" * 80)


def main():
    # Chemin par défaut
    if len(sys.argv) > 1:
        state_file = sys.argv[1]
    else:
        script_dir = Path(__file__).parent
        state_file = script_dir / '../../all_indexes/large_campus2/source_files/crawler_state.json'

    state_file = Path(state_file).resolve()

    print(f'📁 Lecture de: {state_file}\n')
    analyze_failed_pages(state_file)


if __name__ == '__main__':
    main()