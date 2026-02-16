#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from collections import defaultdict


def format_bytes(bytes_size):
    """Formate les octets en unités lisibles"""
    if bytes_size == 0:
        return '0 B'

    units = ['B', 'KB', 'MB', 'GB', 'TB']
    k = 1024
    i = 0
    size = float(bytes_size)

    while size >= k and i < len(units) - 1:
        size /= k
        i += 1

    return f"{size:.2f} {units[i]}"


def count_files(root_path):
    """Compte récursivement tous les fichiers et dossiers"""
    stats = {
        'total_files': 0,
        'total_dirs': 0,
        'by_extension': defaultdict(lambda: {'count': 0, 'size': 0}),
        'total_size': 0,
        'largest_file': {'path': '', 'size': 0},
        'errors': []
    }

    for dirpath, dirnames, filenames in os.walk(root_path):
        stats['total_dirs'] += len(dirnames)

        for filename in filenames:
            filepath = os.path.join(dirpath, filename)

            try:
                file_size = os.path.getsize(filepath)
                stats['total_files'] += 1
                stats['total_size'] += file_size

                # Extension
                ext = Path(filename).suffix.lower() or '(no extension)'
                stats['by_extension'][ext]['count'] += 1
                stats['by_extension'][ext]['size'] += file_size

                # Plus gros fichier
                if file_size > stats['largest_file']['size']:
                    stats['largest_file'] = {'path': filepath, 'size': file_size}

            except (OSError, PermissionError) as e:
                stats['errors'].append({'path': filepath, 'error': str(e)})

    return stats


def main():
    # Chemin par défaut ou depuis argument
    if len(sys.argv) > 1:
        target_path = sys.argv[1]
    else:
        script_dir = Path(__file__).parent
        target_path = script_dir / '../../all_indexes/large_campus2'

    target_path = Path(target_path).resolve()

    # Vérifier que le chemin existe
    if not target_path.exists():
        print(f"❌ Erreur: Le chemin n'existe pas: {target_path}")
        sys.exit(1)

    print('🔍 Analyse en cours...')
    print(f'📁 Chemin: {target_path}\n')

    import time
    start_time = time.time()
    stats = count_files(target_path)
    duration = (time.time() - start_time) * 1000  # en ms

    # Affichage des résultats
    print('=' * 60)
    print('📊 RÉSULTATS')
    print('=' * 60)
    print(f"📁 Dossiers:        {stats['total_dirs']:,}")
    print(f"📄 Fichiers:        {stats['total_files']:,}")
    print(f"💾 Taille totale:   {format_bytes(stats['total_size'])}")
    print(f"⏱️  Durée:           {duration:.0f} ms")
    print('=' * 60)

    print('\n📋 Répartition par type de fichier:')
    print('-' * 60)

    # Trier par nombre de fichiers
    sorted_extensions = sorted(
        stats['by_extension'].items(),
        key=lambda x: x[1]['count'],
        reverse=True
    )

    for ext, data in sorted_extensions:
        percentage = (data['count'] / stats['total_files'] * 100) if stats['total_files'] > 0 else 0
        print(f"{ext:<20} {data['count']:>8,} fichiers  {format_bytes(data['size']):>12}  ({percentage:.1f}%)")

    print('-' * 60)

    print(f"\n🏆 Plus gros fichier:")
    print(f"   {format_bytes(stats['largest_file']['size'])} - {stats['largest_file']['path']}")

    if stats['errors']:
        print(f"\n⚠️  {len(stats['errors'])} erreurs rencontrées:")
        for err in stats['errors'][:10]:
            print(f"   ❌ {err['path']}: {err['error']}")
        if len(stats['errors']) > 10:
            print(f"   ... et {len(stats['errors']) - 10} autres erreurs")

    print('\n✅ Analyse terminée!\n')


if __name__ == '__main__':
    main()