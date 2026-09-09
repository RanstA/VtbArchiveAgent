from pathlib import Path

from app.ingestion.ass_parser import parse_ass


path = Path(
    r"E:\repository\MikotoRecord\2025年9月录播\【直播回放】いろいろ聊 2025年09月11日19点场\【直播回放】いろいろ聊 2025年09月11日19点场_32316327100.ass"
)

danmaku = parse_ass(
    path=path,
    stream_id="test-stream",
)

print("弹幕数量:", len(danmaku))

for item in danmaku[:10]:
    print(
        item.timestamp_ms,
        item.text,
    )
    
def test_parse_ass():
    danmaku = parse_ass(TEST_ASS_PATH, "test-stream")

    assert len(danmaku) > 0
    assert all(item.timestamp_ms >= 0 for item in danmaku)
    assert all(item.text.strip() for item in danmaku)

    # 解析后的正文不应该残留常见 ASS override tag
    assert all(r"{\c" not in item.text for item in danmaku)
    assert all(r"\move" not in item.text for item in danmaku)