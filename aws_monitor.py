import boto3
import botocore
import time
import os
import json
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any

# =====================================
# 기본 설정
# =====================================
CONFIG_PATH = "aws_credentials.json"

# =====================================
# AWS 크레덴셜 관리 + 비용 조회
# =====================================
def save_credentials(access_key: str, secret_key: str) -> None:
    data = {"AWS_ACCESS_KEY": access_key, "AWS_SECRET_KEY": secret_key}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"\n✔ 자격 증명이 '{CONFIG_PATH}' 파일에 저장되었습니다.")

def load_credentials() -> Optional[Dict[str, Any]]:
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_or_create_credentials() -> Tuple[str, str]:
    creds = load_credentials()
    if creds:
        print("✔ 저장된 AWS 자격 증명을 불러왔습니다.")
        return creds["AWS_ACCESS_KEY"], creds["AWS_SECRET_KEY"]

    print("============================================")
    print(" AWS 비용 모니터링 – 최초 설정")
    print("============================================")
    access_key = input("AWS Access Key ID 입력: ").strip()
    secret_key = input("AWS Secret Access Key 입력: ").strip()
    save_credentials(access_key, secret_key)
    return access_key, secret_key

def create_ce_client(access_key: str, secret_key: str):
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="ap-northeast-2",
    )
    return session.client("ce")

def fetch_cost(ce_client, start_date: str, end_date: str):
    try:
        response = ce_client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
        return response
    except botocore.exceptions.ClientError as e:
        print("\n[ERROR] AWS API 호출 실패:")
        print(e)
        return None

def print_cost_table(response) -> None:
    print("\n===== AWS 비용 결과 =====")
    results = response.get("ResultsByTime", [])
    for day in results:
        date = day["TimePeriod"]["Start"]
        print(f"\n📅 날짜: {date}")
        print("----------------------------------")
        for g in day.get("Groups", []):
            service = g["Keys"][0]
            amount = g["Metrics"]["UnblendedCost"]["Amount"]
            print(f"{service:<35} {float(amount):.4f} USD")
        print("----------------------------------")

# =====================================
# 비용 이상징후 감지 + 콘솔 알림
# =====================================
def calculate_total_cost(response):
    results = response.get("ResultsByTime", [])
    if not results:
        return 0.0
    day = results[0]
    total = 0.0
    for g in day.get("Groups", []):
        total += float(g["Metrics"]["UnblendedCost"]["Amount"])
    return total

def detect_anomaly(cost_today: float, cost_yesterday: float, threshold: float = 1.5) -> bool:
    if cost_yesterday == 0:
        return False
    return cost_today / cost_yesterday >= threshold

def send_alert(message: str):
    """Webhook 없이 콘솔로만 알림"""
    print("\n[ALERT] 비용 이상 감지!")
    print(message)
    print("[✔] 알림 완료!")

# =====================================
# 메인 루프
# =====================================
def main() -> None:
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    interval_minutes = 30

    access_key, secret_key = get_or_create_credentials()
    ce_client = create_ce_client(access_key, secret_key)
    prev_cost = None

    while True:
        print(f"\n===== 비용 확인: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
        resp = fetch_cost(ce_client, start_date, end_date)
        if resp:
            print_cost_table(resp)
            today_total = calculate_total_cost(resp)
            if prev_cost is not None:
                if detect_anomaly(today_total, prev_cost, threshold=1.5):
                    increase = today_total / prev_cost
                    alert_message = (
                        f"🚨 AWS 비용 이상 감지!\n"
                        f"전일 대비 {increase:.2f}배 증가\n"
                        f"어제: {prev_cost:.4f} USD → 오늘: {today_total:.4f} USD"
                    )
                    send_alert(alert_message)
            prev_cost = today_total
        print(f"\n⏳ 다음 실행까지 {interval_minutes}분 대기...")
        time.sleep(interval_minutes * 60)

if __name__ == "__main__":
    main()


