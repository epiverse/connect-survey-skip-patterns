#!/usr/bin/env bash
# Faithful, reproducible plain-text extraction of a Connect questionnaire .docx.
#   tools/extract.sh <module_id> [--raw]     # numbered lines (default) -> cite these in provenance
#   tools/extract.sh --path "<file.docx>" [--raw]
#   tools/extract.sh --list
set -euo pipefail
QDIR="data/questionnaire"
IDS="baseline_m1 baseline_m2 baseline_m3 baseline_m4 bio_mouthwash bio_covid19 bio_clinical bio_menstrual bio_research_appt screening qol"
module_file() {
  case "$1" in
    baseline_m1)       echo "Baseline Survey - Module 1.docx" ;;
    baseline_m2)       echo "Baseline Survey - Module 2.docx" ;;
    baseline_m3)       echo "Baseline Survey - Module 3.docx" ;;
    baseline_m4)       echo "Baseline Survey - Module 4.docx" ;;
    bio_mouthwash)     echo "Biospecimens Survey - At Home Mouthwash.docx" ;;
    bio_covid19)       echo "Biospecimens Survey - COVID19.docx" ;;
    bio_clinical)      echo "Biospecimens Survey - Clinical Collection (Blood & Urine).docx" ;;
    bio_menstrual)     echo "Biospecimens Survey - Menstrual Cycle.docx" ;;
    bio_research_appt) echo "Biospecimens Survey - Research Appointment (Blood, Urine, Mouthwash).docx" ;;
    screening)         echo "Cancer Screening History.docx" ;;
    qol)               echo "Quality of Life.docx" ;;
    *) return 1 ;;
  esac
}
usage(){ echo "Usage: tools/extract.sh <module_id> [--raw] | --path <file.docx> [--raw] | --list" >&2;
         echo "module_ids: $IDS" >&2; }
[ $# -ge 1 ] || { usage; exit 2; }
raw=0; mid=""; path=""
while [ $# -gt 0 ]; do case "$1" in
  --raw) raw=1 ;; --list) printf '%s\n' $IDS; exit 0 ;;
  --path) shift; path="${1:-}" ;; -h|--help) usage; exit 0 ;; *) mid="$1" ;;
esac; shift; done
if [ -z "$path" ]; then
  [ -n "$mid" ] || { usage; exit 2; }
  f="$(module_file "$mid")" || { echo "Unknown module_id: $mid" >&2; usage; exit 2; }
  path="$QDIR/$f"
fi
[ -f "$path" ] || { echo "File not found: $path" >&2; exit 2; }
if [ "$raw" -eq 1 ]; then textutil -convert txt -stdout "$path"
else textutil -convert txt -stdout "$path" | cat -n; fi
