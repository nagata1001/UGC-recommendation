from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_BREAK
from docx.shared import Pt


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from append_cold_start_report import add_body, add_bullet, add_heading, add_table, set_run_font


DOCX_PATH = ROOT / "社交场景多模态UGC搜索与推荐系统方案.docx"
REPORT_PATH = ROOT / "reports" / "user_post_simulation.json"
TMP_PATH = ROOT / "reports" / "_post_simulation_docx_update.tmp.docx"
MARKER = "16.10 用户发帖与创作标签背包更新实验"


def add_bold_label(doc: Document, text: str):
    paragraph = doc.add_paragraph()
    run = paragraph.add_run(text)
    set_run_font(run, size=11, bold=True)
    paragraph.paragraph_format.space_before = Pt(7)
    paragraph.paragraph_format.space_after = Pt(4)
    paragraph.paragraph_format.keep_with_next = True
    return paragraph


def main() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    doc = Document(DOCX_PATH)
    if any(MARKER in paragraph.text for paragraph in doc.paragraphs):
        raise SystemExit("方案已包含第16.10节，未重复写入")

    page_break = doc.add_paragraph()
    page_break.add_run().add_break(WD_BREAK.PAGE)
    add_heading(doc, MARKER, 2)
    add_body(
        doc,
        "本实验验证了用户发布图文UGC后，系统能否把内容标签增量写入创作标签背包。6名模拟用户各发布2条图文内容，共产生12个发布事件；12个事件全部成功处理，所有用户的创作画像状态由空白变为warming。消费标签背包保持不变，说明创作兴趣与消费兴趣实现了隔离更新。",
    )

    add_bold_label(doc, "实验配置")
    policy = report["update_policy"]
    add_table(
        doc,
        ["项目", "配置"],
        [
            ["实验日期", "2026年11月11日"],
            ["模拟用户", f"{report['users']}名"],
            ["模拟发帖", f"每名用户2条，共{report['posts']}条图文UGC"],
            ["成功事件", f"{report['applied_events']}条，成功率100%"],
            ["发布行为强度", f"{policy['publish_strength']:.2f}"],
            ["文本标签置信度", f"{policy['tag_confidence']:.2f}"],
            ["重复证据衰减", "同一标签第n次证据乘以0.7的n次方，其中n从0开始"],
            ["时间层权重", "长期吸收60%增量，短期和会话吸收100%增量"],
        ],
        [4.0, 11.8],
    )

    add_bold_label(doc, "逐用户更新结果")
    rows = []
    for user in report["users_after_update"]:
        tags = []
        for tag in user["creator_tag_bag"]:
            tags.append(
                f"{tag['name']}  长期{tag['long_term_weight']:.3f}  "
                f"短期{tag['short_term_weight']:.3f}  证据{tag['evidence_count']}次"
            )
        rows.append(
            [
                user["user_id"],
                str(user["published_post_count"]),
                user["creator_stage"],
                "；".join(tags),
            ]
        )
    add_table(
        doc,
        ["用户", "发帖数", "创作阶段", "更新后的创作标签"],
        rows,
        [2.4, 1.8, 2.5, 9.1],
    )

    add_bold_label(doc, "更新过程说明")
    add_body(
        doc,
        "每条帖子先通过文本关键词规则生成内容类别，当前标签置信度设为0.90。系统将发布强度、标签置信度和重复证据衰减相乘，得到本次标签增量。首次命中标签的增量为0.36；同一标签第二次命中时乘以0.7，因此增量降为0.252。长期创作兴趣只吸收60%的增量，短期和会话兴趣吸收完整增量。",
    )
    add_body(
        doc,
        "以user-003为例，两条美食帖子均命中“美食烹饪”。更新后该标签的长期权重为0.367，短期权重为0.611，证据次数为2。user-001和user-005的帖子同时覆盖两个类别，因此各自形成主标签和辅助标签。",
    )

    add_bold_label(doc, "工程验证结果")
    add_bullet(doc, "12条发帖事件全部成功应用，关联的12张图片均存在。")
    add_bullet(doc, "相同event_id再次处理时会被跳过，避免消息重放造成重复累计。")
    add_bullet(doc, "发帖仅更新creator_tag_bag，consumer_tag_bag保持原始3个注册兴趣标签。")
    add_bullet(doc, "相同标签的后续证据采用递减增量，避免短时间连续发帖使权重迅速达到上限。")
    add_bullet(doc, "项目自动测试增至17项，发帖更新、幂等性和重复证据衰减测试均通过。")

    add_bold_label(doc, "实验边界与下一步")
    add_body(
        doc,
        "本次标签来源是帖子文本关键词规则。图片参与模拟帖的数据结构和路径校验，但尚未通过Chinese CLIP与标签文本向量进行零样本分类。因此当前结果验证的是发帖事件到创作标签背包的更新链路，不代表多模态标签识别效果已经得到验证。下一步应融合文本规则、图片零样本标签、OCR文字和模型置信度，再评估标签准确率、覆盖率、冲突率和未知类别比例。",
    )

    TMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    doc.save(TMP_PATH)
    os.replace(TMP_PATH, DOCX_PATH)
    print(DOCX_PATH)


if __name__ == "__main__":
    main()
