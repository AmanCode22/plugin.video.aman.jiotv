from calendar import c
import requests 
import json
import os
import datetime
import uuid
import time
from codequick.storage import PersistentDict
from codequick import Script
import base64
import secrets

TOKEN_EXPIRY=7000


def refreshToken():
	with PersistentDict("localdb") as db:
		creds=db["creds"]
		
	ref_TokenApi = "https://auth.media.jio.com/tokenservice/apis/v1/refreshtoken?langId=6";
	ref_TokenPost = '{"appName":"RJIL_JioTV","deviceId":"'+creds['deviceId']+'","refreshToken":"'+creds['refreshToken']+'"}'
	ref_TokenHeads ={
      "accesstoken":creds['authToken'],
      "uniqueId": creds['sessionAttributes']['user']['unique'],
      "devicetype":"phone",
      "versionCode":"389",
      "os":"android",
      "Content-Type":"application/json"
    }
	data=requests.post(ref_TokenApi,headers=ref_TokenHeads,data=ref_TokenPost).json()
	creds["authToken"]=data["authToken"]
	with PersistentDict("localdb") as db: 
		db["creds"]=creds
		db["exp"]=time.time()+TOKEN_EXPIRY
	return creds

def isLoggedin():
	with PersistentDict ("localdb") as db:
		if db.get("creds"):
			return True
	return False
	
def getCreds():
	with PersistentDict("localdb") as db:
		if time.time()-db.get("exp")>=TOKEN_EXPIRY:
			Script.notify("Login Refresh","Refreshing token, old one expired..........")
			return refreshToken()
		return db.get("creds")
	

def convertEpoch(epoch):
	date=datetime.datetime.fromtimestamp(int(epoch)/1000,datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
	return date
	

def getCatchupUrl(id,srno, begin,end,showtime):
	creds=getCreds()
	print(creds)
	device_id=creds["deviceId"]
	crm=creds["sessionAttributes"]["user"]["subscriberId"]
	unique_id=creds["sessionAttributes"]["user"]["unique"]
	access_token=creds["authToken"]
	url = "https://jiotvapi.media.jio.com/playback/apis/v1.1/geturl?langId=6"
	payload = {
	  'stream_type': "Catchup",
	  'channel_id': str(id),
	  'programId': str(srno),
	  'showtime': str(showtime).replace(":",""),
	  'srno': datetime.datetime.strptime(str(srno)[:6], "%y%m%d").strftime("%Y%m%d"),
	  'begin': convertEpoch(begin),
	  'end': convertEpoch(end)
	}
	
	headers = {
	  'User-Agent': "okhttp/4.11.0",
	  'Accept-Encoding': "gzip",
	  'appkey': "NzNiMDhlYzQyNjJm",
	  'devicetype': "phone",
	  'os': "android",
	  'deviceid': str(device_id),
	  'osversion': "10",
	  'dm': "Xiaomi Redmi 6",
	  'uniqueid': unique_id,
	  'usergroup': "tvYR7NSNn7rymo3F",
	  'languageid': "6",
	  'userid': crm,
	  'sid': "aeb95677-5610-46ed-998e-fc572c9f",
	  'crmid': crm,
	  'isott': "true",
	  'channel_id': str(id),
	  'langid': "",
	  'camid': "",
	  'm-rating': "100",
	  'accesstoken': access_token,
	  'subscriberid': crm,
	  'lbcookie': "1",
	  'versioncode': "389",
	  "content-length":str(len(payload)),
	
	}
	print(headers)
	response = requests.post(url, data=payload, headers=headers).json()
	print(response)
	return response["result"]
	
def jio_playheaders(cookie,channel_id,srno):
	creds=getCreds()
	access_token=creds["authToken"]
	device_id=creds["deviceId"]
	crm=creds["sessionAttributes"]["user"]["subscriberId"]
	ssoToken=creds["ssoToken"]
	unique_id=creds["sessionAttributes"]["user"]["unique"]
	userid=creds["sessionAttributes"]["user"]["uid"]
	return {
	  'User-Agent': "plaYtv/7.1.7 (Linux;Android 10) AndroidXMedia3/1.1.1",
	  'Accept-Encoding': "gzip, deflate",
	  'os': "android",
	  'appname': "RJIL_JioTV",
	  'subscriberid': "7393928868",
	  'accesstoken':access_token,
	  'deviceid':device_id ,
	  'userid': userid,
	  'versioncode': "389",
	  'devicetype': "phone",
	  'crmid': crm,
	  'osversion': "10",
	  'srno': srno,
	  'usergroup': "tvYR7NSNn7rymo3F",
	  'x-platform': "android",
	  'uniqueid': unique_id,
	  'ssotoken': ssoToken,
	  'channelid': str(channel_id),
	  'priority': "u=1, i",
	  'Cookie': cookie
	}

def sendOtp(number):
	number="+91"+number
	b64_number=base64.b64encode(number.encode()).decode()
	url = "https://jiotvapi.media.jio.com/userservice/apis/v1/loginotp/send?langId=6"
	payload = {
	  "number": b64_number
	}
	headers = {
	  'User-Agent': "okhttp/4.11.0",
	  'Accept-Encoding': "gzip",
	  'Content-Type': "application/json",
	  'appname': "RJIL_JioTV",
	  'os': "android",
	  'm-rating': "100",
	  'devicetype': "phone",
	  'content-type': "application/json; charset=utf-8"
	}
	response = requests.post(url, json=payload, headers=headers)
	if response.text.strip()=="":
		return True
	return False
		
def verifyOTP(number,otp):
	number="+91"+number
	b64_number=base64.b64encode(number.encode()).decode()
	verify_url = "https://jiotvapi.media.jio.com/userservice/apis/v2/loginotp/verify?langId=6"
	verify_payload = {
	  "number": b64_number,
	  "otp": otp,
	  "deviceInfo": {
	    "consumptionDeviceName": "xiaomi Redmi 6",
	    "info": {
	      "type": "android",
	      "platform": {
	        "name": "cereus"
	      },
	      "androidId": f"{secrets.randbits(64):016x}"
	    }
	  }
	}
	verify_headers = {
	  'User-Agent': "okhttp/4.11.0",
	  'Accept-Encoding': "gzip",
	  'Content-Type': "application/json",
	  'appname': "RJIL_JioTV",
	  'os': "android",
	  'm-rating': "100",
	  'devicetype': "phone",
	  'content-type': "application/json; charset=utf-8"
	}
	verify_response = requests.post(verify_url, json=verify_payload, headers=verify_headers).json()
	if verify_response.get("data",{})=={}:
		Script.notify("Login Failed invalid otp.")
		return False
	with PersistentDict("localdb") as db:
		db["creds"]=verify_response["data"]
		db["exp"]=time.time()+TOKEN_EXPIRY
	return True
	
def logout():
	with PersistentDict("localdb") as db:
		del db["creds"]
		del db["exp"]
	return True
	
	
def getGenreList():
	return {
	  "5": "Entertainment",
	  "6": "Movies",
	  "7": "Kids",
	  "8": "Sports",
	  "9": "Lifestyle",
	  "10": "Infotainment",
	  "11": "Religious",
	  "12": "News",
	  "13": "Music",
	  "14": "Regional",
	  "15": "Devotional",
	  "16": "Business News",
	  "17": "Educational",
	  "18": "Shopping",
	  "19": "Jio Darshan"
	}
#	with PersistentDict("localdb") as db:
#		if not db.get("genreList"):
#			api_data=json.loads(requests.get("https://jiotvapi.cdn.jio.com/apis/v1.3/dictionary/dictionary?langId=6",headers={"user-agent":"okhttp/4.11.0"}).content.decode("utf-8-sig"))
#			db["genreList"]=api_data["languageIdMapping"]
#			db["languageList"]=api_data["epgLanguageList"]
#			return api_data["epgGenreList"]
#		return db["genreList"]
		
def getLanguageList():
	return {
	  "1": "Hindi",
	  "2": "Marathi",
	  "3": "Punjabi",
	  "4": "Urdu",
	  "5": "Bengali",
	  "6": "English",
	  "7": "Malayalam",
	  "8": "Tamil",
	  "9": "Gujarati",
	  "10": "Odia",
	  "11": "Telugu",
	  "12": "Bhojpuri",
	  "13": "Kannada",
	  "14": "Assamese",
	  "15": "Nepali",
	  "16": "French"
	}
#	with PersistentDict("localdb") as db:
#		if not db.get("languageList"):
#			api_data=json.loads(requests.get("https://jiotvapi.cdn.jio.com/apis/v1.3/dictionary/dictionary?langId=6",headers={"user-agent":"okhttp/4.11.0"}).content.decode("utf-8-sig"))
#			db["genreList"]=api_data["channelCategoryMapping"]
#			db["languageList"]=api_data["epgLanguageList"]
#			return api_data["epgLanguageList"]
#		return db["languageList"]
		
		
def getChannelList():
	with PersistentDict("localdb") as db:
		if not db.get("channelList"):
			channels=requests.get("https://jiotvapi.cdn.jio.com/apis/v3.1/getMobileChannelList/get/?langId=6&os=android&devicetype=phone&usertype=guest&version=389&langId=6",headers={"user-agent":"okhttp/4.11.0"}).json()
			db["channelList"]=channels["result"]
			return channels["result"]
		return db["channelList"]

def filterChannels(type,query, query2=""):
	channelList=getChannelList()
	if type=="genre":
		finals=[]
		genres=getGenreList()
		for i in channelList:
			if str(i["channelCategoryId"]) not in genres.keys():
				continue
			if genres[str(i["channelCategoryId"])]==query:
				finals.append(i)
	elif type=="language":
		finals=[]
		languages=getLanguageList()
		for i in channelList:
			if str(i["channelLanguageId"]) not in languages.keys():
				continue
			if languages[str(i["channelLanguageId"])]==query:
				finals.append(i)
	else:
		finals=[]
		genres=getGenreList()
		languages=getLanguageList()
		for i in channelList:
			if str(i["channelCategoryId"]) not in genres.keys():
				continue
			if str(i["channelLanguageId"]) not in languages.keys():
				continue
			if languages[str(i["channelLanguageId"])]==query and genres[str(i["channelCategoryId"])]==query2:
				finals.append(i)
	return finals
	
def catchup_data(day,id):
	return requests.get(f"https://jiotvapi.cdn.jio.com/apis/v1.3/getepg/get?offset={day}&channel_id={id}&langId=6",headers={"user-agent":"okhttp/4.11.0"}).json()

def getLivePlayUrl(id):
    creds=getCreds()
    
    url = "https://jiotvapi.media.jio.com/playback/apis/v1.1/geturl?langId=6"
    payload = {
		'stream_type': "Seek",
		'channel_id': str(id),
	}
    headers = {
	'User-Agent': "okhttp/4.11.0",
	'Accept-Encoding': "gzip",
	'appkey': "NzNiMDhlYzQyNjJm",
	'devicetype': "phone",
	'os': "android",
	'deviceid': creds['deviceId'],
	'osversion': "10",
	'dm': "Xiaomi Redmi 6",
	'uniqueid': creds['sessionAttributes']['user']['unique'],
	'usergroup': "tvYR7NSNn7rymo3F",
	'languageid': "6",
	'userid':creds['sessionAttributes']['user']['subscriberId'],
	'crmid': creds['sessionAttributes']['user']['subscriberId'],
	'isott': "false",
	'channel_id': str(id),
	'langid': "",
	'camid': "",
	'm-rating': "100",
	'accesstoken': creds['authToken'],
	'subscriberid': ""+creds['sessionAttributes']['user']['subscriberId'],
	'lbcookie': "1",
	'versioncode': "389"
	}
    response = requests.post(url, data=payload, headers=headers).json()
    return response["result"]
    

    
    





