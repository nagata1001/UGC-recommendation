from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from append_cold_start_report import set_run_font


DOCX_PATH = ROOT / "社交场景多模态UGC搜索与推荐系统方案.docx"
REPORT_PATH = ROOT / "reports" / "hot_start_7d_simulation.json"
TMP_PATH = ROOT / "reports" / "_hot_start_metric_fix.tmp.docx"


def main() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    day_1, day_6, day_7 = report["daily_results"][0], report["daily_results"][5], report["daily_results"][6]
    corrected = (
        f"第1天的NDCG@5为{day_1['mean_ndcg_at_5']:.3f}，随后因候选冷却、探索流量和兴趣漂移而波动。"
        f"第6天降至{day_6['mean_ndcg_at_5']:.3f}，第7天恢复至{day_7['mean_ndcg_at_5']:.3f}。"
        "该变化说明动态画像和探索策略能够重新找到相关内容，但目前尚未与静态画像基线进行同条件对照，因此不能把波动解释为动态方案带来的净提升。"
    )
    doc = Document(DOCX_PATH)
    matches = [paragraph for paragraph in doc.paragraphs if paragraph.text.startswith("第1天的NDCG@5为")]
    if len(matches) != 1:
        raise RuntimeError(f"预期找到1个指标解释段，实际找到{len(matches)}个")
    paragraph = matches[0]
    for run in paragraph.runs:
        run.text = ""
    run = paragraph.runs[0] if paragraph.runs else paragraph.add_run()
    run.text = corrected
    set_run_font(run, size=11)
    doc.save(TMP_PATH)
    os.replace(TMP_PATH, DOCX_PATH)
    print(corrected)


if __name__ == "__main__":
    main()
