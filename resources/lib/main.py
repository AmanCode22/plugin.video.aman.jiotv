# -*- coding: utf-8 -*-
from __future__ import unicode_literals


from codequick import Route, run, Listitem, Resolver, Script
from resources.lib.utils import isLoggedin,logout,sendOtp,verifyOTP, getGenreList, getLanguageList,filterChannels, getCatchupUrl,catchup_data ,jio_playheaders,getLivePlayUrl
import xbmc
from xbmcgui import Dialog
from urllib.parse import urlencode
import datetime
import time


@Route.register
def root(plugin):
         result=[]
         item=Listitem()
         item.label="Genre Wise"
         item.set_callback(genreRoute)
         result.append(item)
         item2=Listitem()
         item2.label="Language Wise"
         item2.set_callback(languageRoute)
         result.append( item2)
         item3=Listitem()
         item3.label="Genre and Language Wise"
         item3.set_callback(langenrRoute_langPart)
         result.append(item3)
         if isLoggedin():
         	logout_item=Listitem()
         	logout_item.label="Logout"
         	logout_item.set_callback(logoutRoute)
         	result.append(logout_item)
         else:
         	login_item=Listitem()
         	login_item.label="Login(Needed for playing anything)"
         	login_item.set_callback(loginRoute)
         	result.append(login_item)
         return result
        
@Route.register
def logoutRoute(plugin):
	logout()
	Script.notify("Logout successfully!","Redirecting after logout")
	xbmc.executebuiltin('RunPlugin(plugin://plugin.video.aman.jiotv/resources/lib/main.py?action=root)')

@Route.register
def loginRoute(plugin):
	number=str(Dialog().numeric(0,"Enter jio mobile number"))
	otp_sent=sendOtp(number)
	if otp_sent:
		Script.notify("OTP SENT","Otp sent successfully!")
		otp=str(Dialog().numeric(0,"Enter OTP"))
		otp_verify=verifyOTP(number,otp)
		if otp_verify:
			Script.notify("Login Done","Successfully logged in.")
			xbmc.executebuiltin('ActivateWindow(Home)')
		else:
			Script.notify("Failed Login","Unable to verify otp")
			xbmc.executebuiltin('ActivateWindow(Home)')
	else:
		Script.notify("Failed Login","Failed to send OTP. Non jio number or invalid number")
		xbmc.executebuiltin('ActivateWindow(Home)')
		
		
@Route.register
def genreRoute(plugin):
	final=[]
	genres=getGenreList().values()
	for i in genres:
		item=Listitem()
		item.label=i
		item.set_callback(filter,type="genre",query=i)
		final.append(item)
	return final

@Route.register
def langenrRoute_langPart(plugin):
	final=[]
	languages=getLanguageList().values()
	for i in languages:
		item=Listitem()
		item.label=i
		item.set_callback(langenrRoute_genrePart,language=i)
		final.append(item)
	return final
	
@Route.register
def languageRoute(plugin):
	final=[]
	languages=getLanguageList().values()
	for i in languages:
		item=Listitem()
		item.label=i
		item.set_callback(filter,type="language",query=i)
		final.append(item)
	return final

@Route.register
def langenrRoute_genrePart(plugin,language):
	final=[]
	genres=getGenreList().values()
	for i in genres:
		item=Listitem()
		item.label=i
		item.set_callback(filter,type="multi",query=language,query2=i)
		final.append(item)
	return final
	
@Route.register
def filter(plugin,type,query,query2=""):
	filtered_data=filterChannels(type,query,query2)
	final_data=[]
	for i in filtered_data:
		item=Listitem()
		item.label=i["channel_name"]
		item.art.fanart=item.art.thumb=item.art.clearart=item.art.clearlogo="https://jiotv.catchup.cdn.jio.com/dare_images/images/"+i["logoUrl"]
		item.art.icon="https://jiotv.catchup.cdn.jio.com/dare_images/images/"+i["logoUrl"]
		item.set_callback(showPlayOptions,id=i["channel_id"],isCatchup=bool(i["stbCatchup"]))
		final_data.append(item)
	return final_data
	
@Route.register
def showPlayOptions(plugin,id,isCatchup):
	live=Listitem()
	live.label="Watch Live"
	live.set_callback(play,id=id,catchup=False)
	if isCatchup:
		catchup=Listitem()
		catchup.label="Watch Older Shows Catchup"
		catchup.set_callback(list_catchup_days,id=id)
		return [live,catchup]
	return [live]
	
@Route.register
def list_catchup_days(plugin,id):
	final=[]
	today=Listitem()
	today.label="Today's past programms"
	today.set_callback(catchup_shows_list,id=id,day=0)
	final.append(today)
	for i in range(1,8):
		item=Listitem()
		item.label=str(i)+" day older"
		item.set_callback(catchup_shows_list,id=id,day=i*-1)
		final.append(item)
	return final 
	
@Route.register
def catchup_shows_list(plugin,day,id):
	data=catchup_data(day,id)
	final=[]
	for i in data["epg"]:
		if int(i["startEpoch"])>time.time()*1000:
			continue
		item=Listitem()
		item.label=item.info.title=i["showname"]
		item.info.plot="Showtime:"+datetime.datetime.fromtimestamp((int(i["startEpoch"]))/1000).strftime("%I:%M %p")+" - "+datetime.datetime.fromtimestamp((int(i["endEpoch"]))/1000).strftime("%I:%M %p")
		item.art.clearart=item.art.clearlogo="https://jiotv.catchup.cdn.jio.com/dare_images/images/"+i["episodeThumbnail"]
		item.art.fanart=item.art.icon=item.art.thumb="https://jiotv.catchup.cdn.jio.com/dare_images/shows/"+i["episodePoster"]
		item.set_callback(play,id=id,catchup=True,srno=i["srno"],showtime=i["showtime"],begin=i["startEpoch"],end=i["endEpoch"])
		final.append(item)
	return final 

@Resolver.register
def play(plugin,id,catchup,srno=None, showtime=None,begin=None,end=None):
	if catchup:
		play_url= getCatchupUrl(id,srno, begin,end,showtime)
		cookies_part=play_url.split("?")[1]
		if "bpk-tv" in cookies_part:
			cookie = '_' + cookies_part.split('&_')[1]
		elif "/HLS/" in cookies_part:
			cookie = '_' + cookies_part.split('&_')[1]
		else:
			cookie=cookies_part
		headers=jio_playheaders(cookie,id,srno)
		final=Listitem()
		final.label=plugin._title
		final.set_callback(play_url+"|verifypeer=false")
		final.property["isPlayable"]=True
		final.property["inputstream"]="inputstream.adaptive"
		final.property["inputstream.adaptive.stream_headers"]=urlencode(headers)
		final.property["inputstream.adaptive.manifest_headers"]=urlencode(headers)
		final.property["inputstream.adaptive.manifest_type"]="hls"
		final.property["inputstream.adaptive.license_type"]="drm"
		final.property["inputstream.adaptive.license_key"]="|" + urlencode(headers) + "|R{SSM}|"
		return final 
	else:
		play_url=getLivePlayUrl(id)
		cookies_part=play_url.split("?")[1]
		if "bpk-tv" in cookies_part:
			cookie = '_' + cookies_part.split('&_')[1]
		elif "/HLS/" in cookies_part:
			cookie = '_' + cookies_part.split('&_')[1]
		else:
			cookie=cookies_part
		headers=jio_playheaders(cookie,id,"250623144006")
		final=Listitem()
		final.label=plugin._title
		final.set_callback(play_url+"|verifypeer=false")
		final.property["isPlayable"]=True
		final.property["inputstream"]="inputstream.adaptive"
		final.property["inputstream.adaptive.stream_headers"]=urlencode(headers)
		final.property["inputstream.adaptive.manifest_headers"]=urlencode(headers)
		final.property["inputstream.adaptive.manifest_type"]="hls"
		final.property["inputstream.adaptive.license_type"]="drm"
		final.property["inputstream.adaptive.license_key"]="|" + urlencode(headers) + "|R{SSM}|"
		return final
