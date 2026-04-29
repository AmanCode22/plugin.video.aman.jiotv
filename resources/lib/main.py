# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
import time
from urllib.parse import quote, urlencode

import xbmc
import xbmcgui
from codequick import Listitem, Resolver, Route, Script, run
from resources.lib.utils import (
    catchup_data,
    filterChannels,
    getCatchupUrl,
    getGenreList,
    getLanguageList,
    getLivePlayUrl,
    isLoggedin,
    jio_playheaders,
    logout,
    sendOtp,
    verifyOTP,
    _extract_cookie,
)
from resources.lib.hls_proxy import start_hls_proxy, get_hls_proxy_port, set_playback_info

_proxy_started = False

def _ensure_proxy():
    global _proxy_started
    if not _proxy_started:
        start_hls_proxy()
        _proxy_started = True

@Route.register
def root(plugin):
    result = []
    item = Listitem("video")
    item.label = "Genre Wise"
    item.set_callback(genreRoute)
    result.append(item)
    item2 = Listitem("video")
    item2.label = "Language Wise"
    item2.set_callback(languageRoute)
    result.append(item2)
    item3 = Listitem("video")
    item3.label = "Genre and Language Wise"
    item3.set_callback(langenrRoute_langPart)
    result.append(item3)
    if isLoggedin():
        logout_item = Listitem("video")
        logout_item.label = "Logout"
        logout_item.set_callback(logoutRoute)
        result.append(logout_item)
    else:
        login_item = Listitem("video")
        login_item.label = "Login(Needed for playing anything)"
        login_item.set_callback(loginRoute)
        result.append(login_item)
    return result

@Route.register
def logoutRoute(plugin):
    try:
        logout()
        Script.notify("Logout successfully!", "Redirecting after logout")
        xbmc.executebuiltin("RunPlugin(plugin://plugin.video.aman.jiotv/resources/lib/main.py?action=root)")
    except:
        Script.notify("Logout Error", "Please restart Kodi")

@Route.register
def loginRoute(plugin):
    try:
        number = str(xbmcgui.Dialog().numeric(0, "Enter jio mobile number"))
        if not number:
            return
        otp_sent = sendOtp(number)
        if otp_sent:
            Script.notify("OTP SENT", "Otp sent successfully!")
            otp = str(xbmcgui.Dialog().numeric(0, "Enter OTP"))
            if not otp:
                return
            if verifyOTP(number, otp):
                Script.notify("Login Done", "Successfully logged in.")
                xbmc.executebuiltin("ActivateWindow(Home)")
            else:
                Script.notify("Failed Login", "Unable to verify otp")
        else:
            Script.notify("Failed Login", "Failed to send OTP")
    except Exception as e:
        Script.notify("Login Error", str(e))

@Route.register
def genreRoute(plugin):
    final = []
    genres = getGenreList().values()
    for i in genres:
        item = Listitem("video")
        item.label = i
        item.set_callback(filter, type="genre", query=i)
        final.append(item)
    return final

@Route.register
def langenrRoute_langPart(plugin):
    final = []
    languages = getLanguageList().values()
    for i in languages:
        item = Listitem("video")
        item.label = i
        item.set_callback(langenrRoute_genrePart, language=i)
        final.append(item)
    return final

@Route.register
def languageRoute(plugin):
    final = []
    languages = getLanguageList().values()
    for i in languages:
        item = Listitem("video")
        item.label = i
        item.set_callback(filter, type="language", query=i)
        final.append(item)
    return final

@Route.register
def langenrRoute_genrePart(plugin, language):
    final = []
    genres = getGenreList().values()
    for i in genres:
        item = Listitem("video")
        item.label = i
        item.set_callback(filter, type="multi", query=language, query2=i)
        final.append(item)
    return final

@Route.register
def filter(plugin, type, query, query2=""):
    filtered_data = filterChannels(type, query, query2)
    final_data = []
    for i in filtered_data:
        item = Listitem("video")
        item.label = i["channel_name"]
        item.art.fanart = item.art.thumb = item.art.clearart = item.art.clearlogo = "https://jiotv.catchup.cdn.jio.com/dare_images/images/" + i["logoUrl"]
        item.art.icon = "https://jiotv.catchup.cdn.jio.com/dare_images/images/" + i["logoUrl"]
        item.set_callback(showPlayOptions, id=i["channel_id"], name=i["channel_name"], isCatchup=bool(i.get("stbCatchup", False)))
        final_data.append(item)
    return final_data

@Route.register
def showPlayOptions(plugin, id, name, isCatchup):
    if not isCatchup:
        live_item = Listitem()
        live_item.label = "Watch Live"
        live_item.set_callback(play_resolver, channel_id=id, catchup=False)
        return [live_item]
    dialog = xbmcgui.Dialog()
    opts = ["Watch Live", "Watch Catchup"]
    choice = dialog.select(name, opts)
    if choice == -1:
        return []
    elif choice == 0:
        live_item = Listitem()
        live_item.label = "Watch Live"
        live_item.set_callback(play_resolver, channel_id=id, catchup=False)
        return [live_item]
    else:
        return list_catchup_days(plugin, channel_id=id)

@Route.register
def list_catchup_days(plugin, channel_id):
    final = []
    today = Listitem("video")
    today.label = "Today's past programms"
    today.set_callback(catchup_shows_list, id=channel_id, day=0)
    final.append(today)
    for i in range(1, 8):
        item = Listitem("video")
        item.label = str(i) + " day older"
        item.set_callback(catchup_shows_list, id=channel_id, day=i * -1)
        final.append(item)
    return final

@Route.register
def catchup_shows_list(plugin, day, id):
    data = catchup_data(day, id)
    final = []
    for i in data["epg"]:
        if int(i["startEpoch"]) > time.time() * 1000:
            continue
        item = Listitem("video")
        item.label = item.info.title = i["showname"]
        start = datetime.datetime.fromtimestamp(int(i["startEpoch"]) / 1000).strftime("%I:%M %p")
        end = datetime.datetime.fromtimestamp(int(i["endEpoch"]) / 1000).strftime("%I:%M %p")
        item.info.plot = "Showtime:" + start + " - " + end
        item.art.clearart = item.art.clearlogo = "https://jiotv.catchup.cdn.jio.com/dare_images/images/" + i["episodeThumbnail"]
        item.art.fanart = item.art.icon = item.art.thumb = "https://jiotv.catchup.cdn.jio.com/dare_images/shows/" + i["episodePoster"]
        item.set_callback(play_resolver, channel_id=id, catchup=True, srno=i["srno"], showtime=i["showtime"], begin=i["startEpoch"], end=i["endEpoch"])
        final.append(item)
    return final

@Resolver.register
def play_resolver(plugin, channel_id, catchup, srno=None, showtime=None, begin=None, end=None):
    _ensure_proxy()
    try:
        if catchup:
            play_url = getCatchupUrl(channel_id, srno, begin, end, showtime)
            cookie = _extract_cookie(play_url)
            headers = jio_playheaders(cookie, channel_id, srno)
        else:
            play_url = getLivePlayUrl(channel_id)
            cookie = _extract_cookie(play_url)
            headers = jio_playheaders(cookie, channel_id, "250623144006")
        if not play_url:
            Script.notify("Error", "Failed to get stream URL")
            return None
        
        set_playback_info({
            'channel_id': channel_id,
            'is_catchup': catchup,
            'srno': srno,
            'showtime': showtime,
            'begin': begin,
            'end': end
        })
        
        port = get_hls_proxy_port()
        proxy_url = "http://127.0.0.1:" + str(port) + "/" + quote(play_url, safe="")
        
        header_str = urlencode(headers, quote_via=quote)
        
        final = Listitem()
        final.label = plugin._title if hasattr(plugin, '_title') else "JioTV"
        final.set_path(proxy_url + "|" + header_str)
        final.property["isPlayable"] = True
        final.property["inputstream"] = "inputstream.adaptive"
        final.property["inputstream.adaptive.stream_headers"] = urlencode(headers)
        final.property["inputstream.adaptive.manifest_headers"] = urlencode(headers)
        final.property["inputstream.adaptive.stream_selection_type"] = "ask-quality"
        if not catchup:
            final.property["IsLive"] = "true"
        return final
    except Exception as e:
        Script.notify("Play Error", str(e))
        return None
