# Copyright 2026 Baek Ga-hui (neisii) - https://github.com/neisii/harness-naroo
# SPDX-License-Identifier: Apache-2.0
"""
qa-inbox.py — QA 대기 장부 조회 (AG-15)

읽기 전용 CLI: 장부 폴더의 모든 JSON에서 수신자=qa-master, 상태=open 항목만
필터링해 긴급도(막힘 우선)·보낸시각(오름차순)으로 정렬해 표시.
"""

import sys
import json
import os
import argparse
from pathlib import Path
from datetime import datetime
import re


def get_field(obj, korean_key, english_key=None):
    """한글 키 우선, 영문 키 폴백."""
    if isinstance(obj, dict):
        val = obj.get(korean_key)
        if val is not None and val != "":
            return val
        if english_key:
            val = obj.get(english_key)
            if val is not None and val != "":
                return val
    return None


def parse_ledger_date(raw):
    """날짜 문자열 파싱: ^\s*(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}(:\d{2})?)"""
    if not raw or not isinstance(raw, str) or not raw.strip():
        return None

    match = re.match(r'^\s*(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}(:\d{2})?)', raw.strip())
    if not match:
        return None

    date_part = match.group(1)
    time_part = match.group(2)
    candidate = f"{date_part} {time_part}"

    formats = ["yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd HH:mm"]
    for fmt in formats:
        try:
            # Python datetime format
            python_fmt = fmt.replace("yyyy", "%Y").replace("MM", "%m").replace("dd", "%d").replace("HH", "%H").replace("mm", "%M").replace("ss", "%S")
            return datetime.strptime(candidate, python_fmt)
        except ValueError:
            pass

    return None


def get_elapsed_minutes(sent_at):
    """경과분 계산."""
    if not sent_at:
        return None
    now = datetime.now()
    elapsed = (now - sent_at).total_seconds() / 60
    return round(elapsed, 1)


def load_ledger_items(ledger_dir, recipient):
    """장부 폴더(존재 전제)의 JSON 로드·필터링.

    폴더 존재 확인은 호출자(main)가 먼저 한다. 여기서 file_issues 는 항상 문자열(파싱/접근 문제)이다.

    Returns:
        (items, delegation_count, file_issues)
    """
    ledger_path = Path(ledger_dir).expanduser()
    items = []
    delegation_count = 0
    file_issues = []

    try:
        json_files = list(ledger_path.glob("*.json"))
    except Exception as e:
        file_issues.append(f"폴더 접근 오류: {ledger_path} — {e}")
        return items, delegation_count, file_issues

    for json_file in sorted(json_files):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                root = json.load(f)
        except Exception as e:
            file_issues.append(f"읽기 문제: {json_file.name} — JSON 파싱 실패: {e}")
            continue

        if not isinstance(root, dict):
            file_issues.append(f"읽기 문제: {json_file.name} — 루트가 객체가 아님")
            continue

        item_list = get_field(root, "항목", "items")
        if not item_list:
            continue

        # item_list가 리스트가 아니면 단일 항목으로 취급
        if not isinstance(item_list, list):
            item_list = [item_list]

        for it in item_list:
            if not isinstance(it, dict):
                continue

            kind = get_field(it, "종류")
            if kind == "상시위임":
                delegation_count += 1

            status = get_field(it, "상태", "status")
            if status and status != "open":
                continue

            recv = get_field(it, "수신자", "recipient")
            if recv != recipient:
                continue

            requester = get_field(it, "요청자", "requester")
            sent_raw = get_field(it, "보낸시각", "sentAt")
            summary = get_field(it, "요지", "summary")
            urgency = get_field(it, "긴급도")
            if not urgency:
                urgency = "일반"

            sent_at = parse_ledger_date(sent_raw)
            elapsed_min = get_elapsed_minutes(sent_at) if sent_at else None

            summary_short = None
            if summary:
                summary_short = summary[:80] if isinstance(summary, str) else summary

            items.append({
                "보낸세션": requester,
                "긴급도": urgency,
                "보낸시각": sent_raw,
                "경과분": elapsed_min,
                "요지": summary_short,
                "장부파일경로": str(json_file.absolute()),
                "_sent_sort_key": sent_at if sent_at else datetime.max,
            })

    return items, delegation_count, file_issues


def sort_items(items):
    """긴급도=막힘 우선, 보낸시각 오름차순 정렬."""
    def sort_key(item):
        urgency_priority = 0 if item["긴급도"] == "막힘" else 1
        sent_key = item["_sent_sort_key"]
        return (urgency_priority, sent_key)

    return sorted(items, key=sort_key)


def format_table(items, delegation_count, file_issues):
    """테이블 형식 출력."""
    print(f"=== qa-inbox (qa-master 수신, {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    print()

    if file_issues:
        print("[읽기 문제]")
        for issue in file_issues:
            if isinstance(issue, str):
                print(f"  - {issue}")
            else:
                print(f"  - {issue.get('error', 'Unknown error')}")
        print()

    print(f"상시위임 사후 보고 건수: {delegation_count}")
    print()

    if not items:
        print("수신 대기 항목이 없습니다.")
    else:
        for row in items:
            urgency = row["긴급도"]
            color_code = "\033[91m" if urgency == "막힘" else ""  # Red for critical
            reset_code = "\033[0m" if color_code else ""

            print(f"{color_code}[{urgency}] {row['보낸세션']} → qa-master  {row['요지']}{reset_code}")
            print(f"  보낸시각 {row['보낸시각']} / 경과 {row['경과분']}분")
            print(f"  장부 파일: {row['장부파일경로']}")
            print()


def format_json(items, delegation_count, file_issues, has_error=False):
    """JSON 형식 출력."""
    # Remove internal sort key from output
    output_items = [
        {k: v for k, v in item.items() if not k.startswith("_")}
        for item in items
    ]

    result = {
        "조회시각": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "수신항목": output_items,
        "건수": len(items),
        "상시위임사후보고건수": delegation_count,
        "읽기문제": file_issues if not has_error else [{"error": "LedgerDir not found"}],
    }

    if has_error:
        result["error"] = "LedgerDir not found"

    return json.dumps(result, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="QA 대기 장부 조회 (수신자=qa-master, 상태=open)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON 형식으로 출력",
    )
    parser.add_argument(
        "--ledger-dir",
        default=None,
        help="장부 폴더 경로 (기본값: ~/.claude/qa-inbox/ledger 또는 QA_INBOX_LEDGER_DIR env)",
    )
    parser.add_argument(
        "--recipient",
        default="qa-master",
        help="수신자 필터 (기본값: qa-master)",
    )

    args = parser.parse_args()

    # 장부 경로 결정
    ledger_dir = args.ledger_dir
    if not ledger_dir:
        ledger_dir = os.environ.get("QA_INBOX_LEDGER_DIR")
    if not ledger_dir:
        ledger_dir = str(Path.home() / ".claude" / "qa-inbox" / "ledger")

    # 폴더 없는 경우 처리 — 로드 전에 분리해서 파싱 오류(문자열)와 혼동하지 않는다.
    ledger_path = Path(ledger_dir).expanduser()
    if not ledger_path.exists():
        if args.json:
            result = {
                "error": "LedgerDir not found",
                "path": str(ledger_path),
                "조회시각": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "수신항목": [],
                "건수": 0,
                "상시위임사후보고건수": 0,
                "읽기문제": [],
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"장부 폴더가 없습니다: {ledger_path}")
        return

    # 데이터 로드
    items, delegation_count, file_issues = load_ledger_items(ledger_dir, args.recipient)

    # 정렬
    sorted_items = sort_items(items)

    # 출력
    if args.json:
        print(format_json(sorted_items, delegation_count, file_issues))
    else:
        format_table(sorted_items, delegation_count, file_issues)


if __name__ == "__main__":
    main()
