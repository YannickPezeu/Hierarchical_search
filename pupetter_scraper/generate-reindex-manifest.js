#!/usr/bin/env node
// generate-reindex-manifest.js
//
// Compare les métadonnées entre l'ancien et le nouveau scrape.
// Produit un fichier reindex_manifest.json qui indique pour chaque page
// si elle doit être réindexée ou pas.
//
// Usage: node generate-reindex-manifest.js <old_dir> <new_dir> <output_file>

const fs = require('fs-extra');
const path = require('path');

const [oldDir, newDir, outputFile] = process.argv.slice(2);

if (!oldDir || !newDir || !outputFile) {
  console.error('Usage: node generate-reindex-manifest.js <old_dir> <new_dir> <output_file>');
  process.exit(1);
}

// Recursively find all metadata.json files in a directory
function findMetadataFiles(dir) {
  const results = new Map(); // url → { contentHash, folderPath }

  if (!fs.existsSync(dir)) {
    return results;
  }

  function walk(currentDir) {
    try {
      const entries = fs.readdirSync(currentDir, { withFileTypes: true });
      for (const entry of entries) {
        const fullPath = path.join(currentDir, entry.name);
        if (entry.isDirectory()) {
          walk(fullPath);
        } else if (entry.name === 'metadata.json') {
          try {
            const metadata = fs.readJSONSync(fullPath);
            if (metadata.url) {
              results.set(metadata.url, {
                contentHash: metadata.contentHash || null,
                folderPath: path.relative(dir, currentDir),
                title: metadata.title || null,
                downloadedDocuments: (metadata.downloadedDocuments || []).length
              });
            }
          } catch (e) {
            console.error(`  ⚠️  Error reading ${fullPath}: ${e.message}`);
          }
        }
      }
    } catch (e) {
      console.error(`  ⚠️  Error walking ${currentDir}: ${e.message}`);
    }
  }

  walk(dir);
  return results;
}

// ── Main ──────────────────────────────────────────────────────────
console.log('==============================================');
console.log('  Generating reindex manifest');
console.log('==============================================');
console.log(`  Old: ${oldDir}`);
console.log(`  New: ${newDir}`);
console.log(`  Out: ${outputFile}`);
console.log('');

const oldPages = findMetadataFiles(oldDir);
const newPages = findMetadataFiles(newDir);

console.log(`  📄 Old scrape: ${oldPages.size} pages`);
console.log(`  📄 New scrape: ${newPages.size} pages`);

const manifest = {
  generatedAt: new Date().toISOString(),
  summary: { added: 0, changed: 0, unchanged: 0, removed: 0 },
  pages: []
};

// Check all pages in the new scrape
for (const [url, newMeta] of newPages) {
  const oldMeta = oldPages.get(url);

  if (!oldMeta) {
    // Page didn't exist before
    manifest.pages.push({
      url,
      status: 'added',
      reindex: true,
      folderPath: newMeta.folderPath,
      title: newMeta.title
    });
    manifest.summary.added++;
  } else if (!newMeta.contentHash || !oldMeta.contentHash) {
    // No hash available — assume changed (safe default)
    manifest.pages.push({
      url,
      status: 'changed',
      reason: 'no_hash_available',
      reindex: true,
      folderPath: newMeta.folderPath,
      title: newMeta.title
    });
    manifest.summary.changed++;
  } else if (newMeta.contentHash !== oldMeta.contentHash) {
    // Content changed
    manifest.pages.push({
      url,
      status: 'changed',
      reindex: true,
      folderPath: newMeta.folderPath,
      title: newMeta.title,
      oldHash: oldMeta.contentHash.substring(0, 12),
      newHash: newMeta.contentHash.substring(0, 12)
    });
    manifest.summary.changed++;
  } else {
    // Identical
    manifest.pages.push({
      url,
      status: 'unchanged',
      reindex: false,
      folderPath: newMeta.folderPath,
      title: newMeta.title
    });
    manifest.summary.unchanged++;
  }
}

// Check for removed pages (in old but not in new)
for (const [url, oldMeta] of oldPages) {
  if (!newPages.has(url)) {
    manifest.pages.push({
      url,
      status: 'removed',
      reindex: false,
      folderPath: oldMeta.folderPath,
      title: oldMeta.title
    });
    manifest.summary.removed++;
  }
}

// Write manifest
fs.writeJSONSync(outputFile, manifest, { spaces: 2 });

const toReindex = manifest.pages.filter(p => p.reindex).length;

console.log('');
console.log('  📊 Results:');
console.log(`     ✚ Added:     ${manifest.summary.added}`);
console.log(`     ✎ Changed:   ${manifest.summary.changed}`);
console.log(`     ═ Unchanged: ${manifest.summary.unchanged}`);
console.log(`     ✗ Removed:   ${manifest.summary.removed}`);
console.log(`     → To reindex: ${toReindex} / ${newPages.size}`);
console.log('');
console.log(`  ✓ Manifest written to ${outputFile}`);
console.log('==============================================');
