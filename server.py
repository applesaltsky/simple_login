#pip install fastapi
#pip install python-multipart

import uvicorn
from fastapi import FastAPI, Form, Request, status, Cookie
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from uuid import uuid4
from typing import Union

class UserDB:
    '''userdata가 저장된 DB, 실제 프로덕션 상황에서는 MONGODB나 MYSQL 등으로 대체'''
    def __init__(self):
        self.DB = [
                        {

                            'username':'admin',
                            'password':'1234',
                            'authority':'admin',
                            'nickname':'administrator'
                        },
                        {
                            'username':'test',
                            'password':'1111',
                            'authority':'general',
                            'nickname':'generaluser'
                        }
                    ]

    def showAll(self):
        return self.DB

    def create(self,username,password,authority,nickname):
        new_user = {
                            'username':username,
                            'password':password,
                            'authority':authority,
                            'nickname':nickname
                        }  
        self.DB.append(new_user)
        return new_user  

    def find(self,username):
        for index,data in enumerate(self.DB):
            if username == data["username"]:
                return index
        return -1

    def get(self,username):
        for data in self.DB:
            if username == data["username"]:
                return data
        return False

    def delete(self,username):
        index = self.find(username)
        if not index == -1:
            del self.DB[index]
        return self.DB

    def verify(self,username,password):
        for data in self.DB:
            if username == data["username"] and password == data['password']:
                return True
        return False        

    def modify(self,username,password,authority,nickname):
        index = self.find(username)
        if not index == -1:
            new_user = {
                                'username':username,
                                'password':password,
                                'authority':authority,
                                'nickname':nickname
                            }  
            self.DB[index] = new_user
        return self.DB

class SessionBackend:
    '''백엔드의 session 저장소, 대충 만든 것, 실제 프로덕션 상황에서는 mysql이나 mongodb이나 redis로 대체'''
    def __init__(self):
        self.sessions = []

    def showAll(self):
        return self.sessions

    def create(self,key,value):
        self.sessions.append({key:value})
        return {key:value}

    def find(self,key):
        for index, session in enumerate(self.sessions):
            if key in session:
                return index
        return -1

    def get(self,key):
        for session in self.sessions:
            if key in session:
                return session[key]
        return False

    def delete(self,key):
        index = self.find(key)
        if not index == -1:
            del self.sessions[index]
        return self.sessions

    def modify(self,key,new_user):
        index = self.find(key)
        if not index == -1:
            self.sessions[index] = {key:new_user}
        return new_user

    def getUniqueID(self): 
        sessionID = str(uuid4())
        validSessionID = self.find(sessionID) == -1
        while validSessionID is not True:               
            sessionID = str(uuid4())
            validSessionID = self.find(sessionID) == -1
        return sessionID




app = FastAPI()
userDB = UserDB()
sessionStore = SessionBackend()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def root(request: Request,sessionID: Union[str, None] = Cookie(default=None)):
    if sessionID is None:
        response = templates.TemplateResponse("home.html",{"request": request,"loggedIn":False})
        return response

    
    session_not_exists_in_sessionStore = sessionStore.find(sessionID) == -1
    if session_not_exists_in_sessionStore:
        #backend 내 session store에 없는 sessionID를 client가 가지고 있을 경우, client의 session을 삭제
        response = templates.TemplateResponse("home.html",{"request": request,"loggedIn":False})
        response.delete_cookie('sessionID')
        return response


    userdata = sessionStore.get(sessionID)
    if userdata['loggedIn'] is False:
        #기존에 로그인 실패 기록이 있다면
        response = templates.TemplateResponse("home.html",{
                                                            "request": request,
                                                            "errormessage":"Login fail, Check your ID and password",
                                                            "loggedIn":False
                                                        }
                                            )
        return response

    nickname = userdata['nickname']
    isAdminuser = userdata['authority'] == 'admin' #관리자인가? 관리자에게만 adminpanel을 노출
    response = templates.TemplateResponse("home.html",{"request": request,"nickname":nickname,"loggedIn":True,"admin":isAdminuser})
    return response


@app.post("/login")
async def login(username: str = Form(), password: str = Form()):
    validUser = userDB.verify(username,password) 

    if validUser is False :  
        #로그인에 실패했다면, 로그인에 실패한 정보가 담긴 session을 발급하고 초기 화면으로 돌린다.
        #초기 화면에 id, pw가 잘못 되었으니 다시 확인해보라는 메시지를 출력하기 위함. 
        sessionID = sessionStore.getUniqueID()
        response = RedirectResponse(url='/', status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(key="sessionID", value=sessionID)

        userdata = {'loggedIn':False}
        sessionStore.create(key=sessionID,value=userdata)
        return response
    
    #로그인에 성공했다면
    sessionID = sessionStore.getUniqueID()
    response = RedirectResponse(url='/', status_code=status.HTTP_303_SEE_OTHER)

    #client에 sessionID가 담긴 쿠키 발행 
    response.set_cookie(key="sessionID", value=sessionID)  

    #backend 내 sessionStore에  {sessionID : 유저 정보} 쌍을 삽입
    userdata = userDB.get(username) 
    userdata['loggedIn'] = True
    sessionStore.create(key=sessionID,value=userdata)  

    #print(sessionStore.showAll())  [{'f8fd84f3-11d8-4e30-96e5-562b8a4b7760': {'username': 'admin', 'password': '1234', 'authority': 'admin', 'nickname': 'administrator', 'loggedIn': True}}]
    return response


@app.post("/logout")
async def logout(sessionID: Union[str, None] = Cookie(default=None)):
    '''client에 건네준 session과 sessionStore의 session 정보를 모두 삭제한다'''
    response = RedirectResponse(url='/', status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie('sessionID')  #client의 session 삭제
    sessionStore.delete(sessionID)       #sessionStore의 session 삭제
    return response


@app.post("/modify")
async def modify(nickname: str = Form(), sessionID: Union[str, None] = Cookie(default=None)): 
    '''수정을 할 땐 session과 db의 정보를 둘 다 수정해야 한다.'''
    #내 기존 정보 조회
    sessionUserdata = sessionStore.get(sessionID)
    username = sessionUserdata["username"]
    password = sessionUserdata["password"]

    #session 정보 수정
    sessionUserdata["nickname"] = nickname
    sessionStore.modify(sessionID,sessionUserdata)

    #db 정보 수정
    DBUserdata = userDB.get(username)
    DBUserdata["nickname"] = nickname
    userDB.modify(DBUserdata["username"],DBUserdata["password"],DBUserdata["authority"],DBUserdata["nickname"])

   
    response = RedirectResponse(url='/', status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="sessionID", value=sessionID)
    #print(sessionStore.showAll())
    return response

@app.get("/join")
async def getJoin(request: Request, sessionID: Union[str, None] = Cookie(default=None)):
    if sessionID is not None:  
        #만약 로그인 된 상태에서 url쳐서 join 화면에 들어온다면, 로그아웃 
        response = RedirectResponse(url='/join')
        response.delete_cookie('sessionID')  #client의 session 삭제
        sessionStore.delete(sessionID)       #sessionStore의 session 삭제
        return response
    response = templates.TemplateResponse("join.html",{"request": request})
    return response 

@app.post("/join") 
async def postJoin(request: Request,username: str = Form(),password1: str = Form(),password2: str = Form(),nickname: str = Form()):
    validUsername = userDB.find(username) == -1
    if validUsername is False:
        #USERNAME 중복 체크
        response = templates.TemplateResponse("join.html",{
                                                            "request": request,
                                                            "errormessage":"That username is already used."
                                                            })
        return response        
    if password1 != password2:
        #PASSWORD와 PASSWORD CONFIRM이 같아야 한다.
        response = templates.TemplateResponse("join.html",{
                                                            "request": request,
                                                            "errormessage":"Password and Password confirmed were not same."
                                                            })
        return response
    
    userDB.create(username=username,password=password1,authority='general',nickname=nickname)
    response = RedirectResponse(url='/', status_code=status.HTTP_303_SEE_OTHER)
    return response 

@app.get("/admin")
async def getAdmin(request: Request, sessionID: Union[str, None] = Cookie(default=None)):
    #admin panel은 admin user만 들어올 수 있어야 함 -> url 보호 필요. 이 부분을 middleware로 만들어도 괜찮겠다.
    if sessionID is None:
        #로그인이 안 되어 있거나
        response = RedirectResponse(url='/')
        return response

    userdata = sessionStore.get(sessionID)
    if userdata['authority'] != 'admin':
        #admin 유저가 아니면 홈 화면으로 리다이렉트.
        response = RedirectResponse(url='/')
        return response

    response = templates.TemplateResponse("admin.html",{"request": request,"userDB":userDB.showAll()})
    return response 

@app.post("/admin")
async def postAdmin(request: Request, username: str = Form()):
    userdata = userDB.get(username) 

    new_userdata = userdata.copy()
    new_userdata['authority'] = 'admin'
    userDB.modify(
                username=new_userdata['username'],
                password=new_userdata['password'],
                authority=new_userdata['authority'],
                nickname=new_userdata['nickname']
                )
    response = RedirectResponse(url='/admin', status_code=status.HTTP_303_SEE_OTHER)
    return response

uvicorn.run("__main__:app", port=4000, reload=False)

