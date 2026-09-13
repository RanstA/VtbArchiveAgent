from pydantic import BaseModel


class SignalWindow(BaseModel):
    """
    某个 StreamPart 中的一个时间窗口。

    例如：

        part_id = 123456
        start_ms = 60_000
        end_ms = 90_000
        scale_ms = 30_000

    表示：
        这个 Part 的 01:00 ~ 01:30 这一段。

    一个 SignalWindow 同时保存：
    1. 原始弹幕统计
    2. 相对于本场直播的异常程度
    3. 最终综合异常分数
    """

    # 这个窗口属于哪一场直播
    stream_id: str

    # 这个窗口属于直播中的哪一个录像 Part
    # 因为同一场直播可能有多个 mp4 / ass Part，
    # 时间戳目前都是 Part 内局部时间。
    part_id: str

    # 窗口开始时间，单位毫秒。
    # 例如 60_000 表示 01:00。
    start_ms: int

    # 窗口结束时间，单位毫秒。
    # 例如 90_000 表示 01:30。
    end_ms: int

    # 这个窗口本身有多长，单位毫秒。
    #
    # 例如：
    # 30_000  -> 30 秒窗口
    # 60_000  -> 60 秒窗口
    # 120_000 -> 120 秒窗口
    scale_ms: int

    # 这个时间窗口里一共有多少条弹幕。
    #
    # 用来衡量弹幕密度。
    danmaku_count: int

    # 这个窗口里有多少种不同的弹幕文本。
    #
    # 例如：
    #
    # 哈哈哈
    # 哈哈哈
    # 怎么回事
    #
    # danmaku_count = 3
    # unique_text_count = 2
    unique_text_count: int

    # 复读比例。
    #
    # 用于描述：
    # “大家是不是突然开始重复相同的话。”
    #
    # 范围大致为 0 ~ 1。
    #
    # 越高说明相同文本重复得越严重。
    repetition_ratio: float

    # 强反应弹幕比例。
    #
    # 当前 V0 中把类似：
    # 哈哈哈
    # ？？？
    # ！！！
    #
    # 视为 reaction。
    #
    # 越高代表这个窗口中的观众强反应越集中。
    reaction_ratio: float

    # 包含“哈哈 / hhh / www / 草 / 笑死”等
    # 笑声反应的弹幕数量。
    laugh_count: int

    # 包含 ? / ？ 的弹幕数量。
    #
    # 通常用于表示：
    # 疑惑、震惊、没听懂、发生奇怪事情等。
    question_count: int

    # 包含 ! / ！ 的弹幕数量。
    #
    # 粗略表示较强烈的情绪反应。
    exclamation_count: int

    # 弹幕密度异常分数。
    #
    # 注意：
    # 它不是原始弹幕数量。
    #
    # 它表示：
    # “当前窗口的弹幕数量，
    # 在这一场直播的同尺度窗口中有多异常。”
    #
    # 归一化后范围 0 ~ 1。
    density_score: float = 0.0

    # 复读异常分数。
    #
    # 表示当前 repetition_ratio
    # 相对于这一场直播其他窗口有多高。
    #
    # 范围 0 ~ 1。
    repetition_score: float = 0.0

    # 强反应异常分数。
    #
    # 表示当前 reaction_ratio
    # 相对于这一场直播其他窗口有多异常。
    #
    # 范围 0 ~ 1。
    reaction_score: float = 0.0

    # 最终综合异常分数。
    #
    # 第一版我们会把：
    #
    # density_score
    # repetition_score
    # reaction_score
    #
    # 按一定权重组合起来。
    #
    # score 越高，
    # 说明这个窗口越值得作为 Highlight Candidate 检查。
    score: float = 0.0
