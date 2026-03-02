"""G-9. サンプルインスタンスのファイル名プレフィックスと G-9 マッピングのクロスチェック

実行方法: uv run docs/QAs/scripts/G-9.cross_check.py
前提: サンプルインスタンスが docs/仕様書/2026/ 配下に存在すること
出力: サンプルの実ファイル名プレフィックスと G-9 マッピング表の整合確認結果
"""

from __future__ import annotations

import re
from pathlib import Path

SAMPLE_ROOT = Path(
    "docs/仕様書/2026/サンプルインスタンス/サンプルインスタンス/ダウンロードデータ"
)

# G-9.a.md §2 のマッピング表を転記
# サンプルディレクトリ番号 → (ordinance_code, 期待タクソノミプレフィックス)
EXPECTED_MAP: dict[str, tuple[str, list[str]]] = {
    "01": ("010", ["jpcrp"]),                    # 開示府令-有価証券届出書
    "02": ("010", ["jpcrp"]),                    # 開示府令-有価証券報告書
    "03": ("010", ["jpcrp"]),                    # 開示府令-IFRS有価証券報告書
    "04": ("010", ["jpcrp"]),                    # 開示府令-半期報告書(銀行業)
    "05": ("010", ["jpcrp"]),                    # 開示府令-半期報告書(建設業)
    "06": ("010", ["jpcrp"]),                    # 開示府令-半期報告書(鉄道業)
    "07": ("010", ["jpcrp"]),                    # 開示府令-発行登録書
    "08": ("010", ["jpcrp"]),                    # 開示府令-発行登録追補書類
    "10": ("030", ["jpsps"]),                    # 特定有価証券府令-有価証券届出書
    "11": ("030", ["jpsps"]),                    # 特定有価証券府令-有価証券報告書
    "12": ("030", ["jpsps"]),                    # 特定有価証券府令-半期報告書
    "13": ("030", ["jpsps"]),                    # 特定有価証券府令-発行登録書
    "14": ("030", ["jpsps"]),                    # 特定有価証券府令-発行登録追補書類
    "16": ("050", ["jptoi"]),                    # 自社株買付府令-公開買付届出書
    "17": ("050", ["jptoi"]),                    # 自社株買付府令-公開買付報告書
    "18": ("060", ["jplvh"]),                    # 大量保有府令-大量保有報告書
    "20": ("010", ["jpcrp"]),                    # 開示府令-訂正有価証券報告書
    "21": ("030", ["jpsps"]),                    # 特定有価証券府令-訂正有価証券届出書
    "22": ("030", ["jpsps"]),                    # 特定有価証券府令-訂正有価証券報告書
}


def extract_taxonomy_prefix(filename: str) -> str | None:
    """ファイル名からタクソノミプレフィックスを抽出する。

    例: "jpcrp030000-asr-001_X99001-000_..." → "jpcrp"
        "jpsps040000-srs-001_Y99009-000_..." → "jpsps"
        "jpaud-aar-cn-001_..." → "jpaud"

    Args:
        filename: XBRLファイル名。

    Returns:
        タクソノミプレフィックス。抽出できなければ None。
    """
    m = re.match(r"^([a-z]+-?[a-z]*)", filename)
    if m:
        raw = m.group(1)
        # "jpcrp030000" → "jpcrp", "jpsps040000" → "jpsps" のように数字前で切る
        m2 = re.match(r"^([a-z]+(?:-[a-z]+)?)", raw)
        return m2.group(1) if m2 else raw
    return None


def main() -> None:
    """メイン処理。"""
    print("G-9: サンプルインスタンス ↔ マッピング表 クロスチェック")
    print("=" * 70)

    if not SAMPLE_ROOT.exists():
        print(f"エラー: サンプルディレクトリが見つかりません: {SAMPLE_ROOT}")
        return

    # サンプルディレクトリ一覧
    sample_dirs = sorted(
        d for d in SAMPLE_ROOT.iterdir()
        if d.is_dir()
    )

    print(f"サンプルディレクトリ数: {len(sample_dirs)}")

    ok_count = 0
    mismatch_count = 0
    skip_count = 0

    print(f"\n{'No':>3s}  {'ディレクトリ':40s}  {'実プレフィックス':18s}  "
          f"{'期待値':12s}  {'結果':8s}")
    print("-" * 100)

    for d in sample_dirs:
        dir_name = d.name
        # ディレクトリ番号を抽出 (例: "01_開示府令-有価証券届出書" → "01")
        dir_num = dir_name.split("_")[0]

        # PublicDoc 内の .xbrl を取得（AuditDoc の jpaud は除外）
        public_xbrls = sorted(d.rglob("PublicDoc/*.xbrl"))

        if not public_xbrls:
            print(f"{dir_num:>3s}  {dir_name:40s}  {'(xbrl なし)':18s}  "
                  f"{'':12s}  {'SKIP':8s}")
            skip_count += 1
            continue

        # 最初のファイルからプレフィックスを抽出
        first_file = public_xbrls[0].name
        actual_prefix = extract_taxonomy_prefix(first_file)

        # 期待値
        expected = EXPECTED_MAP.get(dir_num)
        if expected is None:
            print(f"{dir_num:>3s}  {dir_name:40s}  {str(actual_prefix):18s}  "
                  f"{'(未定義)':12s}  {'SKIP':8s}")
            skip_count += 1
            continue

        _, expected_prefixes = expected
        match = actual_prefix in expected_prefixes

        result = "OK" if match else "MISMATCH"
        if match:
            ok_count += 1
        else:
            mismatch_count += 1

        print(f"{dir_num:>3s}  {dir_name:40s}  {str(actual_prefix):18s}  "
              f"{','.join(expected_prefixes):12s}  {result:8s}")

        # MISMATCH の場合はファイル名も表示
        if not match:
            for xf in public_xbrls[:3]:
                print(f"     → {xf.name}")

    # AuditDoc の jpaud も確認
    print(f"\n\n--- AuditDoc (jpaud) の確認 ---")
    audit_prefixes: set[str] = set()
    for d in sample_dirs:
        audit_xbrls = sorted(d.rglob("AuditDoc/*.xbrl"))
        for xf in audit_xbrls:
            prefix = extract_taxonomy_prefix(xf.name)
            if prefix:
                audit_prefixes.add(prefix)

    print(f"  AuditDoc のプレフィックス: {sorted(audit_prefixes)}")
    print(f"  → jpaud は G-9 マッピング表の対象外（監査報告書タクソノミ）")

    # サマリー
    print(f"\n\n{'=' * 70}")
    print("サマリー")
    print(f"{'=' * 70}")
    print(f"  一致 (OK): {ok_count}")
    print(f"  不一致 (MISMATCH): {mismatch_count}")
    print(f"  スキップ: {skip_count}")

    if mismatch_count == 0:
        print(f"\n  → 全サンプルインスタンスが G-9 マッピング表と整合。")
    else:
        print(f"\n  → {mismatch_count} 件の不整合を検出。G-9.a.md の更新が必要。")


if __name__ == "__main__":
    main()
