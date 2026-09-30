import sys
import os
import json
import time
import random
import hashlib
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx

try:
    from src.config import Config, get_lawd_codes
    from src.database import DatabaseManager
    from src.ai_analyst import GeminiAnalyst
except ImportError:
    from .config import Config, get_lawd_codes
    from .database import DatabaseManager
    from .ai_analyst import GeminiAnalyst

class AptTradeCollector:
    def __init__(self, api_key: str | None = None, db_manager: DatabaseManager | None = None):
        self.api_key = api_key if api_key is not None else Config.API_KEY
        self.db = db_manager or DatabaseManager()
        self.lawd_codes = get_lawd_codes()
        self.sido_map = {c["code"]: (c["sido"], c["sigungu"]) for c in self.lawd_codes}
        self.analyst = GeminiAnalyst()

    def get_target_deal_ymds(self, days: int = 7) -> list[str]:
        """Get target YYYYMM strings covering the recent period."""
        today = datetime.now()
        start_date = today - timedelta(days=days)
        
        ymds = set()
        curr = start_date
        while curr <= today:
            ymds.add(curr.strftime("%Y%m"))
            curr += timedelta(days=1)
            
        return sorted(list(ymds))

    def categorize_pyeong(self, pyeong: float) -> str:
        if pyeong < 20:
            return "소형"
        elif pyeong < 30:
            return "중소형"
        elif pyeong < 40:
            return "중대형"
        else:
            return "대형"

    def parse_trade_item(self, item: dict, sido_map: dict | None = None) -> dict | None:
        """Parse raw XML/JSON item from public data portal to standard schema."""
        try:
            mapping = sido_map or self.sido_map
            sgg_cd = str(item.get("sggCd") or item.get("sigunguCode") or item.get("LAWD_CD") or "").strip()
            sido, sigungu = mapping.get(sgg_cd, ("기타", "기타"))

            year = int(str(item.get("dealYear", "0")).strip())
            month = int(str(item.get("dealMonth", "0")).strip())
            day = int(str(item.get("dealDay", "0")).strip())
            if year == 0 or month == 0 or day == 0:
                return None
                
            deal_date = f"{year:04d}-{month:02d}-{day:02d}"
            apt_name = str(item.get("aptNm") or item.get("aptName") or "").strip()
            umd_name = str(item.get("umdNm") or item.get("dong") or "").strip()
            
            raw_amount = str(item.get("dealAmount", "0")).replace(",", "").strip()
            deal_amount = int(raw_amount) if raw_amount.isdigit() else 0

            exclusive_area = float(str(item.get("excluUseAr") or item.get("exclusiveArea") or "0").strip())
            pyeong = round(exclusive_area / 3.30578, 1) if exclusive_area > 0 else 0.0
            pyeong_category = self.categorize_pyeong(pyeong)
            
            pyeong_price = round(deal_amount / pyeong, 1) if pyeong > 0 else 0.0
            
            floor_str = str(item.get("floor", "0")).strip()
            floor = int(floor_str) if floor_str.lstrip("-").isdigit() else 0
            
            build_year_str = str(item.get("buildYear", "0")).strip()
            build_year = int(build_year_str) if build_year_str.isdigit() else 0
            
            # Cancellation check
            cdeal_type = str(item.get("cdealType", "")).strip()
            cdeal_day = str(item.get("cdealDay", "")).strip()
            is_cancel = 1 if cdeal_type == "O" or len(cdeal_day) > 0 else 0
            cancel_date = cdeal_day if is_cancel else ""

            # Unique ID hash
            id_raw = f"{sgg_cd}_{deal_date}_{apt_name}_{floor}_{exclusive_area}_{deal_amount}"
            unique_id = hashlib.md5(id_raw.encode("utf-8")).hexdigest()

            return {
                "id": unique_id,
                "deal_date": deal_date,
                "deal_year": year,
                "deal_month": month,
                "deal_day": day,
                "sido": sido,
                "sigungu": sigungu,
                "sigungu_code": sgg_cd,
                "umd_name": umd_name,
                "apt_name": apt_name,
                "exclusive_area": exclusive_area,
                "pyeong": pyeong,
                "pyeong_category": pyeong_category,
                "floor": floor,
                "build_year": build_year,
                "deal_amount": deal_amount,
                "pyeong_price": pyeong_price,
                "is_cancel": is_cancel,
                "cancel_date": cancel_date,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception:
            return None

    def fetch_lawd_trades(self, lawd_cd: str, deal_ymd: str, max_retries: int = 3) -> list[dict]:
        """Fetch trades from public API with rate-limit handling and backoff."""
        if not self.api_key:
            return []
            
        params = {
            "serviceKey": self.api_key,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "numOfRows": "1000",
            "pageNo": "1"
        }
        
        endpoints = [Config.API_BASE_URL, Config.API_DEV_URL]
        
        for attempt in range(max_retries):
            for url in endpoints:
                try:
                    response = httpx.get(url, params=params, timeout=12.0)
                    if response.status_code != 200:
                        continue
                        
                    text = response.text
                    if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in text:
                        time.sleep(0.6 * (attempt + 1))
                        continue
                    if "<errMsg>SERVICE_KEY_IS_NOT_REGISTERED" in text:
                        continue
                        
                    root = ET.fromstring(text)
                    items = []
                    for item_elem in root.findall(".//item"):
                        item_dict = {}
                        for child in item_elem:
                            item_dict[child.tag] = child.text
                        if "sggCd" not in item_dict:
                            item_dict["sggCd"] = lawd_cd
                        parsed = self.parse_trade_item(item_dict)
                        if parsed:
                            items.append(parsed)
                    if items or "<resultCode>000</resultCode>" in text:
                        return items
                except Exception:
                    time.sleep(0.3)
                    continue
        return []

    def generate_mock_data(self, days: int = 7, count: int = 150) -> list[dict]:
        """Generate realistic mock data for local testing and demonstration."""
        sample_sigungus = self.lawd_codes if self.lawd_codes else [
            {"sido": "서울특별시", "sigungu": "강남구", "code": "11680"},
            {"sido": "서울특별시", "sigungu": "송파구", "code": "11710"},
            {"sido": "서울특별시", "sigungu": "마포구", "code": "11440"},
            {"sido": "경기도", "sigungu": "성남시 분당구", "code": "41135"},
            {"sido": "부산광역시", "sigungu": "해운대구", "code": "26350"},
            {"sido": "대구광역시", "sigungu": "수성구", "code": "27260"}
        ]
        
        apt_names_by_sido = {
            "서울특별시": ["래미안퍼스티지", "아크로리버파크", "반포자이", "헬리오시티", "은마", "마포래미안푸르지오", "잠실엘스"],
            "경기도": ["판교푸르지오그랑블", "분당파크뷰", "광교중흥S클래스", "킨텍스원시티", "힐스테이트광교"],
            "부산광역시": ["엘시티", "해운대아이파크", "삼익비치", "센텀센트레빌"],
            "대구광역시": ["두산위브더제니스", "수성SK리더스뷰", "범어센트럴푸르지오"]
        }
        
        areas = [59.9, 74.5, 84.9, 102.3, 114.8, 135.0]
        today = datetime.now()
        results = []
        
        for i in range(count):
            reg = random.choice(sample_sigungus)
            sido = reg["sido"]
            sigungu = reg["sigungu"]
            sgg_cd = reg["code"]
            
            names = apt_names_by_sido.get(sido, ["현대아이파크", "자이센트럴", "푸르지오더퍼스트", "e편한세상"])
            apt_name = random.choice(names)
            
            days_ago = random.randint(0, max(1, days - 1))
            deal_dt = today - timedelta(days=days_ago)
            deal_date = deal_dt.strftime("%Y-%m-%d")
            
            area = random.choice(areas)
            pyeong = round(area / 3.30578, 1)
            pyeong_category = self.categorize_pyeong(pyeong)
            
            base_pyeong_price = 8000 if "강남" in sigungu or "서초" in sigungu else (
                5000 if sido == "서울특별시" else (
                    3500 if "분당" in sigungu or "해운대" in sigungu or "수성" in sigungu else 2000
                )
            )
            variation = random.uniform(0.85, 1.25)
            pyeong_price = round(base_pyeong_price * variation, 1)
            deal_amount = int(pyeong_price * pyeong)
            
            floor = random.randint(1, 35)
            build_year = random.randint(1995, 2024)
            is_cancel = 1 if random.random() < 0.05 else 0
            cancel_date = deal_date if is_cancel else ""
            
            id_raw = f"{sgg_cd}_{deal_date}_{apt_name}_{floor}_{area}_{deal_amount}_{i}"
            unique_id = hashlib.md5(id_raw.encode("utf-8")).hexdigest()
            
            results.append({
                "id": unique_id,
                "deal_date": deal_date,
                "deal_year": deal_dt.year,
                "deal_month": deal_dt.month,
                "deal_day": deal_dt.day,
                "sido": sido,
                "sigungu": sigungu,
                "sigungu_code": sgg_cd,
                "umd_name": "중앙동",
                "apt_name": apt_name,
                "exclusive_area": area,
                "pyeong": pyeong,
                "pyeong_category": pyeong_category,
                "floor": floor,
                "build_year": build_year,
                "deal_amount": deal_amount,
                "pyeong_price": pyeong_price,
                "is_cancel": is_cancel,
                "cancel_date": cancel_date,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
        return results

    def generate_and_save_ai_reports(self, days: int = 7):
        """Automatically generate and save Gemini AI analyst reports for recent dates."""
        available_dates = self.db.get_available_dates()
        if not available_dates:
            return

        target_dates = available_dates[:days]
        print(f"Generating and saving AI Analyst reports for recent dates: {target_dates}...")

        for dt in target_dates:
            # Check if summary already exists
            existing = self.db.get_daily_summary(dt)
            if existing:
                print(f"  - [{dt}] Cached AI report already exists. Skipping.")
                continue

            day_df = self.db.get_trades_by_date(dt, exclude_canceled=True)
            if day_df.empty:
                continue

            print(f"  - [{dt}] Generating Gemini AI report ({len(day_df)} trades)...")
            summary_text = self.analyst.generate_summary(day_df, dt)
            self.db.save_daily_summary(dt, summary_text, model_name=self.analyst.model_name)
            time.sleep(0.5)

    def collect_and_save(self, days: int = 7, use_mock: bool = False, count: int = 200) -> int:
        """Collect nationwide trade data, save to SQLite DB, and generate AI reports."""
        if use_mock or not self.api_key:
            print(f"Collecting data in MOCK mode (count={count}, days={days})...")
            trades = self.generate_mock_data(days=days, count=count)
            inserted = self.db.upsert_trades(trades)
            self.generate_and_save_ai_reports(days=days)
            return inserted
            
        target_ymds = self.get_target_deal_ymds(days=days)
        all_trades = []
        
        print(f"Collecting nationwide real trades for YMDs {target_ymds} across {len(self.lawd_codes)} regions...")
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            tasks = []
            for reg in self.lawd_codes:
                code = reg["code"]
                for ymd in target_ymds:
                    tasks.append(executor.submit(self.fetch_lawd_trades, code, ymd))
                    
            for future in as_completed(tasks):
                try:
                    items = future.result()
                    all_trades.extend(items)
                except Exception:
                    pass
                time.sleep(0.05)
                        
        if not all_trades:
            fallback_ymds = ["202409", "202408"]
            print(f"No records in {target_ymds}. Querying recent official records ({fallback_ymds}) from real API...")
            with ThreadPoolExecutor(max_workers=3) as executor:
                tasks = []
                for reg in self.lawd_codes[:60]:
                    for ymd in fallback_ymds:
                        tasks.append(executor.submit(self.fetch_lawd_trades, reg["code"], ymd))
                for future in as_completed(tasks):
                    try:
                        all_trades.extend(future.result())
                    except Exception:
                        pass
                    time.sleep(0.05)
                        
        if not all_trades:
            print("No real data returned from API. Generating fallback sample data...")
            trades = self.generate_mock_data(days=days, count=count)
            inserted = self.db.upsert_trades(trades)
            self.generate_and_save_ai_reports(days=days)
            return inserted
            
        inserted = self.db.upsert_trades(all_trades)
        print(f"[OK] Successfully collected and saved {len(all_trades)} REAL trades from Public Data API (inserted/updated: {inserted}).")

        # Automatically generate and save Gemini AI analyst reports for recent dates
        self.generate_and_save_ai_reports(days=days)
        return inserted

def main():
    parser = argparse.ArgumentParser(description="APT Daily Trade Collector")
    parser.add_argument("--days", type=int, default=7, help="Number of recent days to collect (default: 7)")
    parser.add_argument("--mock", action="store_true", help="Force mock data generation")
    parser.add_argument("--count", type=int, default=200, help="Mock data count (default: 200)")
    args = parser.parse_args()
    
    collector = AptTradeCollector()
    collector.collect_and_save(days=args.days, use_mock=args.mock, count=args.count)

if __name__ == "__main__":
    main()
