from typing import Optional
import os
from fastapi import FastAPI
import uvicorn
import pymongo
from fastapi import FastAPI, HTTPException, Depends, Request, File, UploadFile,Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from datetime import datetime,timezone, timedelta
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
mongodb_url = os.environ['MONGODB_URL']
client = pymongo.MongoClient(mongodb_url)
db=client[os.environ['DBNAME']]

class Settings(BaseModel):
    authjwt_secret_key: str = os.environ['SECRET_KEY']

@AuthJWT.load_config
def get_config():
    return Settings()


@app.exception_handler(AuthJWTException)
def authjwt_exception_handler(request: Request, exc: AuthJWTException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )

class User(BaseModel):
    username: str
    password: str

class BlackList(BaseModel):
    blog: str

class StopWords(BaseModel):
    stop: str

cmap = ['rgb(219, 94, 86)', 'rgb(184, 219, 86)', 'rgb(86, 219, 147)', 'rgb(86, 131, 219)', 'rgb(200, 86, 219)']
def make_network_chart(df):
    global cmap
    node_id = {}
    idx=1
    for i in df['bigram'].dropna():
        nodes = i.split('|')
        for node in nodes:
            if node not in node_id.keys() and len(df[df['keyword']==node])!=0:
                node_id[node] = idx
                idx+=1
    for i in df['trigram'].dropna():

        nodes = i.split('|')
        for node in nodes:
            if node not in node_id.keys() and len(df[df['keyword']==node])!=0:
                node_id[node] = idx
                idx+=1
    data = {'nodes':[],'links':[]}
    tmp_ids = []
    for i in df['bigram'].dropna():
        nodes = i.split('|')
        for inode in nodes:
            try:
                node = {'id':node_id[inode],'name':inode, '_color':cmap[int(node_id[inode]/20)]}
                
                if node not in data['nodes']:
                    data['nodes'].append(node)
                tmp_ids.append(node_id[inode])
            except Exception:
                continue
        try:
            data['links'].append({'sid': tmp_ids[0], 
                                'tid': tmp_ids[1],
                                '_color': 'black',
                                    '_svgAttrs': {
                                        'stroke-width': 2,
                                        'opacity': 1
                                    }}
            )
        except Exception:
            pass
        tmp_ids = []
    tmp_ids = []
    for i in df['trigram'].dropna():
        nodes = i.split('|')
        for inode in nodes:
            try:
                node = {'id':node_id[inode],'name':inode, '_color':cmap[int(node_id[inode]/20)]}
                
                if node not in data['nodes']:
                    data['nodes'].append(node)
                tmp_ids.append(node_id[inode])
            except Exception:
                continue
        try:
            data['links'].append({'sid': tmp_ids[0], 
                                'tid': tmp_ids[1],
                                '_color': 'black',
                                    '_svgAttrs': {
                                        'stroke-width': 2,
                                        'opacity': 1
                                    }
                                }
            )
        except Exception:
            pass
        tmp_ids = []
    return data
## login API endpoint
@app.post('/api/v1.0/login')
async def login(user: User, Authorize: AuthJWT = Depends()):
    if user.username != os.environ['ADMIN_USER'] or user.password != os.environ['ADMIN_PASSWORD']:
        raise HTTPException(status_code=401, detail="아이디와 비밀번호를 확인해주세요.")

    expires = timedelta(days=1)
    access_token = Authorize.create_access_token(subject=user.username, expires_time=expires)
    return {"access_token": access_token, "token_type": "Bearer"}

@app.get("/api/v1.0/theme")
async def get_theme(): 
    collection = db[os.environ['COLLECTION_THEME']]
    data = list(collection.find({},{'_id':0}).sort([("theme", 1)]))

    return JSONResponse(
        status_code=200,
        content= data
    )

# mongodb 에서 분석된 결과 가져오기
# @app.get("/api/v1.0/data")
# def get_analysis_data(theme:str):
#     collection = db[COLLECTION_ANALYSIS]
#     result = []

#     data = list(collection.find({},{'_id':0}).sort([("analysis_date", -1)]))
#     for i in data:
#         convert_date = i['analysis_date'].strftime('%Y-%m-%d %H:%M:%S')
#         result.append({
#             'theme': i['theme'],
#             'data': i['data'],
#             'date': convert_date
#         })

#     return JSONResponse(
#         status_code=200,
#         content= result
#     )

@app.get("/api/v1.0/data")
async def get_anaylsis_theme_data(theme:str, date:str):
    collection = db[os.environ['COLLECTION_ANALYSIS']]
    year,month,day = date.split('-')
    convert_date = datetime(int(year),int(month),int(day),23,59)
    result = collection.find_one({'theme':theme, 'start_date':{'$gte': datetime(int(year),int(month),int(day),0,0),'$lte':convert_date}},{'_id':0}, sort=[('start_date', -1)])
    keyword, bigram, trigram = result['data']['keyword'], result['data']['bigram'], result['data']['trigram']

    if result:
        result['start_date'] = result['start_date'].strftime('%Y-%m-%d %H:%M:%S')
        result['end_date'] = result['end_date'].strftime('%Y-%m-%d %H:%M:%S')
    else:
        return JSONResponse(
        status_code=401,
        content= None
    )

    df = pd.concat([pd.DataFrame(keyword),pd.DataFrame(bigram),pd.DataFrame(trigram)],axis=1)
    df.columns = ['keyword','keyword_num','bigram','bigram_num','trigram','trigram_num']
    data = make_network_chart(df)
    result['network'] =data
    return JSONResponse(
        status_code=200,
        content= result
    )
@app.get("/api/v1.0/best")
async def get_best_data( date:str):
    collection = db[os.environ['COLLECTION_ANALYSIS']]
    year,month,day = date.split('-')
    convert_date = datetime(int(year),int(month),int(day),23,59)
    # year,month,day = date.split('-')
    result = collection.find({'proposal':True,'start_date':{'$gte': datetime(int(year),int(month),int(day),0,0),'$lte':convert_date}},
                            {'_id':0,'data':0,'proposal':0, 'start_date':0, 'end_date':0}, 
                            sort=[('start_date', -1)])


    if result:
        # result['start_date'] = result['start_date'].strftime('%Y-%m-%d')
        # result['end_date'] = result['end_date'].strftime('%Y-%m-%d')
        return JSONResponse(
            status_code=200,
            content= result
        )
    else:
        return JSONResponse(
        status_code=401,
        content= None
    )


    


if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0",reload= True)
