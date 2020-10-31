"""
Downloader Middleware manager

See documentation in docs/topics/downloader-middleware.rst
"""
import six

from twisted.internet import defer

from scrapy.exceptions import _InvalidOutput
from scrapy.http import Request, Response
from scrapy.middleware import MiddlewareManager
from scrapy.utils.defer import mustbe_deferred
from scrapy.utils.conf import build_component_list


class DownloaderMiddlewareManager(MiddlewareManager):

    component_name = 'downloader middleware'

    @classmethod
    def _get_mwlist_from_settings(cls, settings):
        return build_component_list(
            settings.getwithbase('DOWNLOADER_MIDDLEWARES'))

    def _add_middleware(self, mw):
        if hasattr(mw, 'process_request'):
            self.methods['process_request'].append(mw.process_request)
        if hasattr(mw, 'process_response'):
            self.methods['process_response'].appendleft(mw.process_response)
        if hasattr(mw, 'process_exception'):
            self.methods['process_exception'].appendleft(mw.process_exception)

    def download(self, download_func, request, spider):
        @defer.inlineCallbacks
        def process_request(request):
            # 如果下载器中间件有定义process_request，则依次运行
            for method in self.methods['process_request']:
                response = yield method(request=request, spider=spider)
                if response is not None and not isinstance(response, (Response, Request)):
                    raise _InvalidOutput('Middleware %s.process_request must return None, Response or Request, got %s' % \
                                         (six.get_method_self(method).__class__.__name__, response.__class__.__name__))
                # 如果下载器中间件有返回值，直接返回此结果
                if response:
                    defer.returnValue(response)
            # 如果下载器中间件没有返回值，则执行注册进来的方法，也就是Downloader的_enqueue_request
            defer.returnValue((yield download_func(request=request, spider=spider)))

        @defer.inlineCallbacks
        def process_response(response):
            assert response is not None, 'Received None in process_response'
            if isinstance(response, Request):
                defer.returnValue(response)
            # 如果下载器中间件有定义process_response,则依次执行
            for method in self.methods['process_response']:
                response = yield method(request=request, response=response, spider=spider)
                if not isinstance(response, (Response, Request)):
                    raise _InvalidOutput('Middleware %s.process_response must return Response or Request, got %s' % \
                                         (six.get_method_self(method).__class__.__name__, type(response)))
                if isinstance(response, Request):
                    defer.returnValue(response)
            defer.returnValue(response)

        @defer.inlineCallbacks
        def process_exception(_failure):
            exception = _failure.value
            # 如果下载器中间件有定义process_exception,则依次执行
            for method in self.methods['process_exception']:
                response = yield method(request=request, exception=exception, spider=spider)
                if response is not None and not isinstance(response, (Response, Request)):
                    raise _InvalidOutput('Middleware %s.process_exception must return None, Response or Request, got %s' % \
                                         (six.get_method_self(method).__class__.__name__, type(response)))
                if response:
                    defer.returnValue(response)
            defer.returnValue(_failure)
        # 注册执行、错误、回调方法
        deferred = mustbe_deferred(process_request, request)
        deferred.addErrback(process_exception)
        deferred.addCallback(process_response)
        return deferred
