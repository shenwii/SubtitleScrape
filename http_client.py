# -*- coding: UTF-8 -*-

from urllib3 import encode_multipart_formdata
import json
import requests
import urllib.parse

class HttpClient():
    """
    封装了一个Http的客户端
    """
    def __init__(self):
        self.__session__ = requests.Session()
        self.__user_agent__ = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.80 Safari/537.36"
        self.__before_url__ = None

    def get(self, url, headers = {}, params = {}):
        """
        发送get请求

        参数：
            url                 请求的url
            headers             附加的头信息
            params              请求参数

        返回值：
            response_headers    响应头信息
            response_data       响应数据
        """
        headers["User-Agent"] = self.__user_agent__
        if self.__before_url__ is not None:
            headers["Referer"] = self.__before_url__
        url = url.rstrip("/")
        if len(params) != 0:
            if url[-1] != "?":
                url = url + "?"
            for k in params.keys():
                url = url + ("%s=%s&" % (k, urllib.parse.quote_plus(str(params[k]))))
            url = url[0:-1]
        http_response = self.__session__.get(url, headers = headers)
        self.__before_url__ = url
        response_headers = http_response.headers
        response_data = http_response.content
        return response_headers, response_data

    def post(self, url, headers = {}, datas = {}, data_type = "json"):
        """
        发送post请求

        参数：
            url                 请求的url
            headers             附加的头信息
            datas               请求数据
            data_type           数据类型：json、form-data、x-www-form-urlencoded

        返回值：
            response_headers    响应头信息
            response_data       响应数据
        """
        headers["User-Agent"] = self.__user_agent__
        if self.__before_url__ is not None:
            headers["Referer"] = self.__before_url__
        if data_type == "json":
            headers["Content-Type"] = "application/json"
            http_response = self.__session__.post(url, data = json.dumps(datas), headers = headers)
        elif data_type == "form-data":
            encode_data = encode_multipart_formdata(datas)
            headers["Content-Type"] = encode_data[1]
            http_response = self.__session__.post(url, data = encode_data[0], headers = headers)
        elif data_type == "x-www-form-urlencoded":
            headers["Content-Type"] = "application/x-www-form-urlencoded"
            http_response = self.__session__.post(url, data = datas, headers = headers)
        else:
            return None
        response_headers = http_response.headers
        response_data = http_response.content
        return response_headers, response_data
