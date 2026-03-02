"""Wave 2 診断: IFRS 企業 (トヨタ S100VHHR) の中身を調査。

目的: detect_accounting_standard が standard=None を返す原因を特定する。
  - DEI の AccountingStandardsDEI の値
  - 全 namespace URI の一覧
  - jpigp_cor の有無
  - ZIP内の全ファイル名
"""

from __future__ import annotations

import os
import zipfile
from io import BytesIO

from edinet import configure
from edinet.api.download import download_document
from edinet.xbrl import extract_dei, parse_xbrl_facts
from edinet.xbrl._namespaces import classify_namespace

API_KEY = os.environ.get("EDINET_API_KEY", "your_api_key_here")
TAXONOMY_PATH = os.environ.get(
    "EDINET_TAXONOMY_ROOT", "/mnt/c/Users/nezow/Downloads/ALL_20251101"
)
configure(api_key=API_KEY, taxonomy_path=TAXONOMY_PATH)

DOC_ID = "S100VHHR"

print(f"=== Downloading {DOC_ID} ===")
zip_bytes = download_document(DOC_ID, file_type="1")

# 1. ZIP内ファイル一覧
print(f"\n=== ZIP contents ===")
with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
    for name in zf.namelist():
        print(f"  {name}")

# 2. XBRLファイルをパース
print(f"\n=== Parsing XBRL ===")
with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
    xbrl_files = [n for n in zf.namelist() if n.endswith(".xbrl") and "PublicDoc/" in n]
    print(f"  XBRL files found: {xbrl_files}")

    for xbrl_path in xbrl_files:
        print(f"\n  --- Parsing: {xbrl_path} ---")
        xbrl_bytes = zf.read(xbrl_path)
        parsed = parse_xbrl_facts(xbrl_bytes, source_path=xbrl_path)
        print(f"  Total facts: {len(parsed.facts)}")

        # 3. DEI
        dei = extract_dei(parsed.facts)
        print(f"\n  DEI:")
        print(f"    accounting_standards = {dei.accounting_standards!r}")
        print(f"    has_consolidated     = {dei.has_consolidated!r}")
        print(f"    period_type          = {dei.period_type!r}")
        print(f"    edinet_code          = {dei.edinet_code!r}")
        print(f"    filer_name           = {dei.filer_name!r}")
        print(f"    security_code        = {dei.security_code!r}")

        # 4. 全 namespace URI
        all_ns: dict[str, int] = {}
        for f in parsed.facts:
            ns = f.namespace_uri or "(None)"
            all_ns[ns] = all_ns.get(ns, 0) + 1

        print(f"\n  Namespace URI counts ({len(all_ns)} unique):")
        for ns in sorted(all_ns.keys()):
            info = classify_namespace(ns)
            mg = info.module_group if info.module_group else "-"
            print(f"    [{all_ns[ns]:>4}] {mg:<10} {ns[:100]}")

        # 5. jpigp を含む namespace を特に確認
        jpigp_ns = [ns for ns in all_ns if "jpigp" in ns]
        print(f"\n  jpigp-containing namespaces: {jpigp_ns}")

        # 6. jpdei facts の中身サンプル (AccountingStandards 関連)
        print(f"\n  DEI-related facts:")
        for f in parsed.facts:
            ns = f.namespace_uri or ""
            if "jpdei" in ns:
                print(f"    {f.local_name}: value={f.value!r}, nil={f.xsi_nil}")

print("\n=== Done ===")
