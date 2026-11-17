#!/usr/bin/env bash
# bakeoff.sh: the Hinglish voice bake-off harness (SOS-N21A).
#
#   scripts/bakeoff.sh --fake --out DIR   the whole harness with fake providers, written to DIR
#   scripts/bakeoff.sh --live             the real providers; Jayman runs it, from a terminal
#   scripts/bakeoff.sh --templates        rewrite the shipped files in docs/bakeoff
#
# --live reads ~/iespl-baseline/bakeoff/audio/*.wav, reference.tsv and llm-models.txt, and the keys
# sellos_sarvam_key, sellos_deepgram_key, sellos_elevenlabs_key and sellos_anthropic_key from the
# macOS Keychain. It refuses to start when standard input is not a terminal, so the build loop's
# agent cannot run it. No key is printed or written.
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
case " $* " in
  *" --live "*)
    if [ ! -t 0 ]; then
      echo "bakeoff.sh --live runs only from a terminal you are sitting at. Standard input is not a terminal, so nothing was started." >&2
      exit 2
    fi
    ;;
esac
PYTHON="${SELLOS_BAKEOFF_PYTHON:-$HOME/iespl-bench/env/bin/python}"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"
cd "$REPO_DIR" || exit 3
exec "$PYTHON" -m sellos.voice.bakeoff "$@"
