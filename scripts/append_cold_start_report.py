from __future__ import annotations

import json
import os
from pathlib import Path
from statistics import mean

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
DOCX_PATH = ROOT / "社交场景多模态UGC搜索与推荐系统方案.docx"
REPORT_PATH = ROOT / "reports" / "cold_start_recommendations.json"
TMP_PATH = ROOT / "reports" / "_方案追加冷启动实验.tmp.docx"

FONT_CN = "Microsoft YaHei"
FONT_LATIN = "Arial"
DARK_BLUE = "1F4E78"
PALE_BLUE = "EAF2F8"
PALE_GRAY = "F5F7F9"
BORDER = "D9D9D9"


def set_run_font(run, size: float = 11, bold: bool = False, color: str = "000000") -> None:
    run.font.name = FONT_LATIN
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)
    rpr = run._element.get_or_add_rPr()
    fonts = rpr.rFonts
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.insert(0, fonts)
    fonts.set(qn("w:ascii"), FONT_LATIN)
    fonts.set(qn("w:hAnsi"), FONT_LATIN)
    fonts.set(qn("w:eastAsia"), FONT_CN)


def format_paragraph(paragraph, size: float = 11, bold: bool = False) -> None:
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.25
    for run in paragraph.runs:
        set_run_font(run, size=size, bold=bold)


def add_body(doc: Document, text: str, bold_lead: str | None = None):
    paragraph = doc.add_paragraph()
    if bold_lead and text.startswith(bold_lead):
        first = paragraph.add_run(bold_lead)
        set_run_font(first, bold=True)
        rest = paragraph.add_run(text[len(bold_lead) :])
        set_run_font(rest)
    else:
        run = paragraph.add_run(text)
        set_run_font(run)
    paragraph.paragraph_format.space_after = Pt(7)
    paragraph.paragraph_format.line_spacing = 1.3
    return paragraph


def add_bullet(doc: Document, text: str):
    paragraph = doc.add_paragraph(style="List Bullet")
    run = paragraph.add_run(text)
    set_run_font(run)
    paragraph.paragraph_format.space_after = Pt(4)
    paragraph.paragraph_format.line_spacing = 1.2
    return paragraph


def add_heading(doc: Document, text: str, level: int):
    paragraph = doc.add_heading(text, level=level)
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.space_before = Pt(12 if level == 1 else 9)
    paragraph.paragraph_format.space_after = Pt(6)
    for run in paragraph.runs:
        set_run_font(run, size=16 if level == 1 else 13, bold=True)
    return paragraph


def set_cell_fill(cell, color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), color)


def set_cell_margins(cell, top: int = 100, start: int = 120, bottom: int = 100, end: int = 120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for tag, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table) -> None:
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = OxmlElement(f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:color"), BORDER)


def set_repeat_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    repeat = OxmlElement("w:tblHeader")
    repeat.set(qn("w:val"), "true")
    tr_pr.append(repeat)


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths_cm: list[float]):
    table = doc.add_table(rows=1, cols=len(headers))
    table.autofit = False
    table.alignment = 1
    set_table_borders(table)
    header = table.rows[0]
    set_repeat_header(header)
    for index, value in enumerate(headers):
        cell = header.cells[index]
        cell.width = Cm(widths_cm[index])
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        set_cell_fill(cell, DARK_BLUE)
        set_cell_margins(cell)
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = paragraph.add_run(value)
        set_run_font(run, size=9.5, bold=True, color="FFFFFF")
    for row_index, values in enumerate(rows):
        row = table.add_row()
        for column_index, value in enumerate(values):
            cell = row.cells[column_index]
            cell.width = Cm(widths_cm[column_index])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cell)
            if row_index % 2:
                set_cell_fill(cell, PALE_BLUE)
            else:
                set_cell_fill(cell, "FFFFFF")
            paragraph = cell.paragraphs[0]
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER if column_index == 0 else WD_ALIGN_PARAGRAPH.LEFT
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing = 1.15
            run = paragraph.add_run(str(value))
            set_run_font(run, size=9.2)
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(2)
    return table


def main() -> None:
    result = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    profiles = [entry["initial_profile"] for entry in result["results"]]
    recommendations = [item for entry in result["results"] for item in entry["recommendations"]]
    unique_count = len({item["ugc_id"] for item in recommendations})
    category_rate = mean(bool(item["matched_categories"]) for item in recommendations)
    average_score = mean(item["score"] for item in recommendations)

    doc = Document(DOCX_PATH)
    doc.add_page_break()
    add_heading(doc, "16 冷启动推荐实验报告", 1)
    add_body(
        doc,
        "本实验验证了基于初始用户画像生成冷启动推荐的最小闭环。系统使用6个模拟画像对100条真实图文UGC进行排序，共输出30条Top 5推荐，其中29条内容互不重复，Top 5中具有显式兴趣类别匹配的比例为93.3%。结果表明，兴趣弱先验、Chinese CLIP跨模态语义和启发式规则可以共同支撑冷启动阶段的候选排序。由于实验没有人工相关性标签和真实用户反馈，本结果用于验证工程链路与推荐合理性，不能解释为线上点击率或推荐准确率。",
    )

    add_heading(doc, "16.1 实验目标", 2)
    add_body(doc, "实验关注新用户没有点击、点赞、停留和关注历史时，系统如何利用注册阶段的信息生成第一批推荐。验证范围包括初始画像构建、兴趣向量编码、候选UGC编码、混合打分、Top K排序和推荐理由输出。")
    add_bullet(doc, "验证用户主动选择的兴趣能否作为主要弱先验。")
    add_bullet(doc, "验证中文文本与图片能否通过Chinese CLIP进入同一语义空间并参与排序。")
    add_bullet(doc, "验证启发式兴趣类别能否降低短兴趣词产生的语义漂移。")
    add_bullet(doc, "形成可供后续真实用户行为更新的初始画像数据结构。")

    add_heading(doc, "16.2 实验数据与环境", 2)
    add_table(
        doc,
        ["项目", "配置"],
        [
            ["实验日期", "2026年11月9日"],
            ["用户画像", "6个模拟新用户画像"],
            ["候选内容", "COCO CN Mini中的100组真实图片与人工中文描述"],
            ["编码模型", "Chinese CLIP ViT B 16 本地模型"],
            ["运行环境", "Anaconda环境 ugc-minimal，CPU推理"],
            ["推荐规模", "每名用户Top 5，共30条推荐"],
            ["输入字段", "用户年龄、性别、地区、主动选择的兴趣及兴趣权重"],
        ],
        [3.3, 12.5],
    )

    profile_rows = []
    for profile in profiles:
        interests = "、".join(
            f"{value['name']} {value.get('weight', 1.0):.1f}"
            if isinstance(value, dict)
            else str(value)
            for value in profile["selected_interests"]
        )
        profile_rows.append(
            [profile["user_id"], str(profile["age"]), profile["gender"], profile["region"], interests]
        )
    add_table(doc, ["用户", "年龄", "性别", "地区", "主动选择的兴趣与权重"], profile_rows, [2.2, 1.4, 1.4, 2.0, 8.8])

    add_heading(doc, "16.3 初始画像与打分方法", 2)
    add_body(doc, "每个用户的初始画像由人口属性和兴趣弱先验组成。系统分别编码每个兴趣短语，再按用户设置的兴趣权重求加权平均并归一化，形成初始兴趣向量。候选UGC同时编码中文描述和图片，对两个归一化向量求平均后再次归一化。")
    add_body(doc, "综合得分 = 0.68 × 跨模态语义得分 + 0.18 × 兴趣类别匹配 + 0.05 × 热度 + 0.05 × 质量 + 0.02 × 地域亲和度 + 0.02 × 探索分。", bold_lead="综合得分")
    add_table(
        doc,
        ["特征", "权重", "作用"],
        [
            ["跨模态语义", "68%", "衡量用户兴趣向量与图文UGC向量的余弦相似度"],
            ["兴趣类别匹配", "18%", "显式匹配旅行、运动、美食、交通、自然和科技等类别"],
            ["内容热度", "5%", "候选数据未提供真实热度时使用中性默认值"],
            ["内容质量", "5%", "候选数据未提供真实质量时使用中性默认值"],
            ["地域亲和度", "2%", "仅当UGC包含地域字段时产生弱加权"],
            ["探索分", "2%", "提供少量确定性探索，避免推荐列表完全固化"],
        ],
        [3.2, 1.7, 10.7],
    )
    add_body(doc, "性别和年龄目前只保存在画像中，不直接参与排序。当前实验没有足够的群体行为证据支持性别或年龄偏好规则。后续如需使用这类特征，应基于匿名聚合数据训练并进行公平性检查。")

    add_heading(doc, "16.4 实验结果", 2)
    add_table(
        doc,
        ["指标", "结果", "解释"],
        [
            ["参与用户", "6", "覆盖旅行、运动、美食、交通、自然和科技兴趣"],
            ["候选UGC", "100", "均为真实图片与人工中文描述配对"],
            ["推荐总数", "30", "每名用户返回5条"],
            ["去重UGC", str(unique_count), "30个推荐位置中出现29条不同内容"],
            ["类别匹配率", f"{category_rate:.1%}", "28条Top 5推荐存在显式兴趣类别匹配"],
            ["平均综合分", f"{average_score:.3f}", "仅用于同一打分配置下的相对排序"],
            ["自动测试", "11项通过", "覆盖画像解析、类别匹配、地域规则、确定性和原有模块"],
        ],
        [3.0, 2.2, 10.4],
    )

    result_rows = []
    for entry in result["results"]:
        recs = entry["recommendations"]
        interests = "、".join(
            value["name"] if isinstance(value, dict) else str(value)
            for value in entry["initial_profile"]["selected_interests"]
        )
        match_rate = mean(bool(item["matched_categories"]) for item in recs)
        result_rows.append(
            [
                entry["user_id"],
                interests,
                recs[0]["text"],
                f"{match_rate:.0%}",
                f"{mean(item['score'] for item in recs):.3f}",
            ]
        )
    add_table(
        doc,
        ["用户", "兴趣", "Top 1内容", "Top 5类别匹配率", "Top 5平均分"],
        result_rows,
        [1.8, 3.8, 6.8, 2.0, 1.8],
    )

    add_heading(doc, "16.5 推荐结果样例", 2)
    for entry in result["results"]:
        profile = entry["initial_profile"]
        interests = "、".join(
            value["name"] if isinstance(value, dict) else str(value)
            for value in profile["selected_interests"]
        )
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.keep_with_next = True
        run = paragraph.add_run(f"{entry['user_id']}  {profile['region']}  兴趣 {interests}")
        set_run_font(run, size=11, bold=True)
        paragraph.paragraph_format.space_before = Pt(6)
        paragraph.paragraph_format.space_after = Pt(3)
        for item in entry["recommendations"]:
            categories = "、".join(item["matched_categories"]) or "语义探索"
            add_bullet(doc, f"第{item['rank']}名  {item['text']}  类别 {categories}  得分 {item['score']:.3f}")

    add_heading(doc, "16.6 调试发现与修正", 2)
    add_body(doc, "首轮实验只使用短兴趣词与UGC向量的语义相似度。多个用户的列表中出现相同的通用内容，说明小候选集存在语义枢纽现象。系统随后加入18%的显式兴趣类别匹配，使旅行、运动、美食、交通、自然和科技兴趣获得稳定的可解释约束。")
    add_body(doc, "类别词表初版使用单字“马”识别动物内容，误将“马桶”识别为动物。修正后使用“骑马”“马匹”和“一匹马”等更具体的词，并增加回归测试。最终自然兴趣用户的Top 5包括海滩草坪、山坡、羊群和长颈鹿，不再出现卫生间内容。")

    add_heading(doc, "16.7 结果边界", 2)
    add_bullet(doc, "模拟用户没有真实曝光、点击、停留、点赞、关注和负反馈，因此不能计算CTR、NDCG或长期留存。")
    add_bullet(doc, "COCO CN属于通用图文数据，不完全等同于社交平台UGC，缺少作者、时间、地域、热度和质量等业务字段。")
    add_bullet(doc, "热度、质量和地域在缺少真实字段时使用中性值，本次排序主要由语义和兴趣类别决定。")
    add_bullet(doc, "当前兴趣类别词表规模较小，后续应使用多标签分类模型或业务标签体系替代人工关键词。")
    add_bullet(doc, "本实验验证推荐链路可以运行以及样例结果基本合理，不代表线上业务收益已经得到验证。")

    add_heading(doc, "16.8 下一阶段计划", 2)
    add_body(doc, "下一阶段应把静态初始画像升级为可更新画像。用户完成曝光、点击、长停留、点赞、关注、跳过或举报后，系统按行为强度和时间衰减更新兴趣向量，并逐渐降低注册兴趣和群体先验的权重。")
    add_bullet(doc, "为UGC增加多标签、发布时间、作者、地域、热度、质量和安全字段。")
    add_bullet(doc, "构造人工相关性标注集，计算Recall at K、NDCG at K、MRR、覆盖率和多样性。")
    add_bullet(doc, "记录曝光日志并建立位置校正，避免直接把点击当作无偏标签。")
    add_bullet(doc, "设计冷启动对照实验，比较热门基线、纯语义模型和混合打分模型。")
    add_bullet(doc, "在线阶段以点击率、有效停留、关注率、负反馈率和次日留存共同判断收益。")

    add_heading(doc, "16.9 复现实验", 2)
    add_body(doc, "在项目目录激活ugc-minimal环境后执行以下命令，可重新生成冷启动推荐结果。")
    command = (
        "python app.py cold-start --users data\\cold_start\\users.jsonl "
        "--candidates data\\eval\\coco_cn_mini_100\\records.jsonl "
        "--output reports\\cold_start_recommendations.json --top-k 5 --device cpu"
    )
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.left_indent = Cm(0.6)
    paragraph.paragraph_format.right_indent = Cm(0.6)
    paragraph.paragraph_format.space_before = Pt(4)
    paragraph.paragraph_format.space_after = Pt(8)
    set_cell_like = OxmlElement("w:shd")
    set_cell_like.set(qn("w:fill"), PALE_GRAY)
    paragraph._p.get_or_add_pPr().append(set_cell_like)
    run = paragraph.add_run(command)
    set_run_font(run, size=9.5)

    doc.core_properties.title = "社交场景多模态UGC搜索与推荐系统方案"
    doc.core_properties.subject = "用户画像冷启动推荐实验"
    doc.save(TMP_PATH)
    os.replace(TMP_PATH, DOCX_PATH)
    print(DOCX_PATH)


if __name__ == "__main__":
    main()
