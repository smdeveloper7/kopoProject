#!/usr/bin/env python
# coding: utf-8

# ## 라이브러리 불러오기

# In[2]:


#판다스 생성
import pandas as pd 

#engine생성
from sqlalchemy import create_engine,types

# engin 에러처리
from sqlalchemy.exc import OperationalError

#파일 읽어오기
import os


# ## 1.파라미터 테이블 조회

# In[3]:


#try exception 에러처리 class
class NoDBServerError(Exception):
    def __init__(self, *messages):
        self.messages = messages
        super().__init__(self.messages)


# In[4]:


def useDBServer(dbList):
    """
        사용할 dbServer확인
    """
    
    for num in range(len(dbList)):
        dbServer = dbList.loc[num].dbServer
        if dbList.loc[num].dbServer == 'oracle':
           pass
        elif dbList.loc[num].dbServer == 'postgre':
           pass
        elif dbList.loc[num].dbServer == 'mariadb':    
           pass
        elif dbList.loc[num].dbServer == 'mysql':    
           pass 
        else:
            print(f"row {dbList.loc[num]['index']} 지원하지 않는 db형식 : {dbList.loc[num].dbServer}")
            dbList.drop(num, inplace=True) #지원하지않는 row 형식 삭제
    return dbList


# In[5]:


## 파라미터 테이블 제작 함수
def makeParamTable(folder_path,file_path):
    """
    파라미터 테이블이 존재하지않을때 함수호출후 제작
    """
    # 주어진 정보를 리스트로 저장
    type=["filePath","db","db","db","db"]
    dbServer = ["","oracle", "postgre","mariadb","mysql"]
    dbPrefix = ["","oracle+cx_oracle", "postgresql", "mysql+pymysql","mysql"]
    dbId = ["","root", "root", "root","root"]
    dbPw = ["","example", "example", "example","example"]
    dbIp = ["","example", "example", "example","example"]
    dbPort = ["","1521", "5432", "3306","3306"]
    dbName = ["","orcl", "postgre", "mariadb","mysql"]
    etcValue = ["Please folderPath Input Here.","","","",""]
    # 리스트로 데이터프레임 생성
    data = {
        "type":type,
        "dbServer":dbServer,
        "dbPrefix": dbPrefix,
        "dbId": dbId,
        "dbPw": dbPw,
        "dbIp": dbIp,
        "dbPort": dbPort,
        "dbName": dbName,
        "etcValue":etcValue #filePath일때는 경로입력
    }
    # 	dbServer	dbPrefix	dbId	dbPw	dbIp	dbPort	dbName	etcValue	use_yn

    
    df = pd.DataFrame(data)
    df['use_yn'] = 'N'
    
    
    # 폴더 경로
    # folder_path = "../param2/"
    
    # 폴더가 없는 경우 폴더 생성
    if not os.path.isdir(folder_path):
        os.makedirs(folder_path)
    
    
    # 파일 경로
    # file_path = "../param2/parameter_table.csv"
    file_path = folder_path + file_path
    
    # 기존 파일이 있는지 확인
    if os.path.isfile(file_path):
        # 파일이 존재하는 경우, 기존 파일에 데이터를 추가하기 위해 mode='a'로 설정하여 to_csv() 호출
        df.to_csv(file_path, mode='a', header=False, index=False)
    else:
        # 파일이 존재하지 않는 경우, 새로운 파일로 생성
        df.to_csv(file_path, index=False)

    return file_path+" 경로에 파라미터 테이블 제작 완료"


# In[32]:


#필요한 엔진 생성
def createDB_Engine(eachDB):
    try:
        dbPrefix = eachDB.dbPrefix
        dbId = eachDB.dbId
        dbPw = eachDB.dbPw
        dbIp = eachDB.dbIp         
        dbPort = eachDB.dbPort
        dbName = eachDB.dbName
        engine = create_engine(f"{dbPrefix}://{dbId}:{dbPw}@{dbIp}:{dbPort}/{dbName}")
        return engine
    except OperationalError as e:
        return None
    except Exception as e:
        return None    
    return engine


# In[15]:


def csvToTable(folderPath, engine):
    """
    folderPath : 경로
    engine: 사용하는 엔진
    """
    # 경로있는지 체크
    result = False #테이블 하나라도 복사완료 했는지 체크
    extensionList = [".csv"]
    encodingList = ["utf-8", "cp949", "ms949","euc-kr"]
    errorActive = False #예외로그 확인 boolean

    #folderPath 마지막자리에 / 들어가는지 확인
    if folderPath[-1] !='/':
        folderPath += '/'

    #지워도 되는 코드이긴함
    if not os.path.exists(folderPath):
        print(folderPath + " 경로가 존재하지않습니다.")
        return None
    else:

        lists = os.listdir(folderPath)

        #파일이 없는 경우 지금은 None으로 처리하고있다.
        if len(lists) == 0:
            return None
        
        # 폴더내의 리스트
        for eachFile in lists:
            tableName, extension = os.path.splitext(eachFile)
            
            #오라클 대문자일때 replace가 안되는 경우가 발생해서 전체 테이블이름 소문자로 변환
            tableName = tableName.lower()
            
            # 현재는 확장자를 CSV만 확인하고 있음
            if extension in extensionList:
                for encoding in encodingList:
                    try:
                        inData = pd.read_csv(folderPath + eachFile, encoding=encoding)  # csv 파일 읽기
                        objColumns = list(inData.columns)
                     
                        # db로 저장하기
                        typeDict = {}
        
                        for column in objColumns:
                            if inData[column].dtypes == 'float':
                                typeDict[column] = types.Float
                            # typeDict[column] = types.Numeric 에러발생시 이걸로 변환해보자
                            elif inData[column].dtypes == 'object':
                                typeDict[column] = types.VARCHAR(100)
        
                        rowCnt = inData.to_sql(name=tableName, if_exists="replace", con=engine, dtype=typeDict, index=False)    
                        if rowCnt > 0:result=True #복사된게 있을경우
                        print(f"{tableName}테이블 행 {rowCnt} 개 생성완료")
                        break  # 인코딩이 성공하면 반복문 종료
                    except Exception as e:
                        if errorActive:
                            print(e)
            else:
                pass
        return result
                


# In[51]:


try:
    #파라미터 테이블 경로
    paramfolderPath = "../param/"
    paramfilePath = "parameter_table.csv"

    #파라미터 테이블 조회
    param = pd.read_csv(paramfolderPath+paramfilePath)
    dbList = param.loc[(param.use_yn == 'Y')&(param.type=='db')].reset_index()

    ##타입 통합
    ## object 타입의 컬럼들을 str 타입으로 변경
    object_columns = dbList.select_dtypes(include=['object']).columns
    dbList[object_columns] = dbList[object_columns].astype(str)
    dbList['dbPort'] = dbList['dbPort'].astype(int)

    
    #사용할 db확인,파라미터 테이블내에서 사용할 db 없으면 종료
    dbList = useDBServer(dbList) 
    if len(dbList) == 0:
       raise NoDBServerError("(ERROR101) 이관시킬 데이터베이스가 없습니다.")

    # 디렉토리 조회
    dirs = list(param.loc[(param.type =='filePath')&(param.use_yn == 'Y')&(~param.etcValue.isnull())]['etcValue'])
  
    Ndirs = list(param.loc[(param.type =='filePath')&(param.use_yn == 'N')&(~param.etcValue.isnull())]['etcValue']) ##use_Yn='N'인 filePath
    try:
        if len(dirs) == 0:
            if len(Ndirs) == 0:
                raise NoDBServerError("(ERROR102)디렉토리 경로가 존재하지 않습니다.")
            else:
                raise NoDBServerError("(ERROR103) use_yn = 'Y'인 failPath가 없습니다.")
        else:
            pass
        ##todo 추후에 설정된 디렉토리가 없을경우 테이블만드는걸로 바꿀예정

        #데이터 이관
        for num in range(len(dbList)):
            #엔진검사
            engine = createDB_Engine(dbList.loc[num])
            ##엔진이 존재할때
            if engine is not None:
                print(dbList.loc[num].dbServer+" 서버")
                copyOfTableYn = False
                for i in range(len(dirs)):
                    ##엔진도 존재하고 해당 디렉토리가 있을경우
                    if os.path.exists(dirs[i]):
                        result = csvToTable(dirs[i],engine)
                        ##복사된게 하나도 없으면
                        if not result:
                            print("(ERROR104)복사된 테이블이 없습니다.")
                    else:
                        #etcValue에 값과 실제 디렉토리가 다른경우
                        print("(ERROR102)디렉토리 경로가 존재하지 않습니다.")
            else:
                print("(ERROR105)아래 데이터베이스 엔진을 생성하는데 문제가 있습니다.")
                print(dbList.loc[num])
    except NoDBServerError as e:
          print(e)
    except Exception as e:
          print(e)    

    

except FileNotFoundError as e:
    print("파라미터 테이블이 존재하지않습니다.")
    print(makeParamTable(paramfolderPath,paramfilePath))                  
except NoDBServerError as e:
      print(e)
 


# In[ ]:




