# 필요 라이브러리 정의
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
import bs4
import pandas as pd
from sqlalchemy import create_engine, text
import traceback
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

#에러 handler
def handle_error(error):
    """
    예외 처리 함수: 발생한 오류의 위치(함수 이름, 라인)와 내용을 출력합니다.

    Args:
    - error (Exception): 처리할 예외 객체

    """
    tb = traceback.extract_tb(error.__traceback__)
    fileName, lineNo, functionName, text = tb[-1]
    print(f"ErrorLocation : Function Name: {functionName} Line : {lineNo}")
    print(f"Error : {error}\n")
# 데이터베이스 엔진 생성 함수
def createDB_Engine(db_info):
    engine = create_engine(f"{db_info['dbPrefix']}://{db_info['dbId']}:{db_info['dbPw']}@{db_info['dbIp']}:{db_info['dbPort']}/{db_info['dbName']}")
    return engine

# 데이터베이스에 테이블 생성
def create_table(engine,query):
    with engine.connect() as connection:
        connection.execute(text(query))
    print("테이블이 생성되었습니다.")

# 웹드라이버 셋업 함수
def setup_webdriver(osType='linux'):
    options = webdriver.ChromeOptions()
    if osType == 'linux':
        options.add_argument("--headless")  # 헤드리스 모드
    options.add_argument("window-size=1920x1080")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("start-maximized")
    options.add_argument("disable-infobars")
    options.add_argument("--disable-extensions")
    
    # User-agent 설정
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={user_agent}")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

# 페이지 로딩 및 HTML 소스 반환 함수
def load_page(driver, url):
    driver.get(url)
    driver.implicitly_wait(10)
    time.sleep(3)  # 동적으로 생성되는 요소를 위한 추가 대기
    driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.END)
    return driver.page_source

# 가게 정보 파싱 함수
def parse_store_data(pageSource):
    bsObj = bs4.BeautifulSoup(pageSource, 'html.parser')
    storeListTags = bsObj.find_all(name="li", attrs={"class": "_item _lazyImgContainer"})
    storeList = []
    
    for storeTag in storeListTags:
        placeId = storeTag.get("data-id") if storeTag.get("data-sid") is None else storeTag.get("data-sid")
        storeName = storeTag.get("data-title",None)
        storeTel = storeTag.get("data-tel",None)
        storeLat = storeTag.get("data-latitude",None)
        storeLon = storeTag.get("data-longitude",None)
        storeInfo = {
            "place_id": placeId,
            "name": storeName,
            "tel": storeTel,
            "latitude": storeLat,
            "longitude": storeLon,
            "gibun" : None,
            "addr" : None
        }

        # 주소 정보 파싱
        addressDivTag = storeTag.find(name="div", attrs={"class": "bx_address"})
        
        for addr in addressDivTag.find_all('p'):
            tempAddr = addr.get_text(strip=True)
            if '지번' in tempAddr:
                #주소가 없을경우
                storeInfo['gibun'] = tempAddr[2:]  # '지번' 이후 주소
            else:
                storeInfo['addr'] = tempAddr
                
        storeList.append(storeInfo)

    # 데이터프레임으로 변환
    df = pd.DataFrame(storeList)
    return df

# 데이터베이스에 데이터 저장 함수
def save_data(engine,df, tableName):
    try:
        # 데이터프레임을 SQL 테이블로 저장 (중복된 placeId가 있는 경우 업데이트)
         with engine.begin() as connection: #engin.begin 자동 트랜잭션
            totalRow = 0
            for index, row in df.iterrows():
                insert_query = f"""
                INSERT INTO {tableName} (place_id, name, tel, latitude, longitude, addr, gibun, search_keyword, search_sort_type)
                VALUES (:place_id, :name, :tel, :latitude, :longitude, :addr, :gibun, :search_keyword, :search_sort_type)
                ON DUPLICATE KEY UPDATE
                    name = VALUES(name),
                    tel = VALUES(tel),
                    latitude = VALUES(latitude),
                    longitude = VALUES(longitude),
                    addr = VALUES(addr),
                    gibun = VALUES(gibun),
                    search_keyword = VALUES(search_keyword),
                    search_sort_type = VALUES(search_sort_type);
                """
                try:
                    result = connection.execute(text(insert_query), row.to_dict())
                    totalRow += 1
                    # logging.info(f"Row {index}: Affected rows for place_id {row['place_id']}: {result.rowcount}")
                except Exception as e:
                    logging.error(f"Error inserting row {index}: {str(e)}")
                    logging.error(f"Problematic row data: {row.to_dict()}")
            print(f"테이블 '{tableName}' 에 총 row '{totalRow}' 데이터가 성공적으로 삽입되었습니다.")
    except Exception as e:
        print(f"테이블에 데이터 삽입 중 오류 발생: {str(e)}")

# 가게 URL 생성 함수
def get_store_url(keyword, sortVal):
    sort = {"relative": 0, "distance": 1}  # 0: 관련도순, 1: 거리순
    searchUrl = f"https://m.map.naver.com/search2/search.naver?query={keyword}&siteSort={sort[sortVal]}"
    return searchUrl


# FastAPI 애플리케이션 인스턴스 생성
app = FastAPI()
class SearchQuery(BaseModel):
    keyword: str
    sort_type: str
    
@app.get("/")
async def root():
    return {"message": "Hello from FastAPI!"}


@app.post("/search")
async def search(query: SearchQuery):
    try:
        osType = 'linux'
        driver = setup_webdriver(osType)
            # 데이터베이스 정보 설정
        dbInfo = {
            "dbPrefix": "mysql+pymysql",
            "dbId": "crawling",
            "dbPw": "cr1234",
            "dbIp": "54.180.233.91",
            "dbPort": "3306",
            "dbName": "crawling",
        }
        tableName = "store_info"
        createTablequery = """
            CREATE TABLE IF NOT EXISTS {} (
            place_id VARCHAR(255) PRIMARY KEY,
            name VARCHAR(255),
            tel VARCHAR(255),
            latitude VARCHAR(255),
            longitude VARCHAR(255),
            addr VARCHAR(255),
            gibun VARCHAR(255),
            search_keyword VARCHAR(255),
            search_sort_type VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 기본값으로 현재 시간 설정
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP  -- 업데이트 시 현재 시간으로 자동 설정
            );
        """.format(tableName)
        
        # 검색어와 정렬 조건을 사용해 URL 생성
        keyword = query.keyword
        sortType = query.sort_type
        searchUrl = get_store_url(keyword, sortType)
        
        # 페이지 로드 및 데이터 추출
        html = load_page(driver, searchUrl)
        
        df = parse_store_data(html)
        df['search_keyword'] = keyword #서칭 키워드 컬럼 추가
        df['search_sort_type'] = sortType #서칭 정렬 컬럼 추가
        
        
        # 데이터베이스 엔진 생성 및 테이블 생성
        engine = createDB_Engine(dbInfo)
        create_table(engine,createTablequery)
        
        # 추출한 데이터 저장
        save_data(engine,df, tableName)

        return {"status": "success", "message": "Data saved successfully!"}

    except Exception as e:
        handle_error(e)
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        driver.quit()

