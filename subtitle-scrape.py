#!/usr/bin/env python3

import sys
import os
import json
import re
import tempfile
import random
import shutil
import urllib
import urllib.parse
from xml.dom.minidom import parse
import xml.dom.minidom
from http_client import HttpClient
from bs4 import BeautifulSoup
import traceback

#字幕文件后缀
global SUB_EXT_LIST
SUB_EXT_LIST = ( ".srt", ".sub", ".smi", ".ssa", ".ass", ".sup" )
#视频文件后缀
global VIDEO_EXT_LIST
VIDEO_EXT_LIST = (".mkv", ".mp4", ".ts", ".avi", ".mov", ".wmv", ".mpeg")

class UncompressLib():
    """
    压缩包解压库，原理是使用外部命令解压
    """
    def __init__(self, ext_map):
        self.__ext_map = ext_map

    def __file_extension(self, file_name, depth = 1):
        split_name = file_name.lower().split(".")
        idx = len(split_name) - depth
        if idx < 0:
            return None
        file_ext_str = ""
        while True:
            file_ext_str = file_ext_str + "." + split_name[idx]
            idx = idx + 1
            if idx == len(split_name):
                break
        return file_ext_str

    def is_support(self, ext):
        return ext in self.__ext_map

    def uncompress(self, zipfile, dir_path):
        file_name = os.path.basename(zipfile)
        uncompress_command = None
        ext = self.__file_extension(file_name, 2)
        if ext is not None:
            if ext in self.__ext_map:
                uncompress_command = self.__ext_map[ext]
        if uncompress_command is None:
            ext = self.__file_extension(file_name, 1)
            if ext in self.__ext_map:
                uncompress_command = self.__ext_map[ext]
        if uncompress_command is None:
            raise Exception("not supported archive extension.")
        uncompress_command = uncompress_command.replace("$archive_name", f"\"{zipfile}\"")
        os.chdir(dir_path)
        os.system(uncompress_command)
        #if os.system(uncompress_command) != 0:
        #    raise Exception("uncompress command failed.")

class AssrtSubtitle():
    """
    伪射手
    """
    def __init__(self, uncompress_lib, token, _type):
        self.__uncompress_lib = uncompress_lib
        self.__token = token
        self.__type = _type

    """
    遍历文件夹，再次解压
    """
    def __uncompress_again(self, dir_path, except_file):
        for f in os.listdir(dir_path):
            f_abs = os.path.join(dir_path, f)
            if os.path.isfile(f_abs):
                if f == except_file:
                    continue
                name, ext = os.path.splitext(f)
                if self.__uncompress_lib.is_support(ext):
                    self.__uncompress_lib.uncompress(f, dir_path)
            else:
                self.__uncompress_again(f_abs, except_file)


    """
    遍历文件夹，找到所有字幕文件
    """
    def __find_subs(self, dir_path, lst):
        for f in os.listdir(dir_path):
            f_abs = os.path.join(dir_path, f)
            if os.path.isfile(f_abs):
                name, ext = os.path.splitext(f)
                if ext in SUB_EXT_LIST:
                    lst.append(f_abs)
            else:
                self.__find_subs(f_abs, lst)

    """
    根据关键词，去a4k上爬字幕下载到指定的tmp文件夹
    """
    def download(self, keyword, tmp_dir):
        API_URL = "https://api.assrt.net/v1"
        http_client = HttpClient()
        headers, data = http_client.get(API_URL + "/sub/search", params = {
            "token": self.__token,
            "q": keyword
            })
        resData = json.loads(data.decode("utf-8"))
        print(resData)
        if(resData["status"] != 0):
            return []
        i = 0
        subs = resData["sub"]["subs"]
        while True:
            if i > 5:
                break
            if len(subs) == 0:
                break
            sub = subs[random.randint(0, len(subs) - 1)]
            i = i + 1
            if not "lang" in sub:
                i = i + 1
                continue
            if sub["lang"]["desc"].count("简") > 0 or sub["lang"]["desc"].count("繁") > 0 or sub["lang"]["desc"].count("双语") > 0:
                #https://api.assrt.net/v1/sub/detail?token=TOKEN&id=602333
                headers, data = http_client.get(API_URL + "/sub/detail", params = {
                    "token": self.__token,
                    "id": sub["id"]
                    })
                resData = json.loads(data.decode("utf-8"))
                if resData["status"] != 0 or len(resData["sub"]["subs"]) == 0:
                    i = i + 1
                    continue
                filename = resData["sub"]["subs"][0]["filename"]
                name, ext = os.path.splitext(filename)
                if ext not in SUB_EXT_LIST and not self.__uncompress_lib.is_support(ext):
                    i = i + 1
                    continue
                download_url = resData["sub"]["subs"][0]["url"]
                headers, data = http_client.get(download_url)
                tempfile = os.path.join(tmp_dir, filename)
                with open(tempfile, "wb") as f:
                    f.write(data)
                if ext in SUB_EXT_LIST:
                    return [tempfile]
                else:
                    self.__uncompress_lib.uncompress(tempfile, tmp_dir)
                    self.__uncompress_again(tmp_dir, tempfile)
                    subs = []
                    self.__find_subs(tmp_dir, subs)
                    if len(subs) == 0:
                        i = i + 1
                        continue
                    return subs
        return []

def show_usage():
    """
    打印使用方法
    """
    sys.stderr.write(f"{sys.argv[0]} config.json\n")
    sys.stderr.flush()
    sys.exit(1)

def check_subtitle_file_exist(dir_path, video_name):
    """
    检测字幕文件是否已存在
    """
    for f in os.listdir(dir_path):
        f_abs = os.path.join(dir_path, f)
        if os.path.isfile(f_abs):
            name, ext = os.path.splitext(os.path.basename(f_abs))
            if ext in SUB_EXT_LIST and name.startswith(video_name):
                return True
    return False

def download_movie_subtitle(dir_path, video_name, nfo_file):
    """
    刮削电影字幕

    参数：
        dir_path            文件夹路径
        video_name          电影文件名
        nfo_file            nfo文件
    """
    dom_tree = xml.dom.minidom.parse(nfo_file)
    document = dom_tree.documentElement
    title = document.getElementsByTagName("originaltitle")[0].childNodes[0].data
    year = document.getElementsByTagName("year")[0].childNodes[0].data
    #电影的关键词为标题+年份
    keyword = f"{title} {year}"
    keyword = re.sub("[：（）]", " ", keyword)
    sys.stdout.write(f"search keyword = {keyword}\n")
    sys.stdout.flush()
    tmp_dir = tempfile.mkdtemp()
    try:
        assrt = AssrtSubtitle(UNCOMPRESS_LIB, ASSRT_TOKEN, 1)
        subs = assrt.download(keyword, tmp_dir)
        for sub in subs:
            sub_name = os.path.basename(sub)
            sub_name_split = sub_name.split(".")
            if len(sub_name_split) <= 2 or len(subs) == 1:
                new_sub = os.path.join(dir_path, f"{video_name}.chs.{sub_name_split[-1]}")
            else:
                new_sub = os.path.join(dir_path, f"{video_name}.{sub_name_split[-2]}.{sub_name_split[-1]}")
            sys.stdout.write(f"{sub} -> {new_sub}\n")
            sys.stdout.flush()
            shutil.move(sub, new_sub)
    except Exception as e:
        traceback.print_exc()
        sys.stderr.flush()
    finally:
        shutil.rmtree(tmp_dir)

def download_tv_subtitle(dir_path, season, nfo_file):
    """
    刮削电视剧字幕

    参数：
        dir_path            文件夹路径
        season              季
        nfo_file            nfo文件
    """
    scraped = True
    for f in os.listdir(dir_path):
        name, ext = os.path.splitext(f)
        if ext.lower() not in VIDEO_EXT_LIST:
            continue
        if not check_subtitle_file_exist(dir_path, name):
            scraped = False
            break
    if scraped:
        sys.stdout.write(f"[{dir_path}] subtitle already exists.\n")
        sys.stdout.flush()
        return
    season_re = re.compile("([sS]\d+[eE]\d+)")
    dom_tree = xml.dom.minidom.parse(nfo_file)
    document = dom_tree.documentElement
    title = document.getElementsByTagName("originaltitle")[0].childNodes[0].data
    #电视的关键词为：标题+季
    #电视的字幕下载逻辑是整季下载，然后一个个文件去匹配改名
    keyword = f"{title} S{season:02d}"
    sys.stdout.write(f"search keyword = {keyword}\n")
    sys.stdout.flush()
    tmp_dir = tempfile.mkdtemp()
    try:
        assrt = AssrtSubtitle(UNCOMPRESS_LIB, ASSRT_TOKEN, 2)
        subs = assrt.download(keyword, tmp_dir)
        for f in os.listdir(dir_path):
            name, ext = os.path.splitext(f)
            if ext.lower() not in VIDEO_EXT_LIST:
                continue
            if check_subtitle_file_exist(dir_path, name):
                sys.stdout.write(f"[{name}] subtitle already exists.\n")
                sys.stdout.flush()
                continue
            season_match = season_re.findall(f)
            if len(season_match) == 0:
                continue
            video_season = season_match[0]
            for sub in subs:
                sub_name = os.path.basename(sub)
                season_match = season_re.findall(sub_name)
                if len(season_match) == 0:
                    continue
                sub_season = season_match[0]
                if sub_season.lower() == video_season.lower():
                    sub_name_split = sub_name.split(".")
                    if len(sub_name_split) <= 2 or len(subs) == 1:
                        new_sub = os.path.join(dir_path, f"{name}.chs.{sub_name_split[-1]}")
                    else:
                        new_sub = os.path.join(dir_path, f"{name}.{sub_name_split[-2]}.{sub_name_split[-1]}")
                    try:
                        sys.stdout.write(f"{sub} -> {new_sub}\n")
                        sys.stdout.flush()
                    except:
                        pass
                    shutil.move(sub, new_sub)
                    subs.remove(sub)
    except Exception as e:
        traceback.print_exc()
        sys.stderr.flush()
    finally:
        shutil.rmtree(tmp_dir)

def dir_scrape(dir_path, _type):
    """
    去具体文件夹刮削

    参数：
        dir_path            文件夹路径
        _type               类型：1：电影、2：电视剧
    """
    if os.path.exists(os.path.join(dir_path, ".skip_sub")):
        return
    for f in os.listdir(dir_path):
        f_abs = os.path.join(dir_path, f)
        if os.path.isfile(f_abs):
            if _type == 1:
                name, ext = os.path.splitext(f)
                if name == "trailer":
                    continue
                if ext.lower() not in VIDEO_EXT_LIST:
                    continue
                if check_subtitle_file_exist(dir_path, name):
                    sys.stdout.write(f"[{f_abs}] subtitle already exists.\n")
                    sys.stdout.flush()
                    continue
                nfo_file = None
                tmp_nfo_file = os.path.join(dir_path, "movie.nfo")
                if os.path.exists(tmp_nfo_file):
                    nfo_file = tmp_nfo_file
                if nfo_file is None:
                    tmp_nfo_file = os.path.join(dir_path, name + ".nfo")
                    if os.path.exists(tmp_nfo_file):
                        nfo_file = tmp_nfo_file
                if nfo_file is None:
                    sys.stdout.write(f"[{f_abs}] nfo file not exists, skip.\n")
                    sys.stdout.flush()
                    continue
                download_movie_subtitle(dir_path, name, nfo_file)
        else:
            if _type != 2:
                dir_scrape(f_abs, _type)
                continue
            nfo_file = os.path.join(f_abs, "tvshow.nfo")
            if not os.path.exists(nfo_file):
                dir_scrape(f_abs, _type)
                continue
            if os.path.exists(os.path.join(f_abs, ".skip_sub")):
                continue
            for d in os.listdir(f_abs):
                if not d.startswith("Season_"):
                    continue
                download_tv_subtitle(os.path.join(f_abs, d), int(d[7:]), nfo_file)
            continue

def subtitle_scrape(conf):
    """
    刮削字幕总入口
    """
    if "UncompressLib" not in conf:
        raise Exception("UncompressLib key not exists.")
    if "AssrtToken" not in conf:
        raise Exception("AssrtToken key not exists.")
    global UNCOMPRESS_LIB
    UNCOMPRESS_LIB = UncompressLib(conf["UncompressLib"])
    global ASSRT_TOKEN
    ASSRT_TOKEN = conf["AssrtToken"]
    if "MovieDir" in conf:
        conf_movie_dir = conf["MovieDir"]
        if type(conf_movie_dir) == str:
            movie_dir_list = [conf_movie_dir]
        elif type(conf_movie_dir) == list:
            movie_dir_list = conf_movie_dir
        else:
            movie_dir_list = []
        for movie_dir in movie_dir_list:
            if os.path.exists(movie_dir) and os.path.isdir(movie_dir):
                dir_scrape(movie_dir, 1)
            else:
                sys.stdout.write(f"Warning: movie dir ({movie_dir}) is not exists.\n")
                sys.stdout.flush()
    else:
        sys.stdout.write("Warning: MovieDir key not exists.\n")
        sys.stdout.flush()
    if "TvDir" in conf:
        conf_tv_dir = conf["TvDir"]
        if type(conf_tv_dir) == str:
            tv_dir_list = [conf_tv_dir]
        elif type(conf_tv_dir) == list:
            tv_dir_list = conf_tv_dir
        else:
            tv_dir_list = []
        for tv_dir in tv_dir_list:
            if os.path.exists(tv_dir) and os.path.isdir(tv_dir):
                dir_scrape(tv_dir, 2)
            else:
                sys.stdout.write(f"Warning: tv dir ({tv_dir}) is not exists.\n")
                sys.stdout.flush()
    else:
        sys.stdout.write("Warning: TvDir key not exists.\n")
        sys.stdout.flush()

if __name__ == "__main__":
    if len(sys.argv) == 1:
        show_usage()
    with open(sys.argv[1]) as f:
        conf = json.load(f)
    subtitle_scrape(conf)
