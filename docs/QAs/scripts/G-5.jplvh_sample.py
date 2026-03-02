"""G-5. 大量保有報告書サンプル XBRL の Dimension / 数値構造確認スクリプト

実行方法: uv run docs/QAs/scripts/G-5.jplvh_sample.py
前提: サンプルインスタンスが docs/仕様書/2026/ 配下に存在すること
出力: 保有割合の decimals/unitRef、Dimension 構造、数値 Fact の一覧
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

# サンプルインスタンスのパス
SAMPLE_DIR = Path(
    "docs/仕様書/2026/サンプルインスタンス/サンプルインスタンス"
    "/ダウンロードデータ/18_大量保有府令-大量保有報告書"
)


def find_xbrl_files(base: Path) -> list[Path]:
    """指定ディレクトリ以下の .xbrl ファイルを再帰検索する。

    Args:
        base: 検索起点のディレクトリ。

    Returns:
        見つかった .xbrl ファイルのパスリスト。
    """
    return sorted(base.rglob("*.xbrl"))


def analyze_xbrl(xbrl_path: Path) -> None:
    """XBRL ファイルを解析し、数値 Fact・Dimension 構造を表示する。

    Args:
        xbrl_path: 解析対象の .xbrl ファイルパス。
    """
    print(f"\n{'=' * 70}")
    print(f"ファイル: {xbrl_path.name}")
    print(f"{'=' * 70}")

    tree = ET.parse(xbrl_path)
    root = tree.getroot()

    # 名前空間マップ（手動で取得）
    ns_map: dict[str, str] = {}
    with open(xbrl_path, encoding="utf-8") as f:
        text = f.read()

    # xmlns:prefix="uri" パターンを抽出
    for m in re.finditer(r'xmlns:(\w+)="([^"]+)"', text):
        ns_map[m.group(1)] = m.group(2)

    print(f"\n--- 名前空間 ---")
    for prefix, uri in sorted(ns_map.items()):
        if any(k in prefix for k in ["jplvh", "jpdei", "xbrli", "xbrldi"]):
            print(f"  {prefix}: {uri}")

    # Context 解析
    print(f"\n--- Context 一覧 ---")
    contexts: dict[str, dict] = {}
    for ctx in root.iter("{http://www.xbrl.org/2003/instance}context"):
        ctx_id = ctx.get("id", "")
        # entity
        entity_el = ctx.find("{http://www.xbrl.org/2003/instance}entity")
        identifier = ""
        segments = []
        if entity_el is not None:
            id_el = entity_el.find("{http://www.xbrl.org/2003/instance}identifier")
            if id_el is not None:
                identifier = id_el.text or ""

            seg = entity_el.find("{http://www.xbrl.org/2003/instance}segment")
            if seg is not None:
                for member in seg:
                    dim = member.get("dimension", "")
                    val = member.text or ""
                    segments.append((dim, val))

        # period
        period_el = ctx.find("{http://www.xbrl.org/2003/instance}period")
        period_str = ""
        if period_el is not None:
            instant = period_el.find("{http://www.xbrl.org/2003/instance}instant")
            if instant is not None:
                period_str = f"instant:{instant.text}"
            else:
                start = period_el.find("{http://www.xbrl.org/2003/instance}startDate")
                end = period_el.find("{http://www.xbrl.org/2003/instance}endDate")
                if start is not None and end is not None:
                    period_str = f"duration:{start.text}~{end.text}"

        contexts[ctx_id] = {
            "identifier": identifier,
            "segments": segments,
            "period": period_str,
        }

        seg_str = ""
        if segments:
            seg_str = " | " + ", ".join(f"{d}={v}" for d, v in segments)
        print(f"  {ctx_id}: entity={identifier}, {period_str}{seg_str}")

    # Unit 解析
    print(f"\n--- Unit 一覧 ---")
    for unit in root.iter("{http://www.xbrl.org/2003/instance}unit"):
        unit_id = unit.get("id", "")
        measure = unit.find("{http://www.xbrl.org/2003/instance}measure")
        measure_text = measure.text if measure is not None else "N/A"
        print(f"  {unit_id}: {measure_text}")

    # 数値 Fact の抽出（jplvh_cor 名前空間）
    print(f"\n--- 数値 Fact (decimals 属性を持つ要素) ---")
    numeric_facts = []
    for el in root.iter():
        tag = el.tag
        decimals = el.get("decimals")
        if decimals is not None:
            # ローカル名を取得
            local_name = tag.split("}")[-1] if "}" in tag else tag
            ns_uri = tag.split("}")[0].lstrip("{") if "}" in tag else ""

            # 名前空間プレフィックスを逆引き
            prefix = ""
            for p, u in ns_map.items():
                if u == ns_uri:
                    prefix = p
                    break

            numeric_facts.append({
                "name": f"{prefix}:{local_name}" if prefix else local_name,
                "value": el.text or "",
                "decimals": decimals,
                "unitRef": el.get("unitRef", ""),
                "contextRef": el.get("contextRef", ""),
            })

    for fact in numeric_facts:
        ctx = contexts.get(fact["contextRef"], {})
        dim_info = ""
        if ctx.get("segments"):
            dim_info = " [DIM: " + ", ".join(
                f"{d.split(':')[-1]}={v.split(':')[-1]}"
                for d, v in ctx["segments"]
            ) + "]"
        print(
            f"  {fact['name']:60s} = {fact['value']:>15s}"
            f"  decimals={fact['decimals']:>4s}  unit={fact['unitRef']}"
            f"  ctx={fact['contextRef']}{dim_info}"
        )

    # 保有割合 (HoldingRatio) の詳細
    print(f"\n--- 保有割合 (HoldingRatio) の詳細 ---")
    holding_facts = [
        f for f in numeric_facts if "HoldingRatio" in f["name"]
    ]
    if holding_facts:
        for f in holding_facts:
            print(f"  要素名: {f['name']}")
            print(f"  値: {f['value']}")
            print(f"  decimals: {f['decimals']}")
            print(f"  unitRef: {f['unitRef']}")
            print(f"  contextRef: {f['contextRef']}")
            ctx = contexts.get(f["contextRef"], {})
            if ctx.get("segments"):
                print(f"  Dimension:")
                for dim, val in ctx["segments"]:
                    print(f"    {dim} = {val}")
            print()
    else:
        print("  (保有割合 Fact なし)")

    # Dimension を使用する Context の統計
    dim_contexts = [
        cid for cid, c in contexts.items() if c.get("segments")
    ]
    plain_contexts = [
        cid for cid, c in contexts.items() if not c.get("segments")
    ]
    print(f"\n--- Context 統計 ---")
    print(f"  Dimension あり: {len(dim_contexts)} 個")
    print(f"  Dimension なし: {len(plain_contexts)} 個")
    print(f"  数値 Fact 総数: {len(numeric_facts)} 個")


def main() -> None:
    """メイン処理。"""
    print("G-5: 大量保有報告書サンプル XBRL 解析")
    print("=" * 70)

    if not SAMPLE_DIR.exists():
        print(f"エラー: サンプルディレクトリが見つかりません: {SAMPLE_DIR}")
        return

    xbrl_files = find_xbrl_files(SAMPLE_DIR)
    print(f"検出された .xbrl ファイル: {len(xbrl_files)} 個")
    for p in xbrl_files:
        print(f"  {p.relative_to(SAMPLE_DIR)}")

    for xbrl_path in xbrl_files:
        analyze_xbrl(xbrl_path)

    # サマリー
    print(f"\n\n{'=' * 70}")
    print("サマリー")
    print(f"{'=' * 70}")
    print(f"  解析ファイル数: {len(xbrl_files)}")
    print("  検証ポイント:")
    print("    1. HoldingRatioOfShareCertificatesEtc の decimals/unitRef")
    print("    2. FilersLargeVolumeHoldersAndJointHoldersAxis の Dimension 構造")
    print("    3. 金額系要素の decimals/unitRef (JPY / decimals=-3)")


if __name__ == "__main__":
    main()
