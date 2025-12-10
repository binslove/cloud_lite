import boto3
import botocore
import time
import os
import json
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict, Any

CONFIG_PATH = "aws_credentials.json"


def save_credentials(access_key: str, secret_key: str) -> None:
    """입력받은 자격 증명을 로컬 JSON 파일에 저장"""
    data = {
        "AWS_ACCESS_KEY": access_key,
        "AWS_SECRET_KEY": secret_key,
    }
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    print(f"\n✔ 자격 증명이 '{CONFIG_PATH}' 파일에 저장되었습니다.")


def load_credentials() -> Optional[Dict[str, Any]]:
    """저장된 자격 증명 불러오기 (없으면 None 반환)"""
    if not os.path.exists(CONFIG_PATH):
        return None

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_or_create_credentials() -> Tuple[str, str]:
    """
    최초 실행이면 사용자에게 키를 입력받아 저장하고,
    이후 실행부터는 저장된 정보를 바로 사용.
    """
    creds = load_credentials()

    if creds:
        print("✔ 저장된 AWS 자격 증명을 불러왔습니다.")
        return creds["AWS_ACCESS_KEY"], creds["AWS_SECRET_KEY"]

    print("============================================")
    print(" AWS 비용 모니터링 – 최초 설정 (A 역할 버전)")
    print("============================================")
    access_key = input("AWS Access Key ID 입력: ").strip()
    secret_key = input("AWS Secret Access Key 입력: ").strip()

    save_credentials(access_key, secret_key)
    return access_key, secret_key


def create_ce_client(access_key: str, secret_key: str):
    """입력된 키를 기반으로 boto3 Cost Explorer 클라이언트 생성"""
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="ap-northeast-2",
    )
    return session.client("ce")  # Cost Explorer


def fetch_cost(ce_client, start_date: str, end_date: str):
    """AWS Cost Explorer API를 사용해 서비스별 UnblendedCost 조회"""
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
    """조회 결과를 표 형태로 출력"""
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


def main() -> None:
    """어제~오늘 기간의 비용을 30분마다 반복 조회하는 메인 루프"""
    # 1) 조회 기간: 어제 ~ 오늘
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    interval_minutes = 30

    # 2) 자격 증명 준비
    access_key, secret_key = get_or_create_credentials()

    # 3) Cost Explorer 클라이언트 생성
    ce_client = create_ce_client(access_key, secret_key)

    # 4) 반복 모니터링 루프
    while True:
        print(f"\n===== 비용 확인: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====")
        resp = fetch_cost(ce_client, start_date, end_date)

        if resp:
            print_cost_table(resp)

        print(f"\n⏳ 다음 실행까지 {interval_minutes}분 대기...")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    main()
