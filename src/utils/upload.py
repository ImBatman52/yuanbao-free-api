import hmac
import urllib.parse
import xml.etree.ElementTree as ET
from hashlib import sha1
from typing import Dict


def generate_q_signature(
    http_method: str,
    path: str,
    query_params: Dict[str, str],
    headers: Dict[str, str],
    sign_time: str,
    secret_key: str,
) -> str:

    def url_encode(s: str, safe: str = "") -> str:
        return urllib.parse.quote(s, safe=safe)

    def canonicalize_params(params: Dict[str, str]) -> str:
        normalized = {k.lower(): v for k, v in params.items()}
        sorted_items = sorted(normalized.items())
        return "&".join(f"{url_encode(k)}={url_encode(v)}" for k, v in sorted_items)

    encoded_path = url_encode(path.strip(), safe="/")

    canonical_query_string = canonicalize_params(query_params)

    canonical_headers = canonicalize_params(headers)

    format_string = (
        f"{http_method.lower()}\n" f"{encoded_path}\n" f"{canonical_query_string}\n" f"{canonical_headers}\n"
    )
    format_string_hash = sha1(format_string.encode()).hexdigest()

    string_to_sign = f"sha1\n{sign_time}\n{format_string_hash}\n"
    sign_key = hmac.new(secret_key.encode(), sign_time.encode(), sha1).hexdigest()
    signature = hmac.new(sign_key.encode(), string_to_sign.encode(), sha1).hexdigest()

    return signature


def generate_headers(file_type: str, content_length: int, upload_host: str, upload_info: Dict, user_agent: str) -> Dict:
    content_length = str(content_length)

    headers = {
        "Host": upload_host,
        "Content-Length": content_length,
        "Content-Type": "application/octet-stream",
        "Origin": "https://yuanbao.tencent.com",
        "Referer": "https://yuanbao.tencent.com/",
        "User-Agent": user_agent,
        "x-cos-security-token": upload_info["encryptToken"],
    }

    path = upload_info["location"]
    headers_to_sign = {
        "content-length": content_length,
        "host": upload_host,
    }
    query_params = {}
    sign_time = f"{upload_info['startTime']};{upload_info['expiredTime']}"
    secret_key = upload_info["encryptTmpSecretKey"]

    if file_type == "image":
        headers["Content-Type"] = "image/png"
        pic_operations = (
            '{"is_pic_info":1,"rules":[{"fileid":"%s","rule":"imageMogr2/format/jpg"}]}' % upload_info["location"]
        )
        headers["Pic-Operations"] = pic_operations
        headers_to_sign["pic-operations"] = pic_operations

    signature = generate_q_signature("PUT", path, query_params, headers_to_sign, sign_time, secret_key)

    auth_params = {
        "q-sign-algorithm": "sha1",
        "q-ak": upload_info["encryptTmpSecretId"],
        "q-sign-time": sign_time,
        "q-key-time": sign_time,
        "q-header-list": ";".join(headers_to_sign.keys()),
        "q-url-param-list": "",
        "q-signature": signature,
    }

    headers["Authorization"] = "&".join([f"{k}={v}" for k, v in auth_params.items()])
    return headers


def get_file_info(file_type: str, file_name: str, content_length, url: str, xml_data: str) -> Dict:
    file_info = {
        "type": file_type,
        "docType": file_type,
        "url": url,
        "fileName": file_name,
        "size": 0,
        "width": 0,
        "height": 0,
    }

    if file_type == "image":
        root = ET.fromstring(xml_data)
        process_result = root.find("ProcessResults/Object")

        file_info["size"] = int(process_result.find("Size").text)
        file_info["width"] = int(process_result.find("Width").text)
        file_info["height"] = int(process_result.find("Height").text)
    else:
        file_info["size"] = content_length
    return file_info
