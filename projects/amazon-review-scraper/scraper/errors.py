"""失败保留类型与部分评论，避免把错误视为空评论成功。"""


class CrawlError(RuntimeError):
    def __init__(self, status, message, reviews=None):
        super().__init__(message)
        self.status = status
        self.reviews = list(reviews or [])
