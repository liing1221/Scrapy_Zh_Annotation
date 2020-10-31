from __future__ import print_function
import os
import logging

from scrapy.utils.job import job_dir
from scrapy.utils.request import referer_str, request_fingerprint

class BaseDupeFilter(object):
    # 过滤器基类，子类可重写以下方法
    @classmethod
    def from_settings(cls, settings):
        return cls()

    def request_seen(self, request):
        # 请求过滤
        return False

    def open(self):  # can return deferred
        # 可重写，完成过滤器的初始化工作
        pass

    def close(self, reason):  # can return a deferred
        # 可重写，完成关闭过滤器工作
        pass

    def log(self, request, spider):  # log that a request has been filtered
        pass


class RFPDupeFilter(BaseDupeFilter):
    """Request Fingerprint duplicates filter"""

    def __init__(self, path=None, debug=False):
        self.file = None
        self.fingerprints = set()
        self.logdupes = True
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        if path:
            self.file = open(os.path.join(path, 'requests.seen'), 'a+')
            self.file.seek(0)
            self.fingerprints.update(x.rstrip() for x in self.file)

    @classmethod
    def from_settings(cls, settings):
        debug = settings.getbool('DUPEFILTER_DEBUG')
        return cls(job_dir(settings), debug)

    def request_seen(self, request):
        # 生成请求指纹
        fp = self.request_fingerprint(request)
        # 请求指纹如果在指纹集合中，则认为重复
        if fp in self.fingerprints:
            return True
        # 不重复则记录此指纹
        self.fingerprints.add(fp)
        # 实例化 如果有path，则把指纹写入文件
        if self.file:
            self.file.write(fp + os.linesep)

    def request_fingerprint(self, request):
        # 调用utils.request的request_fingerprint
        return request_fingerprint(request)

    def close(self, reason):
        if self.file:
            self.file.close()

    def log(self, request, spider):
        if self.debug:
            msg = "Filtered duplicate request: %(request)s (referer: %(referer)s)"
            args = {'request': request, 'referer': referer_str(request) }
            self.logger.debug(msg, args, extra={'spider': spider})
        elif self.logdupes:
            msg = ("Filtered duplicate request: %(request)s"
                   " - no more duplicates will be shown"
                   " (see DUPEFILTER_DEBUG to show all duplicates)")
            self.logger.debug(msg, {'request': request}, extra={'spider': spider})
            self.logdupes = False

        spider.crawler.stats.inc_value('dupefilter/filtered', spider=spider)
