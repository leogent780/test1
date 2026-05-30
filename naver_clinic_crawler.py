"""
네이버 플레이스 피부과 인스타그램 계정 수집기
- 실행 환경: 본인 PC (한국 IP 필요)
- 필요 패키지: pip install requests beautifulsoup4
- 실행: python naver_clinic_crawler.py
"""

import requests
import json
import csv
import time
import re
from urllib.parse import quote

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8',
    'Referer': 'https://map.naver.com/',
})

SEARCH_QUERIES = [
    '서울 강남 피부과',
    '서울 압구정 피부과',
    '서울 신사 피부과',
    '서울 홍대 피부과',
    '서울 이태원 피부과',
    '서울 신촌 피부과',
    '서울 종로 피부과',
    '서울 명동 피부과',
    '서울 잠실 피부과',
    '서울 건대 피부과',
    '서울 왕십리 피부과',
    '서울 노원 피부과',
    '서울 강서 피부과',
    '서울 마포 피부과',
    '경기 분당 피부과',
    '경기 일산 피부과',
    '경기 수원 피부과',
    '부산 해운대 피부과',
    '부산 서면 피부과',
    '대구 동성로 피부과',
    '인천 피부과',
    '제주 피부과',
    '대전 피부과',
    '광주 피부과',
]


def search_naver_places(query: str, start: int = 1, display: int = 50) -> list:
    """네이버 플레이스 검색 API 호출"""
    url = 'https://map.naver.com/v5/api/search'
    params = {
        'caller': 'pcweb',
        'query': query,
        'type': 'place',
        'page': start,
        'displayCount': display,
        'lang': 'ko',
    }
    try:
        r = SESSION.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        places = data.get('result', {}).get('place', {}).get('list', [])
        return places
    except Exception as e:
        print(f'  [오류] {query} 검색 실패: {e}')
        return []


def get_place_detail(place_id: str) -> dict:
    """개별 플레이스 상세 정보 (SNS 링크 포함) 조회"""
    url = f'https://map.naver.com/v5/api/sites/summary/{place_id}?lang=ko'
    try:
        r = SESSION.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f'  [오류] {place_id} 상세 조회 실패: {e}')
        return {}


def extract_instagram(detail: dict) -> str:
    """상세 정보에서 인스타그램 URL 추출"""
    # SNS 링크 필드 탐색
    sns_list = detail.get('sns', [])
    for sns in sns_list:
        url = sns.get('url', '')
        if 'instagram.com' in url:
            return url

    # 홈페이지 URL에서 인스타그램 체크
    homepage = detail.get('homepageUrl', '')
    if 'instagram.com' in homepage:
        return homepage

    # 전체 텍스트에서 정규식으로 찾기
    text = json.dumps(detail, ensure_ascii=False)
    match = re.search(r'instagram\.com/([A-Za-z0-9._]+)', text)
    if match:
        return f'https://www.instagram.com/{match.group(1)}/'

    return ''


def crawl_all(output_file: str = '피부과_인스타_전체.csv'):
    results = {}  # place_id -> info (중복 제거)

    print(f'총 {len(SEARCH_QUERIES)}개 지역 검색 시작\n')

    for query in SEARCH_QUERIES:
        print(f'[검색] {query}')
        for page in range(1, 6):  # 최대 5페이지 (50개 x 5 = 250개/지역)
            places = search_naver_places(query, start=page)
            if not places:
                break

            for place in places:
                pid = place.get('id') or place.get('placeId')
                if not pid or pid in results:
                    continue

                name = place.get('name', '')
                address = place.get('address', '')
                phone = place.get('phone', '')

                results[pid] = {
                    'id': pid,
                    'name': name,
                    'address': address,
                    'phone': phone,
                    'instagram': '',
                }

            print(f'  페이지 {page}: {len(places)}개 수집 (누적 {len(results)}개)')
            time.sleep(0.5)

            if len(places) < 50:
                break

        time.sleep(1)

    print(f'\n총 {len(results)}개 병원 수집. 인스타그램 링크 조회 시작...\n')

    # 상세 조회로 인스타그램 링크 추출
    insta_count = 0
    for i, (pid, info) in enumerate(results.items()):
        detail = get_place_detail(pid)
        insta = extract_instagram(detail)
        if insta:
            info['instagram'] = insta
            insta_count += 1
            print(f'  [{i+1}/{len(results)}] {info["name"]} → {insta}')
        else:
            if (i + 1) % 50 == 0:
                print(f'  [{i+1}/{len(results)}] 진행중...')

        time.sleep(0.3)  # 요청 간격

    # CSV 저장
    with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['name', 'address', 'phone', 'instagram', 'id'])
        writer.writeheader()
        for info in results.values():
            writer.writerow(info)

    print(f'\n완료!')
    print(f'총 병원 수: {len(results)}개')
    print(f'인스타그램 있는 병원: {insta_count}개')
    print(f'저장 위치: {output_file}')


if __name__ == '__main__':
    crawl_all()
