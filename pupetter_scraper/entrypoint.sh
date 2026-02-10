#!/bin/bash
set -e

# ── Configuration ────────────────────────────────────────────────
LIBRARY_NAME="${LIBRARY_NAME:-large_campus2}"
BASE_DIR="/app/all_indexes"
LIVE_DIR="${BASE_DIR}/${LIBRARY_NAME}"
NEW_DIR="${BASE_DIR}/${LIBRARY_NAME}_new"
OLD_DIR="${BASE_DIR}/${LIBRARY_NAME}_old"

echo "============================================="
echo "  EPFL Scraper — Fresh Dump + Swap"
echo "============================================="
echo "  LIVE : ${LIVE_DIR}"
echo "  NEW  : ${NEW_DIR}"
echo "  OLD  : ${OLD_DIR}"
echo "============================================="

# ── Cleanup any leftover partial run ─────────────────────────────
if [ -d "${NEW_DIR}" ]; then
    echo "⚠️  Found leftover ${NEW_DIR} from a previous failed run."
    echo "   Checking for crawler state to resume..."
    if [ -f "${NEW_DIR}/source_files/crawler_state.json" ]; then
        echo "   ✓ State file found — resuming previous scrape."
    else
        echo "   ✗ No state file — cleaning up and starting fresh."
        rm -rf "${NEW_DIR}"
    fi
fi

# ── Run the scraper into the _new directory ──────────────────────
echo ""
echo "🚀 Starting scraper into ${LIBRARY_NAME}_new ..."
node epfl-hierarchical-scraper.js "${LIBRARY_NAME}_new" "$@"

# ── Verify the scrape produced data ─────────────────────────────
FILE_COUNT=$(find "${NEW_DIR}" -type f | wc -l)
echo ""
echo "📊 Scrape complete: ${FILE_COUNT} files in new directory."

if [ "${FILE_COUNT}" -lt 10 ]; then
    echo "❌ Too few files (${FILE_COUNT}). Scrape likely failed. Keeping old data."
    exit 1
fi

# ── Generate reindex manifest ────────────────────────────────────
echo ""
if [ -d "${LIVE_DIR}" ]; then
    echo "📋 Comparing old and new scrape to generate reindex manifest..."
    node generate-reindex-manifest.js \
        "${LIVE_DIR}/source_files" \
        "${NEW_DIR}/source_files" \
        "${NEW_DIR}/reindex_manifest.json"
else
    echo "📋 No previous scrape found — all pages will be marked for indexing."
    # Generate manifest with everything as "added"
    node generate-reindex-manifest.js \
        "/tmp/empty_dir" \
        "${NEW_DIR}/source_files" \
        "${NEW_DIR}/reindex_manifest.json"
fi

# ── Atomic swap ──────────────────────────────────────────────────
echo ""
echo "🔄 Swapping directories..."

# Remove previous old backup if it exists
if [ -d "${OLD_DIR}" ]; then
    echo "   Removing previous backup ${OLD_DIR}..."
    rm -rf "${OLD_DIR}"
fi

# Move current live → old (if it exists)
if [ -d "${LIVE_DIR}" ]; then
    echo "   ${LIBRARY_NAME} → ${LIBRARY_NAME}_old"
    mv "${LIVE_DIR}" "${OLD_DIR}"
fi

# Move new → live
echo "   ${LIBRARY_NAME}_new → ${LIBRARY_NAME}"
mv "${NEW_DIR}" "${LIVE_DIR}"

# Delete old
if [ -d "${OLD_DIR}" ]; then
    echo "   Deleting ${LIBRARY_NAME}_old..."
    rm -rf "${OLD_DIR}"
fi

echo ""
echo "✅ Swap complete. Live data is now fresh."
echo "   Files: $(find "${LIVE_DIR}" -type f | wc -l)"
echo "   Manifest: ${LIVE_DIR}/reindex_manifest.json"
echo "============================================="