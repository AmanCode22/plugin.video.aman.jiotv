# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import datetime
import time
import threading
from urllib.parse import quote, urlencode

import xbmc
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
)
from xbmcgui import Dialog
from resources.lib.proxy_server import start_proxy, stop_proxy

_proxy_server = None
_proxy_port = None
_proxy_lock = threading.Lock()

def get_or_start_proxy():
    global _proxy_server, _proxy_port
    with _proxy_lock:
        if _proxy_server is None:
            _proxy_server, _proxy_port = start_proxy()
            xbmc.log("[JioTV] Proxy started on port %d" % _proxy_port, xbmc.LOGINFO)
        return _proxy_server, _proxy_port

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
        login_item.label = "Login (Needed for playing anything)"
        login_item.set_callback(loginRoute)
        result.append(login_item)
    return result

@Route.register
def logoutRoute(plugin):
    logout()
    Script.notify("Logout successfully!", "Redirecting after logout")
    plugin.container.refresh()

@Route.register
def loginRoute(plugin):
    number = Dialog().numeric(0, "Enter jio mobile number")
    if not number:
        Script.notify("Login cancelled", "No number entered")
        return
    number = str(number)
    otp_sent = sendOtp(number)
    if otp_sent:
        Script.notify("OTP SENT", "Otp sent successfully!")
        otp = Dialog().numeric(0, "Enter OTP")
        if not otp:
            Script.notify("Login cancelled", "No OTP entered")
            return
        otp = str(otp)
        otp_verify = verifyOTP(number, otp)
        if otp_verify:
            Script.notify("Login Done", "Successfully logged in.")
            plugin.container.refresh()
        else:
            Script.notify("Failed Login", "Unable to verify otp")
    else:
        Script.notify("Failed Login", "Failed to send OTP. Non jio number or invalid number")

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
        item.art.fanart = item.art.thumb = item.art.clearart = item.art.clearlogo = (
            "https://jiotv.catchup.cdn.jio.com/dare_images/images/" + i["logoUrl"]
        )
        item.art.icon = (
            "https://jiotv.catchup.cdn.jio.com/dare_images/images/" + i["logoUrl"]
        )
        item.set_callback(
            showPlayOptions,
            id=i["channel_id"],
            isCatchup=bool(i.get("stbCatchup", False)),
        )
        final_data.append(item)
    return final_data

@Route.register
def showPlayOptions(plugin, id, isCatchup):
    live = Listitem("video")
    live.label = "Watch Live"
    live.set_callback(play, id=id, catchup=False)
    if isCatchup:
        catchup = Listitem("video")
        catchup.label = "Watch Older Shows (Catchup)"
        catchup.set_callback(list_catchup_days, id=id)
        return [live, catchup]
    else:
        return live

@Route.register
def list_catchup_days(plugin, id):
    final = []
    today = Listitem("video")
    today.label = "Today's past programmes"
    today.set_callback(catchup_shows_list, id=id, day=0)
    final.append(today)
    for i in range(1, 8):
        item = Listitem("video")
        item.label = str(i) + " day older"
        item.set_callback(catchup_shows_list, id=id, day=i * -1)
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
        item.info.plot = (
            "Showtime: "
            + datetime.datetime.fromtimestamp(int(i["startEpoch"]) / 1000).strftime("%I:%M %p")
            + " - "
            + datetime.datetime.fromtimestamp(int(i["endEpoch"]) / 1000).strftime("%I:%M %p")
        )
        item.art.clearart = item.art.clearlogo = (
            "https://jiotv.catchup.cdn.jio.com/dare_images/images/" + i["episodeThumbnail"]
        )
        item.art.fanart = item.art.icon = item.art.thumb = (
            "https://jiotv.catchup.cdn.jio.com/dare_images/shows/" + i["episodePoster"]
        )
        item.set_callback(
            play,
            id=id,
            catchup=True,
            srno=i["srno"],
            showtime=i["showtime"],
            begin=i["startEpoch"],
            end=i["endEpoch"],
        )
        final.append(item)
    return final

@Resolver.register
def play(plugin, id, catchup, srno=None, showtime=None, begin=None, end=None):
    get_or_start_proxy()
    if catchup:
        play_url = getCatchupUrl(id, srno, begin, end, showtime)
        cookies_part = play_url.split("?")[1]
        if "bpk-tv" in cookies_part:
            cookie = "_" + cookies_part.split("&_")[1]
        elif "/HLS/" in cookies_part:
            cookie = "_" + cookies_part.split("&_")[1]
        else:
            cookie = cookies_part
        headers = jio_playheaders(cookie, id, srno)
    else:
        play_url = getLivePlayUrl(id)
        cookies_part = play_url.split("?")[1]
        if "bpk-tv" in cookies_part:
            cookie = "_" + cookies_part.split("&_")[1]
        elif "/HLS/" in cookies_part:
            cookie = "_" + cookies_part.split("&_")[1]
        else:
            cookie = cookies_part
        headers = jio_playheaders(cookie, id, "250623144006")

    clean_url = play_url
    proxy_url = f"http://127.0.0.1:{_proxy_port}/{quote(clean_url, safe='')}"

    final = Listitem("video")
    final.label = plugin._title
    final.set_callback(proxy_url)
    final.property["isPlayable"] = True
    final.property["inputstream"] = "inputstream.adaptive"
    final.property["inputstream.adaptive.stream_headers"] = urlencode(headers)
    final.property["inputstream.adaptive.manifest_headers"] = urlencode(headers)
    final.property["inputstream.adaptive.manifest_type"] = "hls"
    final.property["inputstream.adaptive.license_type"] = "drm"
    final.property["inputstream.adaptive.license_key"] = "|" + urlencode(headers) + "|R{SSM}|"
    final.property["inputstream.adaptive.stream_selection_type"] = "ask-quality"
    if not catchup:
        final.property["IsLive"] = "true"
    return final
