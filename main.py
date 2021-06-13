from typing import Optional
from secret import env
from fastapi import FastAPI
import uvicorn
import pymongo
from fastapi import FastAPI, HTTPException, Depends, Request, File, UploadFile,Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from fastapi_jwt_auth import AuthJWT
from fastapi_jwt_auth.exceptions import AuthJWTException
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
import json
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
mongodb_url = env.MONGODB_URL.format(username=env.USERNAME, password=env.PASSWORD)
client = pymongo.MongoClient(mongodb_url)
db=client[env.DBNAME]

class Settings(BaseModel):
    authjwt_secret_key: str = env.SECRET_KEY

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
    for i in df['trigram']:
        nodes = i.split('|')
        for node in nodes:
            if node not in node_id.keys() and len(df[df['keyword']==node])!=0:
                node_id[node] = idx
                idx+=1
    data = {'nodes':[],'links':[]}
    tmp_ids = []
    for i in df['bigram']:
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
    for i in df['trigram']:
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
    if user.username != env.ADMIN_USER or user.password != env.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="아이디와 비밀번호를 확인해주세요.")

    expires = timedelta(days=1)
    access_token = Authorize.create_access_token(subject=user.username, expires_time=expires)
    return {"access_token": access_token, "token_type": "Bearer"}

@app.get("/api/v1.0/theme")
async def get_theme(): 
    collection = db[env.COLLECTION_THEME]
    data = list(collection.find({},{'_id':0}).sort([("theme", 1)]))

    return JSONResponse(
        status_code=200,
        content= data
    )

# mongodb 에서 분석된 결과 가져오기
# @app.get("/api/v1.0/data")
# def get_analysis_data(theme:str):
#     collection = db[env.COLLECTION_ANALYSIS]
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
async def get_anaylsis_theme_data(theme:str):
    collection = db[env.COLLECTION_ANALYSIS]
    result = collection.find_one({'theme':theme},{'_id':0})
    keyword, bigram, trigram = result['data']['keyword'], result['data']['bigram'], result['data']['trigram']

    if result:
        result['analysis_date'] = result['analysis_date'].strftime('%Y-%m-%d %H:%M:%S')

    df = pd.concat([pd.DataFrame(keyword),pd.DataFrame(bigram),pd.DataFrame(trigram)],axis=1)
    df.columns = ['keyword','keyword_num','bigram','bigram_num','trigram','trigram_num']
    data = make_network_chart(df)
    result['network'] =data
    return JSONResponse(
        status_code=200,
        content= result
    )

@app.get("/api/v1.0/raw_data/{sid}/{eid}")
def get_raw_data(sid:int=0, eid:int=10,  Authorize: AuthJWT = Depends()): 
    Authorize.jwt_required()
    collection = db[env.COLLECTION_MAIN]
    result = []
    data = list(collection.find({},{'_id':0}).sort([("add_date", -1)]).skip(sid).limit(eid-sid))
    for i in data:
        convert_date = i['add_date'].strftime('%Y-%m-%d %H:%M:%S')
        result.append({
            'theme': i['theme'],
            'blog_id': i['blog_id'],
            'log_no':i['log_no'],
            'url':i['url'],
            'contents': i['contents'],
            'date': convert_date
        })

    return JSONResponse(
        status_code=200,
        content= result
    )
# raw data 삭제
@app.delete("/api/v1.0/raw_data")
def delete_raw_data(blog_id: str, log_no: str, Authorize: AuthJWT = Depends()): 
    Authorize.jwt_required()
    collection = db[env.COLLECTION_MAIN]
    collection.delete_one(
        {
            'blog_id':blog_id,
            'log_id':log_no
        })

    return JSONResponse(
        status_code=200,
        content= 'Delete Success {}  {}'.format(blog_id, log_no)
    )
@app.get("/api/v1.0/blacklist/{sid}/{eid}")
async def get_blacklist(sid:int=0, eid:int=10,  Authorize: AuthJWT = Depends()): 
    Authorize.jwt_required()
    collection = db[env.COLLECTION_BLOCK]
    data = list(collection.find({},{'_id':0}).sort([("blog", 1)]).skip(sid).limit(eid-sid))

    return JSONResponse(
        status_code=200,
        content= data
    )

@app.post("/api/v1.0/blacklist")
async def add_blacklist(blacklist: BlackList,  Authorize: AuthJWT = Depends()): 
    Authorize.jwt_required()
    collection = db[env.COLLECTION_BLOCK]
    data = collection.find_one({'blog':blacklist.blog}, upsert=True)
    if data:
        return JSONResponse(
            status_code=202,
            content= "Already exist"
        )

    return JSONResponse(
        status_code=201,
        content= "Add blacklist success id : {}".format(blacklist.blog)
    )

@app.delete("/api/v1.0/blacklist")
async def delete_blacklist(blog: str,  Authorize: AuthJWT = Depends()): 
    Authorize.jwt_required()
    collection = db[env.COLLECTION_BLOCK]
    collection.delete_one({'blog':blog})

    return JSONResponse(
        status_code=200,
        content= "Delete blacklist success id : {}".format(blog)
    )

@app.get("/api/v1.0/stopwords/{sid}/{eid}")
async def get_stopwords(sid:int=0, eid:int=10,  Authorize: AuthJWT = Depends()): 
    Authorize.jwt_required()
    collection = db[env.COLLECTION_STOPWORDS]
    data = list(collection.find({},{'_id':0}).sort([("stop", 1)]).skip(sid).limit(eid-sid))

    return JSONResponse(
        status_code=200,
        content= data
    )

@app.post("/api/v1.0/stopwords")
async def add_stopwords(stopwords: StopWords,  Authorize: AuthJWT = Depends()): 
    Authorize.jwt_required()
    collection = db[env.COLLECTION_STOPWORDS]
    collection.insert_one({'stop': stopwords.stop}, upsert=True)

    return JSONResponse(
        status_code=201,
        content= "Add success stopwords {}".format(stopwords.stop)
    )

@app.delete("/api/v1.0/stopwords")
async def delete_stopwords(stopwords: StopWords,  Authorize: AuthJWT = Depends()): 
    Authorize.jwt_required()
    collection = db[env.COLLECTION_STOPWORDS]
    collection.delete_one({'stop': stopwords.stop})

    return JSONResponse(
        status_code=200,
        content= "Delete success stopwords {}".format(stopwords.stop)
    )


if __name__ == '__main__':
    uvicorn.run("main:app", reload= True)
