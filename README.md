## GPT 기반 비용 분석 (추가 기능)

이 프로젝트는 비용 모니터링 결과를 자동으로 GPT 모델에 보내 간단한 한국어 분석 리포트를 생성합니다.
분석은 `ai_analyzer.py`에 구현되어 있으며, `aws_monitor.py`가 비용을 출력한 직후에 AI 분석을 호출합니다.

### 동작 원리
1. Cost Explorer에서 기간별/서비스별 비용을 조회합니다.
2. 조회된 결과에서 `date`, `service`, `cost` 형태의 레코드 리스트를 생성합니다.
3. 이 리스트를 `ai_analyzer.analyze_cost_with_gpt`에 전달하면 GPT 모델이 다음을 포함한 한국어 리포트를 반환합니다:
   - 이상 비용(Anomaly) 감지 및 근거
   - 전체 비용 추세 요약
   - 추가 확인 항목(운영팀 액션 아이템) 제안
   - (선택) 비용 절감 아이디어

### 필요한 환경변수
- `OPENAI_API_KEY` : OpenAI API 키 (예: `sk-xxxx...`)

예시: Windows PowerShell에서 환경변수 설정
```powershell
$env:OPENAI_API_KEY="sk-xxxx..."
