"""パフォーマンスベンチマーク: リファクタリング前後の比較用。

各問題箇所を個別に N 回繰り返し実行し、所要時間を計測する。
結果は JSON ファイルに出力して前後比較に使う。
"""

from __future__ import annotations

import io
import json
import sys
import time
import zipfile
from pathlib import Path

# プロジェクトルートをパスに追加
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

FIXTURES = PROJECT_ROOT / "tests" / "fixtures"
TAXONOMY_MINI = FIXTURES / "taxonomy_mini"
XBRL_FILE = FIXTURES / "xbrl_fragments" / "simple_pl.xbrl"
OUTPUT_FILE = PROJECT_ROOT / "tools" / "perf_benchmark_result.json"

# テスト用 ZIP を動的に構築
def _build_test_zip() -> bytes:
    """テスト用の小さな ZIP を作成する。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("XBRL/PublicDoc/test.xbrl", XBRL_FILE.read_bytes())
        zf.writestr("XBRL/PublicDoc/test_lab.xml",
                     (FIXTURES / "taxonomy_mini" / "filer" / "filer_lab.xml").read_bytes())
        zf.writestr("XBRL/PublicDoc/test_lab-en.xml",
                     (FIXTURES / "taxonomy_mini" / "filer" / "filer_lab-en.xml").read_bytes())
        zf.writestr("XBRL/PublicDoc/test.xsd",
                     (FIXTURES / "taxonomy_mini" / "filer" / "filer.xsd").read_bytes())
    return buf.getvalue()


def bench(name: str, fn, n: int) -> dict:
    """fn を n 回実行して計測。"""
    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    total = sum(times)
    avg = total / n
    return {
        "name": name,
        "n": n,
        "total_sec": round(total, 6),
        "avg_sec": round(avg, 6),
        "min_sec": round(min(times), 6),
        "max_sec": round(max(times), 6),
    }


def main():
    results: list[dict] = []
    N = 100  # 繰り返し回数

    # ---------------------------------------------------------------
    # 1. TaxonomyResolver 繰り返し生成
    # ---------------------------------------------------------------
    from edinet.xbrl.taxonomy import TaxonomyResolver, get_taxonomy_resolver, _resolver_cache

    # 標準タクソノミが存在する場合のみ測定
    taxonomy_root_path = Path("/mnt/c/Users/nezow/Downloads/ALL_20251101")
    if taxonomy_root_path.exists():
        # ウォームアップ（pickle 生成）
        TaxonomyResolver(taxonomy_root_path)
        r = bench(
            "1_TaxonomyResolver_create",
            lambda: TaxonomyResolver(taxonomy_root_path),
            N,
        )
        results.append(r)
        print(f"  {r['name']}: avg={r['avg_sec']:.4f}s, total={r['total_sec']:.4f}s (x{N})")

        # シングルトンキャッシュ経由
        _resolver_cache.clear()
        get_taxonomy_resolver(taxonomy_root_path)  # ウォームアップ
        r = bench(
            "1b_get_taxonomy_resolver_cached",
            lambda: get_taxonomy_resolver(taxonomy_root_path),
            N,
        )
        results.append(r)
        print(f"  {r['name']}: avg={r['avg_sec']:.6f}s, total={r['total_sec']:.4f}s (x{N})")
    else:
        print("  [SKIP] 1_TaxonomyResolver_create: 標準タクソノミ未検出")
        # ミニタクソノミで代替
        TaxonomyResolver(TAXONOMY_MINI, use_cache=False)
        r = bench(
            "1_TaxonomyResolver_create_mini",
            lambda: TaxonomyResolver(TAXONOMY_MINI, use_cache=False),
            N,
        )
        results.append(r)
        print(f"  {r['name']}: avg={r['avg_sec']:.4f}s, total={r['total_sec']:.4f}s (x{N})")

    # ---------------------------------------------------------------
    # 2. ZIP 再オープン (list_zip_members + extract_zip_member × 4)
    # ---------------------------------------------------------------
    from edinet.api.download import extract_zip_member, list_zip_members

    zip_bytes = _build_test_zip()
    members = list_zip_members(zip_bytes)

    def zip_multi_open():
        list_zip_members(zip_bytes)
        for m in members:
            extract_zip_member(zip_bytes, m)

    r = bench("3_zip_multi_open", zip_multi_open, N)
    results.append(r)
    print(f"  {r['name']}: avg={r['avg_sec']:.4f}s, total={r['total_sec']:.4f}s (x{N})")

    # ---------------------------------------------------------------
    # 3. _extract_filer_taxonomy_files
    # ---------------------------------------------------------------
    from edinet.models.filing import _extract_filer_taxonomy_files

    r = bench(
        "3b_extract_filer_taxonomy_files",
        lambda: _extract_filer_taxonomy_files(zip_bytes),
        N,
    )
    results.append(r)
    print(f"  {r['name']}: avg={r['avg_sec']:.4f}s, total={r['total_sec']:.4f}s (x{N})")

    # ---------------------------------------------------------------
    # 4. derive_concept_sets 繰り返し
    # ---------------------------------------------------------------
    if taxonomy_root_path.exists():
        from edinet.xbrl.taxonomy.concept_sets import derive_concept_sets

        # ウォームアップ
        derive_concept_sets(taxonomy_root_path)
        r = bench(
            "4_derive_concept_sets",
            lambda: derive_concept_sets(taxonomy_root_path),
            N,
        )
        results.append(r)
        print(f"  {r['name']}: avg={r['avg_sec']:.4f}s, total={r['total_sec']:.4f}s (x{N})")
    else:
        print("  [SKIP] 4_derive_concept_sets: 標準タクソノミ未検出")

    # ---------------------------------------------------------------
    # 5. parse_xbrl_facts (deepcopy 含む)
    # ---------------------------------------------------------------
    from edinet.xbrl.parser import parse_xbrl_facts

    xbrl_bytes = XBRL_FILE.read_bytes()

    r = bench(
        "5_parse_xbrl_facts",
        lambda: parse_xbrl_facts(xbrl_bytes, source_path="bench"),
        N,
    )
    results.append(r)
    print(f"  {r['name']}: avg={r['avg_sec']:.4f}s, total={r['total_sec']:.4f}s (x{N})")

    # ---------------------------------------------------------------
    # 6. classify_namespace with cache thrashing
    # ---------------------------------------------------------------
    from edinet.xbrl._namespaces import classify_namespace

    # キャッシュをクリアしてから測定
    classify_namespace.cache_clear()
    # 500 ユニーク URI を生成 (maxsize=256 を超える)
    uris = [
        f"http://disclosure.edinet-fsa.go.jp/jpcrp030000/asr/001/E{i:05d}-000/2025-03-31/01/2025-06-30/CasualCo"
        for i in range(500)
    ]

    def classify_many():
        for u in uris:
            classify_namespace(u)

    r = bench("6_classify_namespace_500uris", classify_many, 10)
    results.append(r)
    print(f"  {r['name']}: avg={r['avg_sec']:.4f}s, total={r['total_sec']:.4f}s (x10)")

    # ---------------------------------------------------------------
    # 7. _select_filer_xsd (re.compile in function scope)
    # ---------------------------------------------------------------
    from edinet.models.filing import _select_filer_xsd

    candidates = [
        "XBRL/PublicDoc/audit_lab.xsd",
        "XBRL/PublicDoc/jpcrp030000-asr-001_E02144-000_2025-03-31_01_2025-06-30.xsd",
        "XBRL/PublicDoc/other.xsd",
    ]

    r = bench(
        "7_select_filer_xsd",
        lambda: _select_filer_xsd(candidates),
        N * 10,
    )
    results.append(r)
    print(f"  {r['name']}: avg={r['avg_sec']:.6f}s, total={r['total_sec']:.4f}s (x{N*10})")

    # ---------------------------------------------------------------
    # 出力
    # ---------------------------------------------------------------
    with OUTPUT_FILE.open("w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n結果を {OUTPUT_FILE} に保存しました。")


if __name__ == "__main__":
    main()
