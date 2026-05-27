from __future__ import annotations

import json
import re
from typing import TypedDict

from langgraph.graph import END, StateGraph

from .database import connect, decode_options, row_to_dict
from .knowledge import all_context, chapter_context, document_outline_chapters, has_documents, knowledge_stats, outline_context, search_chunks
from .providers import call_provider


class AssistantState(TypedDict, total=False):
    task: str
    chapter_id: int
    chapter_count: int
    provider: str
    model: str
    base_url: str
    api_key: str
    api_key_env: str
    context: str
    chapter_title: str
    chapter_objective: str
    prompt_templates: dict[str, str]
    initialization_id: str
    prompt: str
    result: str
    warning: str


DEFAULT_PROMPTS = {
    "outline": (
        "你是一个严谨的课程学习路径设计师。\n\n"
        "请基于给定课程资料，为学生设计一套系统化学习大纲。大纲要能覆盖资料的主要知识结构，而不是只概括前几页内容。\n\n"
        "资料规模信息：\n"
        "- 建议章节数量：{{chapter_count}} 章\n\n"
        "生成要求：\n"
        "1. 严格输出 {{chapter_count}} 行。\n"
        "2. 每行只表示一个学习章节。\n"
        "3. 每行格式必须为：章节标题 - 学习目标\n"
        "4. 章节标题要简洁明确，适合作为学习路径卡片标题。\n"
        "5. 学习目标要具体，说明学生学完本章应该掌握什么。\n"
        "6. 章节之间要有递进关系，从基础概念到实践应用，再到总结提升。\n"
        "7. 如果资料中存在目录、章节标题、学习路线图，请优先参考原资料结构。\n"
        "8. 不要只生成泛泛的“概述、基础、应用、总结”四类标题。\n"
        "9. 不要输出寒暄语。\n"
        "10. 不要输出“好的”“下面是”“这是为你生成的”等说明。\n"
        "11. 不要输出 Markdown 代码块。\n"
        "12. 不要输出额外解释。\n\n"
        "课程资料：\n{{context}}"
    ),
    "chapter": (
        "你是一个专业的课程章节讲义生成器。\n\n"
        "请严格基于课程资料，为章节《{{chapter_title}}》生成一份可以直接展示给学生学习的 Markdown 讲义。\n\n"
        "章节目标：\n{{chapter_objective}}\n\n"
        "内容质量要求：\n"
        "1. 内容必须有实际学习价值，不能只是几句话概括。\n"
        "2. 内容应当适合学生自学，讲解要清楚、分层、有逻辑。\n"
        "3. 要结合资料中的术语、概念、例子、章节结构，不要泛泛而谈。\n"
        "4. 对于教材类资料，应尽量还原教材知识脉络。\n"
        "5. 不要编造资料中完全没有的具体页码、作者观点或代码细节。\n"
        "6. 可以适度补充通用解释，但必须服务于理解资料内容。\n"
        "7. 输出内容建议不少于 900 个中文字符；如果资料上下文足够，建议 1200~1800 个中文字符。\n"
        "8. 不要输出寒暄语。\n"
        "9. 不要输出“好的”“下面是”“这是为你生成的”“以下内容”等开场白。\n"
        "10. 不要重复章节标题和章节目标。\n"
        "11. 不要使用 Markdown 代码围栏。\n\n"
        "输出结构必须包含以下二级标题：\n\n"
        "## 学习目标\n"
        "用 3~5 条项目符号说明本章学完后应掌握的能力。\n\n"
        "## 核心概念\n"
        "解释本章最重要的概念。每个概念都要有简明解释，不能只列名词。\n\n"
        "## 知识讲解\n"
        "按照由浅入深的方式展开说明。必要时使用有序列表、小标题和加粗突出重点。\n\n"
        "## 典型例子或应用场景\n"
        "结合资料内容说明这些知识可以解决什么问题，或者在实际项目中如何使用。\n\n"
        "## 重点难点\n"
        "列出本章容易混淆、容易忽视、需要重点理解的地方。\n\n"
        "## 易错点提醒\n"
        "列出学生学习或答题时容易犯的错误，并说明原因。\n\n"
        "## 本章小结\n"
        "用简洁语言总结本章核心内容。\n\n"
        "## 复盘建议\n"
        "给出学生复习本章时可以采用的方法，例如画图、对比、做题、复述、代码实践等。\n\n"
        "课程资料：\n{{context}}"
    ),
    "quiz": (
        "你是一个严谨的课程测验出题器。\n\n"
        "请严格基于课程资料和章节学习目标，为章节《{{chapter_title}}》生成一组用于检测学习成果的测验题。\n\n"
        "章节目标：\n{{chapter_objective}}\n\n"
        "出题要求：\n"
        "1. 生成 10 道单选题。\n"
        "2. 每题 4 个选项。\n"
        "3. 题目必须覆盖本章主要知识点，不要集中考同一个概念。\n"
        "4. 题目需要有难度层级：3 道基础记忆题、3 道概念理解题、2 道应用分析题、1 道易错辨析题、1 道拓展思考题。\n"
        "5. 选项不能过于明显，错误选项要有一定迷惑性。\n"
        "6. 正确答案必须与 options 中某一项完全一致。\n"
        "7. explanation 必须解释为什么正确，以及为什么其他选项不合适。\n"
        "8. 不要输出 Markdown 代码块。\n"
        "9. 不要输出任何解释文字。\n"
        "10. 只输出合法 JSON 数组。\n\n"
        "JSON 对象必须包含 type、difficulty、question、options、answer、explanation。\n\n"
        "课程资料：\n{{context}}"
    ),
}

MIN_CHAPTERS = 4
MAX_CHAPTERS = 10
DEFAULT_QUIZ_COUNT = 10
FALLBACK_QUIZ_COUNT = 6
_CANCELLED_INITIALIZATIONS: set[str] = set()


def cancel_initialization(initialization_id: str) -> None:
    if initialization_id:
        _CANCELLED_INITIALIZATIONS.add(initialization_id)
    clear_generated_learning()


def clear_generated_learning() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM wrong_answers")
        conn.execute("DELETE FROM quizzes")
        conn.execute("DELETE FROM chapters")


def _raise_if_cancelled(initialization_id: str = "") -> None:
    if initialization_id and initialization_id in _CANCELLED_INITIALIZATIONS:
        raise ValueError("课程初始化已暂停，已清空本次生成的大纲、章节内容和测验。")


def run_outline(
    provider: str,
    model: str = "",
    base_url: str = "",
    api_key: str = "",
    api_key_env: str = "",
    prompt_templates: dict[str, str] | None = None,
    initialization_id: str = "",
) -> dict:
    _require_documents()
    _raise_if_cancelled(initialization_id)
    stats = knowledge_stats()
    source_chapters = document_outline_chapters()
    chapter_count = len(source_chapters) if len(source_chapters) >= 4 else estimate_outline_size(stats["total_chunks"], stats["total_chars"])
    if len(source_chapters) >= 4:
        _raise_if_cancelled(initialization_id)
        _replace_outline(source_chapters[:chapter_count])
        return {"chapters": list_chapters(), "warning": ""}
    state = _graph().invoke(
        {
            "task": "outline",
            "chapter_count": chapter_count,
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "api_key": api_key,
            "api_key_env": api_key_env,
            "prompt_templates": prompt_templates or {},
            "initialization_id": initialization_id,
        }
    )
    _raise_if_cancelled(initialization_id)
    chapters = _merge_outline_with_source(_parse_outline(state["result"], chapter_count), source_chapters, chapter_count)
    _replace_outline(chapters)
    return {"chapters": list_chapters(), "warning": state.get("warning", "")}


def _replace_outline(chapters: list[dict]) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM chapters")
        conn.execute("DELETE FROM quizzes")
        conn.execute("DELETE FROM wrong_answers")
        conn.executemany(
            "INSERT INTO chapters(title, objective, content) VALUES (?, ?, '')",
            [(item["title"], item["objective"]) for item in chapters],
        )


def generate_chapter(
    chapter_id: int,
    provider: str,
    model: str = "",
    base_url: str = "",
    api_key: str = "",
    api_key_env: str = "",
    prompt_templates: dict[str, str] | None = None,
    initialization_id: str = "",
) -> dict:
    _require_documents()
    _raise_if_cancelled(initialization_id)
    state = _graph().invoke(
        {
            "task": "chapter",
            "chapter_id": chapter_id,
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "api_key": api_key,
            "api_key_env": api_key_env,
            "prompt_templates": prompt_templates or {},
            "initialization_id": initialization_id,
        }
    )
    _raise_if_cancelled(initialization_id)
    with connect() as conn:
        conn.execute("UPDATE chapters SET content=?, progress=35, status='learning' WHERE id=?", (state["result"], chapter_id))
    return {"chapter": get_chapter(chapter_id), "warning": state.get("warning", "")}


def generate_quiz(
    chapter_id: int,
    provider: str,
    model: str = "",
    base_url: str = "",
    api_key: str = "",
    api_key_env: str = "",
    prompt_templates: dict[str, str] | None = None,
    initialization_id: str = "",
) -> dict:
    _require_documents()
    _raise_if_cancelled(initialization_id)
    chapter = get_chapter(chapter_id)
    context = "\n\n".join(
        item
        for item in [
            f"章节学习内容：\n{chapter['content']}" if chapter.get("content") else "",
            chapter_context(chapter["title"], chapter["objective"], 12),
        ]
        if item
    )
    prompt = _render_prompt(
        (prompt_templates or {}).get("quiz"),
        "quiz",
        {
            "context": context or chapter["content"],
            "chapter_title": chapter["title"],
            "chapter_objective": chapter["objective"],
        },
    )
    result = call_provider(provider, prompt, model, base_url, api_key, api_key_env)
    _raise_if_cancelled(initialization_id)
    questions = _parse_quiz(result.text, chapter)
    with connect() as conn:
        conn.execute("DELETE FROM quizzes WHERE chapter_id=?", (chapter_id,))
        conn.executemany(
            "INSERT INTO quizzes(chapter_id, type, difficulty, question, options, answer, explanation) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    chapter_id,
                    item["type"],
                    item["difficulty"],
                    item["question"],
                    json.dumps(item["options"], ensure_ascii=False),
                    item["answer"],
                    item["explanation"],
                )
                for item in questions
            ],
        )
    return {"quizzes": list_quizzes(chapter_id), "warning": result.warning}


def submit_quiz(chapter_id: int, answers: dict[str, str]) -> dict:
    quizzes = list_quizzes(chapter_id)
    if not quizzes:
        raise ValueError("当前章节暂无测验，请先生成测验题目。")
    score = 0
    details = []
    with connect() as conn:
        for quiz in quizzes:
            selected = answers.get(str(quiz["id"]), "")
            correct = selected == quiz["answer"]
            score += 1 if correct else 0
            if not correct:
                conn.execute("INSERT INTO wrong_answers(quiz_id, selected) VALUES (?, ?)", (quiz["id"], selected))
            details.append({**quiz, "selected": selected, "correct": correct})
        progress = 100 if score == len(quizzes) else max(60, int(score / max(len(quizzes), 1) * 100))
        conn.execute(
            "UPDATE chapters SET progress=?, status=? WHERE id=?",
            (progress, "completed" if progress == 100 else "reviewing", chapter_id),
        )
    total = len(quizzes)
    accuracy = round(score / max(total, 1) * 100)
    level = "掌握良好" if accuracy >= 90 else "基本掌握" if accuracy >= 70 else "建议复习" if accuracy >= 60 else "需要重点复盘"
    advice = "先复盘错题，再继续学习下一章。" if score < total else "可以进入下一章，保持当前学习节奏。"
    return {
        "score": score,
        "total": total,
        "accuracy": accuracy,
        "level": level,
        "wrong_count": total - score,
        "advice": advice,
        "details": details,
        "chapter": get_chapter(chapter_id),
    }


def list_chapters() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM chapters ORDER BY id").fetchall()
    return [row_to_dict(row) for row in rows]


def get_chapter(chapter_id: int) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM chapters WHERE id=?", (chapter_id,)).fetchone()
    if not row:
        raise ValueError("章节不存在，请先生成课程大纲。")
    return row_to_dict(row)


def list_quizzes(chapter_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM quizzes WHERE chapter_id=? ORDER BY id", (chapter_id,)).fetchall()
    return [{**row_to_dict(row), "options": decode_options(row["options"])} for row in rows]


def wrong_answers() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT wrong_answers.id, wrong_answers.selected, wrong_answers.created_at,
                   quizzes.question, quizzes.options, quizzes.answer, quizzes.explanation,
                   quizzes.type, quizzes.difficulty,
                   chapters.title AS chapter_title
            FROM wrong_answers
            JOIN quizzes ON quizzes.id = wrong_answers.quiz_id
            JOIN chapters ON chapters.id = quizzes.chapter_id
            ORDER BY wrong_answers.id DESC
            """
        ).fetchall()
    return [{**row_to_dict(row), "options": decode_options(row["options"])} for row in rows]


def _require_documents() -> None:
    if not has_documents():
        raise ValueError("请先上传课程资料，系统需要基于知识库生成大纲和测验。")


def _graph():
    graph = StateGraph(AssistantState)
    graph.add_node("retrieve", _retrieve)
    graph.add_node("compose", _compose)
    graph.add_node("generate", _generate)
    graph.set_entry_point("retrieve")
    graph.add_edge("retrieve", "compose")
    graph.add_edge("compose", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


def _retrieve(state: AssistantState) -> AssistantState:
    if state["task"] == "chapter":
        chapter = get_chapter(int(state["chapter_id"]))
        state["context"] = chapter_context(chapter["title"], chapter["objective"], 14) or all_context(16)
    elif state["task"] == "outline":
        state["context"] = outline_context(26)
    else:
        state["context"] = all_context()
    return state


def _compose(state: AssistantState) -> AssistantState:
    if state["task"] == "outline":
        state["prompt"] = _render_prompt(
            state.get("prompt_templates", {}).get("outline"),
            "outline",
            {"context": state.get("context", ""), "chapter_count": str(state.get("chapter_count", 6))},
        )
    else:
        chapter = get_chapter(int(state["chapter_id"]))
        state["prompt"] = _render_prompt(
            state.get("prompt_templates", {}).get("chapter"),
            "chapter",
            {
                "context": state.get("context", ""),
                "chapter_title": chapter["title"],
                "chapter_objective": chapter["objective"],
            },
        )
    return state


def _generate(state: AssistantState) -> AssistantState:
    _raise_if_cancelled(state.get("initialization_id", ""))
    result = call_provider(
        state.get("provider", "mock"),
        state.get("prompt", ""),
        state.get("model", ""),
        state.get("base_url", ""),
        state.get("api_key", ""),
        state.get("api_key_env", ""),
    )
    _raise_if_cancelled(state.get("initialization_id", ""))
    state["result"] = _clean_model_text(result.text, state.get("task", ""))
    state["warning"] = result.warning
    return state


def _render_prompt(template: str | None, key: str, values: dict[str, str]) -> str:
    text = (template or "").strip() or DEFAULT_PROMPTS[key]
    if key == "outline" and "{{chapter_count}}" not in text:
        text = DEFAULT_PROMPTS[key]
    for name, value in values.items():
        text = text.replace(f"{{{{{name}}}}}", value or "")
    return text


def _clean_model_text(text: str, task: str = "") -> str:
    cleaned = _strip_code_fences(text)
    lines = []
    dropping_prefix = True
    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line or line == "---":
            if dropping_prefix:
                continue
            lines.append(raw_line)
            continue
        if dropping_prefix and _is_preface_line(line):
            continue
        dropping_prefix = False
        lines.append(raw_line)
    cleaned = "\n".join(lines).strip()
    if task == "chapter":
        cleaned = re.sub(r"^#{1,3}\s*《[^》]+》\s*(?:学习指南|学习内容)?\s*\n+", "", cleaned).strip()
        cleaned = re.sub(r"^#{1,3}\s*(?:章节)?(?:学习指南|学习内容)\s*\n+", "", cleaned).strip()
    return cleaned


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json|markdown|md|text)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _is_preface_line(line: str) -> bool:
    patterns = [
        r"^好的[，。,\s]",
        r"^当然[，。,\s]",
        r"^下面是",
        r"^以下是",
        r"^这是为[您你]生成的",
        r"^我将为[您你]",
        r"^根据[您你]提供的资料",
        r"^基于[您你]提供的资料",
        r"^为[您你]整理",
    ]
    return any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in patterns)


def estimate_outline_size(total_chunks: int, total_chars: int) -> int:
    if total_chunks < 50:
        chapter_count = 4
    elif total_chunks < 150:
        chapter_count = 6
    elif total_chunks < 400:
        chapter_count = 8
    else:
        chapter_count = 10
    return min(max(chapter_count, MIN_CHAPTERS), MAX_CHAPTERS)


def _parse_outline(text: str, expected_count: int = 6) -> list[dict]:
    chapters = []
    for line in text.splitlines():
        clean = re.sub(r"^[\d一二三四五六七八九十、.()\s-]+", "", line).strip()
        if not clean or len(clean) < 4:
            continue
        if " - " in clean:
            title, objective = clean.split(" - ", 1)
        elif "：" in clean:
            title, objective = clean.split("：", 1)
        else:
            title, objective = clean[:18], clean
        chapters.append({"title": title.strip()[:40], "objective": objective.strip()[:120]})
        if len(chapters) == expected_count:
            break
    if len(chapters) < expected_count:
        existing_titles = {item["title"] for item in chapters}
        for item in fallback_outline(expected_count):
            if item["title"] in existing_titles:
                continue
            chapters.append(item)
            existing_titles.add(item["title"])
            if len(chapters) == expected_count:
                break
    return chapters[:expected_count]


def _merge_outline_with_source(generated: list[dict], source: list[dict], expected_count: int) -> list[dict]:
    if len(source) >= 4:
        return source[:expected_count]
    return generated[:expected_count]


def _parse_quiz(text: str, chapter: dict) -> list[dict]:
    try:
        text = _strip_code_fences(text)
        start = text.index("[")
        end = text.rindex("]") + 1
        parsed = json.loads(text[start:end])
        questions = normalize_quiz_items(parsed, chapter)
        if len(questions) >= 5:
            return questions
    except Exception:
        pass
    return fallback_quiz(chapter)


def normalize_quiz_items(items: list, chapter: dict) -> list[dict]:
    questions = []
    for index, item in enumerate(items[:DEFAULT_QUIZ_COUNT]):
        if not isinstance(item, dict):
            continue
        options = item.get("options", [])
        if not isinstance(options, list):
            continue
        options = [str(option).strip() for option in options if str(option).strip()][:4]
        if len(options) != 4:
            continue
        answer = str(item.get("answer", "")).strip()
        if answer not in options:
            answer = options[0]
        question = str(item.get("question", "")).strip()
        if not question:
            question = f"{chapter['title']}第 {index + 1} 题考察什么？"
        questions.append(
            {
                "type": str(item.get("type", "")).strip() or "综合题",
                "difficulty": str(item.get("difficulty", "")).strip() or "normal",
                "question": question,
                "options": options,
                "answer": answer,
                "explanation": str(item.get("explanation", "")).strip() or "该题用于检查章节核心概念掌握情况。",
            }
        )
    if len(questions) < 5:
        questions.extend(fallback_quiz(chapter)[: 5 - len(questions)])
    return questions[:DEFAULT_QUIZ_COUNT]


def fallback_outline(chapter_count: int) -> list[dict]:
    base = [
        ("深度学习基础与学习路线", "理解深度学习的基本概念、典型任务和整体学习路径。"),
        ("神经网络数学基础", "掌握张量、矩阵运算、梯度和优化的基础知识。"),
        ("神经网络训练流程", "理解前向传播、损失函数、反向传播和参数更新过程。"),
        ("Keras 与模型构建入门", "掌握使用高级框架构建、训练和评估神经网络的方法。"),
        ("机器学习工作流程", "理解数据准备、验证集划分、过拟合控制和模型评估。"),
        ("计算机视觉模型应用", "理解卷积神经网络及其在图像任务中的应用方式。"),
        ("文本与序列模型", "掌握序列数据、循环网络、嵌入表示和文本任务基本思路。"),
        ("生成式模型与综合实践", "了解生成式模型思想，并能将前面知识整合到项目实践。"),
        ("模型调优与工程化", "理解超参数调节、训练监控和部署前的质量检查。"),
        ("课程复盘与能力迁移", "通过测验、错题和总结形成可迁移的深度学习学习方法。"),
    ]
    return [{"title": title, "objective": objective} for title, objective in base[:chapter_count]]


def fallback_quiz(chapter: dict) -> list[dict]:
    types = [
        ("基础记忆题", "easy"),
        ("基础记忆题", "easy"),
        ("概念理解题", "normal"),
        ("概念理解题", "normal"),
        ("应用分析题", "normal"),
        ("易错辨析题", "hard"),
    ]
    questions = [
        {
            "type": types[0][0],
            "difficulty": types[0][1],
            "question": f"学习《{chapter['title']}》时最应该先完成哪项任务？",
            "options": ["阅读资料并提炼框架", "直接提交空白测验", "忽略学习目标", "删除知识库"],
            "answer": "阅读资料并提炼框架",
            "explanation": "先建立框架有助于理解章节结构。",
        },
        {
            "type": types[1][0],
            "difficulty": types[1][1],
            "question": f"《{chapter['title']}》的学习目标主要用于指导什么？",
            "options": ["明确本章应掌握的能力", "替代所有原始资料", "跳过测验环节", "清空错题记录"],
            "answer": "明确本章应掌握的能力",
            "explanation": "学习目标帮助学生判断本章重点，并指导后续学习和测验。",
        },
        {
            "type": types[2][0],
            "difficulty": types[2][1],
            "question": "章节内容生成时为什么要结合原始资料片段？",
            "options": ["保证讲义贴合资料知识结构", "让内容越短越好", "避免生成学习目标", "只为了显示文件名"],
            "answer": "保证讲义贴合资料知识结构",
            "explanation": "结合资料片段可以减少泛泛而谈，使内容更贴近课程资料。",
        },
        {
            "type": types[3][0],
            "difficulty": types[3][1],
            "question": "错题归档的主要作用是什么？",
            "options": ["定位薄弱点并复盘", "隐藏错误", "减少学习资料", "替代章节学习"],
            "answer": "定位薄弱点并复盘",
            "explanation": "错题复盘能帮助学习者有针对性地巩固。",
        },
        {
            "type": types[4][0],
            "difficulty": types[4][1],
            "question": "本系统知识库构建依赖的关键步骤是什么？",
            "options": ["资料加载与文本切割", "只保存文件名", "关闭后端服务", "跳过检索"],
            "answer": "资料加载与文本切割",
            "explanation": "LangChain loader 和 splitter 是知识库构建的基础。",
        },
        {
            "type": types[5][0],
            "difficulty": types[5][1],
            "question": "如果测验结果不理想，最合适的下一步是什么？",
            "options": ["查看解析并回到重点难点复盘", "删除所有资料", "继续随机答题", "关闭模型设置"],
            "answer": "查看解析并回到重点难点复盘",
            "explanation": "复盘解析并回看章节重点，才能把错误转化为新的学习线索。",
        },
    ]
    return questions
