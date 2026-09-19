import argparse
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib

VIEW_API = (
    "https://api.bilibili.com/"
    "x/web-interface/view"
)

DANMAKU_XML_API = (
    "https://comment.bilibili.com/"
    "{cid}.xml"
)


def build_request(
    url: str,
    referer: str | None = None,
) -> urllib.request.Request:
    """
    构造一个接近普通浏览器请求的 HTTP Request。
    """

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/152.0.0.0 Safari/537.36"
        ),
    }

    if referer:
        headers["Referer"] = referer

    return urllib.request.Request(
        url=url,
        headers=headers,
    )


def fetch_json(
    url: str,
    referer: str | None = None,
) -> dict:
    """
    GET 一个 JSON 接口。
    """

    request = build_request(
        url=url,
        referer=referer,
    )

    with urllib.request.urlopen(
        request,
        timeout=15,
    ) as response:
        body = response.read()

    return json.loads(
        body.decode("utf-8")
    )


def fetch_video_info(
    bvid: str,
) -> dict:
    """
    根据 BV 号获取视频元数据。

    重点使用：
    - title
    - aid
    - pages[]

    每个 pages[] 对应一个 B 站分 P，
    其中 cid 是读取弹幕的关键。
    """

    query = urllib.parse.urlencode(
        {
            "bvid": bvid,
        }
    )

    url = f"{VIEW_API}?{query}"

    data = fetch_json(
        url=url,
        referer=(
            f"https://www.bilibili.com/"
            f"video/{bvid}"
        ),
    )

    if data.get("code") != 0:
        raise RuntimeError(
            "Bilibili video API failed: "
            f"code={data.get('code')}, "
            f"message={data.get('message')}"
        )

    return data["data"]


def fetch_danmaku_xml(
    cid: int,
    bvid: str,
) -> bytes:
    """
    根据 cid 下载当前 XML 弹幕池。

    Bilibili 的 XML 弹幕接口可能返回：
    - 明文 XML
    - zlib deflate
    - raw deflate

    因此这里统一解压成真正的 XML bytes，
    后面的 XML parser 不需要关心 HTTP 压缩格式。
    """

    url = DANMAKU_XML_API.format(
        cid=cid
    )

    request = build_request(
        url=url,
        referer=(
            f"https://www.bilibili.com/"
            f"video/{bvid}"
        ),
    )

    with urllib.request.urlopen(
        request,
        timeout=15,
    ) as response:
        data = response.read()

    # 已经是明文 XML
    stripped = data.lstrip()

    if (
        stripped.startswith(b"<?xml")
        or stripped.startswith(b"<i")
    ):
        return data

    # 先尝试标准 zlib deflate
    try:
        return zlib.decompress(data)
    except zlib.error:
        pass

    # Bilibili 常见的是 headerless raw deflate
    try:
        return zlib.decompress(
            data,
            -zlib.MAX_WBITS,
        )
    except zlib.error as exc:
        preview = data[:80]

        raise RuntimeError(
            "无法解析 Bilibili 弹幕响应。"
            f"\nCID: {cid}"
            f"\n响应前 80 bytes: {preview!r}"
        ) from exc
    
def parse_danmaku_xml(
    xml_bytes: bytes,
) -> list[dict]:
    """
    将 B 站 XML 弹幕转换为一个简单结构。

    XML 中：

        <d p="12.345,...">哈哈哈</d>

    p 的第一个字段就是弹幕出现时间，
    单位为秒。
    """

    root = ET.fromstring(
        xml_bytes
    )

    results: list[dict] = []

    for element in root.findall("d"):
        p = element.attrib.get(
            "p",
            "",
        )

        fields = p.split(",")

        if not fields:
            continue

        try:
            timestamp_seconds = float(
                fields[0]
            )
        except ValueError:
            continue

        text = (
            element.text or ""
        ).strip()

        if not text:
            continue

        results.append(
            {
                "timestamp_ms": int(
                    timestamp_seconds
                    * 1000
                ),
                "text": text,
            }
        )

    results.sort(
        key=lambda item: (
            item["timestamp_ms"]
        )
    )

    return results


def format_time(
    timestamp_ms: int,
) -> str:
    total_seconds = (
        timestamp_ms // 1000
    )

    hours = total_seconds // 3600

    minutes = (
        total_seconds % 3600
    ) // 60

    seconds = total_seconds % 60

    return (
        f"{hours:02d}:"
        f"{minutes:02d}:"
        f"{seconds:02d}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "bvid",
        help="Bilibili BV ID",
    )

    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="每个 Part 显示多少条弹幕",
    )

    args = parser.parse_args()

    bvid = args.bvid.strip()

    print(
        f"读取视频: {bvid}"
    )

    video = fetch_video_info(
        bvid=bvid
    )

    print("=" * 70)

    print(
        "Title:",
        video.get("title"),
    )

    print(
        "AID:",
        video.get("aid"),
    )

    print(
        "BVID:",
        video.get("bvid"),
    )

    print(
        "Owner:",
        video.get(
            "owner",
            {},
        ).get("name"),
    )

    pages = video.get(
        "pages",
        []
    )

    print(
        "Parts:",
        len(pages),
    )

    print("=" * 70)

    total_danmaku = 0

    for page in pages:
        page_number = page["page"]

        cid = page["cid"]

        part_title = page.get(
            "part",
            "",
        )

        duration = page.get(
            "duration",
            0,
        )

        print()

        print(
            f"Part P{page_number - 1}"
        )

        print(
            "CID:",
            cid,
        )

        print(
            "Title:",
            part_title,
        )

        print(
            "Duration:",
            f"{duration}s",
        )

        xml_bytes = (
            fetch_danmaku_xml(
                cid=cid,
                bvid=bvid,
            )
        )

        danmaku = parse_danmaku_xml(
            xml_bytes
        )

        total_danmaku += len(
            danmaku
        )

        print(
            "Danmaku:",
            len(danmaku),
        )

        print(
            "First danmaku:"
        )

        for item in danmaku[
            : args.top
        ]:
            print(
                " ",
                format_time(
                    item[
                        "timestamp_ms"
                    ]
                ),
                item["text"],
            )

    print()
    print("=" * 70)

    print(
        "Total danmaku:",
        total_danmaku,
    )


if __name__ == "__main__":
    main()