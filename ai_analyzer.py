# ai_analyzer.py
"""
GPT 기반 비용 분석 모듈 (B 역할)
- analyze_cost_with_gpt(cost_rows: List[Dict]) -> str
- build_prompt(cost_rows) -> str

요구:
- OPENAI_API_KEY 환경변수에서 키를 읽음
- 모델: gpt-4.1-mini (경량)
"""

import os
import json
import statistics
from typing import List, Dict

try:
    # 최신 OpenAI Python SDK 사용법 가정
    from openai import OpenAI
except Exception as e:
    raise RuntimeError("openai 라이브러리가 필요합니다. requirements.txt에 openai를 추가하고 설치하세요.") from e


def build_prompt(cost_rows: List[Dict]) -> str:
    """
    GPT에 전달할 프롬프트를 구성.
    cost_rows 예시: [{"date": "2025-12-10", "service": "AmazonEC2", "cost": 12.34}, ...]
    GPT가 잘 이해하도록 요약, 질문 목록, 분석 포인트를 포함한 프롬프트 문자열 반환.
    """
    # 안정성: 정렬(날짜 기준) 및 JSON 직렬화
    try:
        rows_sorted = sorted(cost_rows, key=lambda r: r.get("date", ""))
    except Exception:
        rows_sorted = list(cost_rows)

    # 간단 통계(로컬)로 GPT에 추가 정보 제공 (추세, 평균, 표준편차)
    costs = [float(r.get("cost", 0.0)) for r in rows_sorted if r.get("cost") is not None]
    summary_stats = {}
    if costs:
        summary_stats = {
            "count": len(costs),
            "total": sum(costs),
            "mean": statistics.mean(costs),
        }
        if len(costs) > 1:
            summary_stats["stdev"] = statistics.pstdev(costs)  # population stdev
        else:
            summary_stats["stdev"] = 0.0
    else:
        summary_stats = {"count": 0, "total": 0.0, "mean": 0.0, "stdev": 0.0}

    prompt = f"""
당신은 AWS 비용 분석 전문가입니다. 아래는 AWS 서비스별/일자별 비용 데이터입니다.
목표: 한국어로 이해하기 쉬운 비용 분석 리포트를 만드세요. 포맷은 자유지만 아래 항목을 반드시 포함하세요:
  1) 이상 비용(Anomaly) 감지: 어떤 서비스/일자에서 평소보다 급증 또는 급감했는지 식별하고, 근거(숫자 비교: 전일 대비, 평균 대비 등)를 함께 표기하세요.
  2) 전체 추세 요약: 최근 기간의 총 비용 추세(증가/감소/안정)와 주요 원인으로 추정되는 서비스들을 요약하세요.
  3) 추가 확인 항목 제안: 운영팀이 확인해야 할 구체적인 액션 아이템(예: 특정 로그/리소스 확인, 예약 인스턴스/스팟 사용 확인, S3 데이터 전송량 점검 등).
  4) (선택) 비용 절감 아이디어가 있으면 간략히 제안하세요.

입력 데이터(정렬된 JSON)와 간단 통계는 아래에 포함됩니다. 숫자는 한국어로 설명하되, 중요한 수치는 괄호안에 원본 숫자를 포함하세요.

간단한 포맷 제안(권장):
- 요약(1-2문장)
- 주요 이상치(항목별, 한두문장 + 수치)
- 추세 및 원인(한두문단)
- 권장 확인 항목(번호 목록)
- 비용 절감 아이디어(선택)

아래는 데이터와 간단 통계입니다.

=== COST_ROWS_JSON START ===
{json.dumps(rows_sorted, ensure_ascii=False, indent=2)}
=== COST_ROWS_JSON END ===

=== SUMMARY_STATS START ===
{json.dumps(summary_stats, ensure_ascii=False, indent=2)}
=== SUMMARY_STATS END ===

주의:
- 분석은 주어진 데이터만 기반하여 추정으로 제시하세요. (확인 필요 시 '추정'이라고 표기)
- 결과는 한국어로 출력하세요.
"""
    return prompt.strip()


def analyze_cost_with_gpt(cost_rows: List[Dict]) -> str:
    """
    주어진 cost_rows를 GPT로 분석 요청하고, 한국어 분석 리포트를 문자열로 반환.
    """
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        return ("[AI 분석 실패] OPENAI_API_KEY 환경변수가 설정되어 있지 않습니다. "
                "환경변수를 설정한 뒤 다시 시도하세요.")

    prompt = build_prompt(cost_rows)

    # OpenAI 클라이언트 초기화 (최신 SDK 가정)
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
    except TypeError:
        # 일부 SDK 버전에서는 OpenAI()만 써야할 수 있음
        client = OpenAI()
        # client.api_key = OPENAI_API_KEY  # 보통은 생성자에서 처리되나 환경변수 reliance 가능

    # 호출: responses API 사용 가정
    try:
        # responses.create의 반환 형식이 SDK 버전에 따라 다를 수 있으므로 안전하게 처리
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            max_tokens=800  # 적당한 분량
        )
    except Exception as e:
        return f"[AI 분석 실패] OpenAI API 호출 중 오류가 발생했습니다: {e}"

    # 응답 텍스트 추출 (여러 SDK 호환성 고려)
    ai_text = None
    try:
        # 최신 responses API: response.output[0].content[0].text 또는 response.output_text
        if hasattr(response, "output_text"):
            ai_text = response.output_text
        else:
            out = getattr(response, "output", None)
            if out and isinstance(out, list) and len(out) > 0:
                # 합쳐서 텍스트 생성
                parts = []
                for item in out:
                    content = item.get("content", [])
                    for c in content:
                        # c can be dict like {"type":"output_text","text":"..."}
                        if isinstance(c, dict) and c.get("text"):
                            parts.append(c.get("text"))
                        elif isinstance(c, str):
                            parts.append(c)
                ai_text = "\n".join(parts).strip() if parts else None

        # 마지막 안전망
        if not ai_text:
            ai_text = str(response)
    except Exception:
        ai_text = str(response)

    # 최종 포맷: 간단한 헤더 + 본문
    header = "=== GPT 기반 비용 분석 리포트 ===\n"
    footer = "\n=== 리포트 끝 ==="
    return header + ai_text + footer
