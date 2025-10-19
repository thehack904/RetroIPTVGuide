#!/usr/bin/env bash
# ────────────────────────────────────────────────────────────────
# bump_version.sh — Version bump utility for RetroIPTVGuide
# Author: RetroIPTVGuide Dev Team
# License: CC BY-NC-SA 4.0
# Usage:
#   ./bump_version.sh 4.0.0
#   ./bump_version.sh 4.0.0 --commit
# ────────────────────────────────────────────────────────────────

set -euo pipefail
# macOS locale workaround for sed "illegal byte sequence"
export LC_CTYPE=C
export LANG=C

# --- Color setup ---
RED=$(tput setaf 1)
GREEN=$(tput setaf 2)
YELLOW=$(tput setaf 3)
RESET=$(tput sgr0)

# --- Argument parsing ---
NEW_VERSION="${1:-}"
DO_COMMIT="${2:-}"
TODAY=$(date +%Y-%m-%d)

if [[ -z "$NEW_VERSION" ]]; then
  echo "${YELLOW}Usage:${RESET} $0 <new_version> [--commit]"
  exit 1
fi

# Strip leading v
NEW_VERSION="${NEW_VERSION#v}"

# --- File targets ---
FILES=(
  "retroiptv_linux.sh"
  "retroiptv_rpi.sh"
  "retroiptv_windows.ps1"
  "app.py"
)

CHANGELOG="CHANGELOG.md"

# --- Detect sed flavor ---
if sed --version >/dev/null 2>&1; then
  # GNU sed
  SED_INPLACE=(-i)
else
  # BSD/macOS sed
  SED_INPLACE=(-i "")
fi

echo "🔢 Bumping version to v${NEW_VERSION}"
echo "───────────────────────────────────────────────"

# --- Update app.py ---
if [[ -f "app.py" ]]; then
  if grep -q '^APP_VERSION' app.py; then
    sed "${SED_INPLACE[@]}" "s/^APP_VERSION.*/APP_VERSION = \"v${NEW_VERSION}\"/" app.py
  else
    sed "${SED_INPLACE[@]}" "1iAPP_VERSION = \"v${NEW_VERSION}\"" app.py
  fi
  echo "${GREEN}✔ Updated app.py${RESET}"
fi

# --- Update version in scripts ---
for FILE in "${FILES[@]}"; do
  [[ ! -f "$FILE" ]] && continue

  case "$FILE" in
    *.sh)
      if grep -q '^VERSION=' "$FILE"; then
        sed "${SED_INPLACE[@]}" "s/^VERSION=.*/VERSION=\"${NEW_VERSION}\"/" "$FILE"
      else
        sed "${SED_INPLACE[@]}" "1iVERSION=\"${NEW_VERSION}\"" "$FILE"
      fi
      ;;
    *.ps1|*.bat)
      if grep -q 'VERSION' "$FILE"; then
        sed "${SED_INPLACE[@]}" "s/^[\$]*VERSION.*/\$VERSION = \"${NEW_VERSION}\"/" "$FILE"
      else
        sed "${SED_INPLACE[@]}" "1i\$VERSION = \"${NEW_VERSION}\"" "$FILE"
      fi
      ;;
  esac
  echo "${GREEN}✔ Updated ${FILE}${RESET}"
done

# --- Update CHANGELOG.md ---
if [[ -f "$CHANGELOG" ]]; then
  TMP_FILE=$(mktemp)
  awk -v ver="v${NEW_VERSION}" -v date="$TODAY" '
    /^---$/ && !inserted {
      print ""
      print "## " ver " - " date
      print "### Added"
      print "- (empty)\n"
      print "### Fixed"
      print "- (empty)\n"
      print "---\n"
      inserted=1
    }
    {print}
  ' "$CHANGELOG" > "$TMP_FILE"
  mv "$TMP_FILE" "$CHANGELOG"
  echo "${GREEN}✔ Updated CHANGELOG.md${RESET}"
fi

# --- Optional Git commit ---
if [[ "$DO_COMMIT" == "--commit" ]]; then
  git add app.py "$CHANGELOG" "${FILES[@]}" || true
  if git diff --cached --quiet; then
    echo "${YELLOW}⚠ No changes to commit.${RESET}"
  else
    git commit -m "Bump version to v${NEW_VERSION}" || true
    echo "${GREEN}✔ Git commit created${RESET}"
  fi
fi

echo "───────────────────────────────────────────────"
echo "${GREEN}🎉 Version bump complete → v${NEW_VERSION}${RESET}"

