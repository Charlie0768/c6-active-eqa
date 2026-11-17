"""S05 离线确定性评分：只在评分阶段读取私有真值文件。

运行时策略和视觉模型只能读取 dev_questions.json；本脚本在模型输出已经
保存后，才将预测与 dev_labels.json 按题目 ID 对齐。当前只支持是非题。
"""

import argparse
import hashlib
import json
from pathlib import Path


ACTION_BUDGET = 20
ANSWER_ALIASES = {
    "是": "是", "yes": "是", "true": "是",
    "否": "否", "no": "否", "false": "否",
    "不确定": "不确定", "unknown": "不确定", "unsure": "不确定",
}


def normalize_answer(value):
    """仅接受事先声明的完整别名；不能用子串匹配把“不是”误判成“是”。"""
    if not isinstance(value, str):
        return None
    return ANSWER_ALIASES.get(value.strip().casefold())


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def indexed(rows, name):
    """按 ID 建索引，并拒绝重复题目或重复预测，防止静默覆盖。"""
    result = {}
    for row in rows:
        item_id = row["id"]
        if item_id in result:
            raise ValueError(f"duplicate {name} id: {item_id}")
        result[item_id] = row
    return result


def score_rows(questions, labels, predictions, budget=ACTION_BUDGET):
    """逐题比较答案并计算准确率、行动数与项目自定义效率分。"""
    if not isinstance(budget, int) or isinstance(budget, bool) or budget < 1:
        raise ValueError("budget must be a positive integer")
    question_by_id = indexed(questions, "question")
    label_by_id = indexed(labels, "label")
    prediction_by_id = indexed(predictions, "prediction")
    expected = set(question_by_id)
    if set(label_by_id) != expected or set(prediction_by_id) != expected:
        raise ValueError("question, label and prediction IDs must match exactly")

    rows = []
    for item_id, question in question_by_id.items():
        if question["question_type"] not in ("yes_no_presence", "yes_no_attribute"):
            raise ValueError(f"unsupported question type: {item_id}")
        gold = normalize_answer(label_by_id[item_id]["answer"])
        if gold not in ("是", "否"):
            raise ValueError(f"gold answer must be yes/no: {item_id}")
        prediction = prediction_by_id[item_id]
        actions = prediction["actions_used"]
        if not isinstance(actions, int) or isinstance(actions, bool) or not 0 <= actions <= budget:
            raise ValueError(f"invalid actions_used: {item_id}")
        # JSON 格式失败和“不确定”都留在分母内，不能当作缺失样本排除。
        answer = normalize_answer(prediction.get("answer")) if prediction.get("valid_answer_json") is True else None
        correct = answer == gold
        rows.append({
            "id": item_id,
            "question_type": question["question_type"],
            "gold_answer": gold,
            "predicted_answer": answer,
            "correct": correct,
            "actions_used": actions,
            "efficiency_score": round((1 - actions / (2 * budget)) if correct else 0.0, 6),
        })

    count = len(rows)
    if count == 0:
        raise ValueError("question set is empty")
    correct_rows = [row for row in rows if row["correct"]]
    return {
        "question_count": count,
        "correct_count": len(correct_rows),
        "accuracy": len(correct_rows) / count,
        "mean_actions": sum(row["actions_used"] for row in rows) / count,
        "mean_actions_when_correct": (
            sum(row["actions_used"] for row in correct_rows) / len(correct_rows)
            if correct_rows else None
        ),
        "mean_correct_action_efficiency": sum(row["efficiency_score"] for row in rows) / count,
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path, default=Path("data/dev_questions.json"))
    parser.add_argument("--labels", type=Path, default=Path("data/dev_labels.json"))
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"refusing to overwrite existing score file: {args.output}")

    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    labels = json.loads(args.labels.read_text(encoding="utf-8"))
    predictions = json.loads(args.predictions.read_text(encoding="utf-8"))
    if not (questions["schema_version"] == labels["schema_version"] == predictions["schema_version"]):
        parser.error("dataset and prediction schema versions differ")
    if predictions["baseline"] == "B0_initial_rgb_only" and any(
        row["actions_used"] != 0 for row in predictions["predictions"]
    ):
        parser.error("B0 predictions must use zero actions")
    result = score_rows(questions["questions"], labels["labels"], predictions["predictions"])
    result.update({
        "schema_version": questions["schema_version"],
        "baseline": predictions["baseline"],
        "questions_sha256": file_sha256(args.questions),
        "labels_sha256": file_sha256(args.labels),
        "predictions_sha256": file_sha256(args.predictions),
        "score_kind": "exact_yes_no_with_project_action_efficiency",
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in (
        "question_count", "correct_count", "accuracy", "mean_actions",
        "mean_correct_action_efficiency")}, ensure_ascii=False, indent=2))
    print(f"Full scores: {args.output.resolve()}")


if __name__ == "__main__":
    main()
